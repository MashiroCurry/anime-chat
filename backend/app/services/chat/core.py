"""ChatCoreService：核心对话服务（三层架构的核心层）。

只处理 LLM + 记忆 + 角色卡，完全不知道消息来自哪个渠道。
通过 MessageChannel 接口输出，WS / 微信 / QQ 由 Adapter 承载。
"""

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger
from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import redact
from app.core.messaging.channel import MessageChannel
from app.core.messaging.exceptions import ChannelException
from app.core.messaging.types import ReplyResult, UnifiedMessage
from app.db.session import async_session_factory
from app.models import Character, Conversation, Message
from app.models.character import DEFAULT_OWNER_ID
from app.schemas.character import CharacterCard
from app.services.character import build_system_prompt
from app.services.memory import Memory

# 结果就绪回调：核心层处理完一条消息后，把完整回复抛给监听者（微信异步推送用）
ReplyHandler = Callable[[ReplyResult], Awaitable[None]]

# 无角色时的默认系统提示词（向后兼容，不强制用户先建角色）
_DEFAULT_SYSTEM_PROMPT = "你是一个 AI 伴侣。请自然、温暖地回应用户。"

# 带上下文的最近消息条数
_CONTEXT_LIMIT = 20

# 记忆检索超时（秒）——embedding 服务超时不能阻塞聊天
_MEMORY_SEARCH_TIMEOUT = 1.5

# 记忆注入预算：每条截断字数 / 总预算（中文字符数，约对应 ~800 token）
_MEMORY_ITEM_MAX_CHARS = 200
_MEMORY_BUDGET_CHARS = 600


def _build_messages(history: list[Message], user_text: str, system_prompt: str) -> list[dict]:
    """把 DB 历史 + 本轮用户消息组装成 OpenAI 兼容消息列表。"""
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_text})
    return messages


def _inject_memories(system_prompt: str, memories: list[Memory]) -> str:
    """把召回的记忆追加到 system prompt 末尾（末尾权重更高），带 token 预算。"""
    if not memories:
        return system_prompt

    ordered = sorted(
        memories, key=lambda m: m.score if m.score is not None else 0.0, reverse=True
    )
    lines: list[str] = []
    budget = _MEMORY_BUDGET_CHARS
    for m in ordered:
        text = (m.content or "").strip()
        if not text:
            continue
        text = text[:_MEMORY_ITEM_MAX_CHARS]
        if len(text) > budget:
            text = text[:budget]
        if not text:
            break
        lines.append(f"- {text}")
        budget -= len(text)

    if not lines:
        return system_prompt

    block = "你记得的关于用户的事：\n" + "\n".join(lines)
    return f"{system_prompt}\n\n{block}"


async def _safe_add(memory, messages: list[dict], user_id: str, character_id: str) -> None:
    """记忆抽取兜底：异常不吞，不阻塞主流程。"""
    try:
        await memory.add(messages, user_id=user_id, character_id=character_id)
    except Exception:  # noqa: BLE001
        logger.exception("memory.add 失败")


class ChatCoreService:
    """核心对话服务：接收 UnifiedMessage，产出回复（通过 MessageChannel）。"""

    def __init__(self, llm, memory) -> None:
        self._llm = llm
        self._memory = memory
        self._reply_handlers: list[ReplyHandler] = []
        # 记忆抽取：按 character_id 串行化，防并发写重复记忆
        self._extract_locks: dict[str, asyncio.Lock] = {}
        # 持引用防 GC：asyncio.create_task 不存引用会被中途回收（Python 官方警告）
        self._extract_tasks: set[asyncio.Task] = set()

    def on_reply(self, handler: ReplyHandler) -> None:
        """注册「回复就绪」回调。处理完一条消息后，把完整结果抛给监听者。

        流式渠道（WS）走 channel.send_delta 逐 token 输出；
        需要完整回复的渠道（微信异步推送）监听此回调。
        """
        self._reply_handlers.append(handler)

    def _spawn_extraction(self, user_text: str, assistant_text: str, character_id: str) -> None:
        """投递记忆抽取任务：同角色串行化，任务持引用防 GC。"""
        lock = self._extract_locks.setdefault(character_id, asyncio.Lock())
        task = asyncio.create_task(
            self._extract(lock, user_text, assistant_text, character_id)
        )
        self._extract_tasks.add(task)
        task.add_done_callback(self._extract_tasks.discard)

    async def _extract(
        self, lock: asyncio.Lock, user_text: str, assistant_text: str, character_id: str
    ) -> None:
        """在锁内执行抽取，保证同一角色的抽取不并发。"""
        async with lock:
            await _safe_add(
                self._memory,
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": assistant_text},
                ],
                DEFAULT_OWNER_ID,
                character_id,
            )

    async def handle_message(
        self, msg: UnifiedMessage, api_key: str, channel: MessageChannel
    ) -> None:
        """处理一条消息：角色卡 + 记忆 + LLM + 落库，输出经 channel 发出。"""
        settings = get_settings()

        async with async_session_factory() as session:
            # 确定会话（session_id ↔ conversation_id）
            conversation: Conversation | None = None
            if msg.session_id:
                conversation = await session.get(Conversation, msg.session_id)
            if conversation is None:
                conversation = Conversation()
                session.add(conversation)
                await session.flush()  # 拿到 conversation.id

            # 载入角色卡（可选）
            character: Character | None = None
            if msg.character_id:
                character = await session.get(Character, msg.character_id)

            # 先拉历史上下文（此时本轮用户消息尚未落库，故不含本轮，避免重复拼接）
            stmt = (
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc())
                .limit(_CONTEXT_LIMIT)
            )
            rows = (await session.scalars(stmt)).all()
            history = list(reversed(rows))  # 时间正序

            # 再落库本轮用户消息
            user_msg = Message(
                conversation_id=conversation.id, role="user", content=msg.content
            )
            session.add(user_msg)

            await session.commit()

        # 组装 system prompt：有角色卡用人设，否则默认
        if character is not None:
            card = CharacterCard.model_validate(character.card)
            system_prompt = build_system_prompt(character.name, card)
            temperature = card.llm.temperature
        else:
            system_prompt = _DEFAULT_SYSTEM_PROMPT
            temperature = None

        # 记忆检索注入（读路径）：超时/异常降级空，不阻塞聊天
        if settings.memory_search_enabled and msg.character_id:
            try:
                memories = await asyncio.wait_for(
                    self._memory.search(
                        msg.content,
                        user_id=DEFAULT_OWNER_ID,
                        character_id=msg.character_id,
                    ),
                    timeout=_MEMORY_SEARCH_TIMEOUT,
                )
            except Exception:  # noqa: BLE001
                logger.debug("记忆检索失败，降级为空")
                memories = []
            system_prompt = _inject_memories(system_prompt, memories)

        messages = _build_messages(history, msg.content, system_prompt)

        # 流式生成
        collected: list[str] = []
        try:
            async for delta in self._llm.chat_stream(
                messages, api_key, temperature=temperature
            ):
                collected.append(delta)
                await channel.send_delta(msg.user_id, delta)
        except Exception as e:
            logger.error("LLM 调用失败：{}", redact(str(e)))
            await channel.send_error(msg.user_id, "llm_error", redact(str(e)))
            return

        full_text = "".join(collected)

        # 落库助手消息
        async with async_session_factory() as session:
            assistant_msg = Message(
                conversation_id=conversation.id, role="assistant", content=full_text
            )
            session.add(assistant_msg)
            await session.commit()
            message_id = assistant_msg.id

        # 构造完整结果，经 on_reply 回调抛出（微信异步推送用）
        result = ReplyResult(
            user_id=msg.user_id,
            content=full_text,
            message_id=message_id,
            session_id=conversation.id,
        )

        # 流式结束通知（WS 用）：渠道异常降级，不崩溃、不吞结果
        try:
            await channel.send_done(msg.user_id, message_id, conversation.id)
        except ChannelException as e:
            logger.warning("渠道发送失败（已降级）：[{}] {}", e.code, e.message)

        # 结果就绪回调（需要完整回复的渠道，如微信异步推送）
        for handler in self._reply_handlers:
            try:
                await handler(result)
            except ChannelException as e:
                logger.warning("结果回调渠道异常（已降级）：[{}] {}", e.code, e.message)
            except Exception:  # noqa: BLE001
                logger.exception("on_reply 处理器异常")

        # 记忆抽取投递（写路径）：fire-and-forget，不阻塞主流程。
        # 可靠性：同角色串行化（防并发写重复），任务持引用（防 GC 中途消失）。
        if settings.memory_extract_enabled and msg.character_id:
            self._spawn_extraction(msg.content, full_text, msg.character_id)
