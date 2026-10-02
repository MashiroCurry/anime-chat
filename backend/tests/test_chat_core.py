"""ChatCoreService 单元测试：直接测核心层，不经过 WS 传输。

验证核心层只依赖 MessageChannel 接口，正确产出流式输出、载入角色卡、注入记忆。
"""

import asyncio

import pytest

from app.core.messaging.channel import MessageCallback
from app.core.messaging.exceptions import CODE_WECHAT_48H_LIMIT, ChannelException
from app.core.messaging.types import ReplyResult, UnifiedMessage
from app.db.session import async_session_factory
from app.models import Character
from app.services.chat import ChatCoreService
from app.services.memory.base import Memory


class FakeChannel:
    def __init__(self):
        self.deltas: list[str] = []
        self.done: tuple[str, str] | None = None
        self.errors: list[tuple[str, str]] = []

    def on_message(self, callback: MessageCallback) -> None:
        self._cb = callback

    async def send_delta(self, user_id: str, text: str) -> None:
        self.deltas.append(text)

    async def send_done(self, user_id: str, message_id: str, session_id: str) -> None:
        self.done = (message_id, session_id)

    async def send_error(self, user_id: str, code: str, message: str) -> None:
        self.errors.append((code, message))


class FakeLLM:
    def __init__(self, chunks: list[str]):
        self._chunks = chunks
        self.messages: list[dict] = []

    async def chat_stream(self, messages, api_key, **kw):
        self.messages = list(messages)
        for c in self._chunks:
            yield c


class FakeMemory:
    def __init__(self, search_result: list[Memory] | None = None):
        self._search = search_result or []
        self.added: list = []

    async def search(self, query, *, user_id, character_id=None, top_k=8):
        return self._search

    async def add(self, messages, *, user_id, character_id=None):
        self.added.append((messages, user_id, character_id))


class ConcurrencyTrackingMemory(FakeMemory):
    """记录 add 的最大并发数，用于验证同角色抽取被串行化。"""

    def __init__(self):
        super().__init__()
        self._active = 0
        self.max_active = 0

    async def add(self, messages, *, user_id, character_id=None):
        self._active += 1
        self.max_active = max(self.max_active, self._active)
        await asyncio.sleep(0.02)  # 拉开窗口，无锁时并发会叠加
        self._active -= 1
        self.added.append((messages, user_id, character_id))


async def _create_character(name: str, identity: str) -> str:
    async with async_session_factory() as s:
        c = Character(name=name, card={"persona": {"identity": identity}})
        s.add(c)
        await s.commit()
        return c.id


def _msg(character_id: str | None = None) -> UnifiedMessage:
    return UnifiedMessage(
        user_id="local",
        session_id=None,
        content="你好",
        timestamp=0.0,
        channel_type="ws",
        character_id=character_id,
    )


@pytest.mark.anyio
async def test_core_streams_delta_and_done():
    core = ChatCoreService(FakeLLM(["你", "好"]), FakeMemory())
    channel = FakeChannel()
    await core.handle_message(_msg(), "sk-test", channel)

    assert channel.deltas == ["你", "好"]
    assert channel.done is not None
    assert channel.errors == []


@pytest.mark.anyio
async def test_core_loads_character_prompt():
    cid = await _create_character("傲娇猫", "一只猫")
    llm = FakeLLM(["喵"])
    core = ChatCoreService(llm, FakeMemory())
    channel = FakeChannel()
    await core.handle_message(_msg(cid), "sk-test", channel)

    # LLM 收到的 system prompt 应含角色名与人设
    assert llm.messages[0]["role"] == "system"
    assert "傲娇猫" in llm.messages[0]["content"]
    assert "一只猫" in llm.messages[0]["content"]


@pytest.mark.anyio
async def test_core_injects_memory():
    cid = await _create_character("小明", "测试")
    memory = FakeMemory([Memory(memory_id="m1", content="用户喜欢猫", score=0.9)])
    llm = FakeLLM(["好"])
    core = ChatCoreService(llm, memory)
    channel = FakeChannel()
    await core.handle_message(_msg(cid), "sk-test", channel)

    system = llm.messages[0]["content"]
    assert "你记得的关于用户的事" in system
    assert "用户喜欢猫" in system


@pytest.mark.anyio
async def test_core_llm_error_sends_error_frame():
    class RaisingLLM:
        async def chat_stream(self, messages, api_key, **kw):
            if False:
                yield
            raise RuntimeError("upstream failed sk-secretkey123")

    core = ChatCoreService(RaisingLLM(), FakeMemory())
    channel = FakeChannel()
    await core.handle_message(_msg(), "sk-test", channel)

    assert channel.done is None
    assert len(channel.errors) == 1
    code, message = channel.errors[0]
    assert code == "llm_error"
    assert "sk-secretkey123" not in message  # 密钥已脱敏


@pytest.mark.anyio
async def test_core_on_reply_callback():
    """处理完消息后，经 on_reply 回调抛出完整结果（微信异步推送用）。"""
    core = ChatCoreService(FakeLLM(["你好", "呀"]), FakeMemory())
    results: list[ReplyResult] = []
    core.on_reply(lambda r: _collect(r, results))

    channel = FakeChannel()
    await core.handle_message(_msg(), "sk-test", channel)

    assert len(results) == 1
    assert results[0].content == "你好呀"
    assert results[0].message_id
    assert results[0].session_id


async def _collect(r: ReplyResult, out: list[ReplyResult]) -> None:
    out.append(r)


@pytest.mark.anyio
async def test_core_channel_exception_degrades():
    """Adapter 抛 ChannelException 时，核心层降级不崩溃（不抛给上层）。"""

    class RaisingChannel(FakeChannel):
        async def send_done(self, user_id, message_id, session_id):
            raise ChannelException(CODE_WECHAT_48H_LIMIT, "已超 48 小时窗口")

    core = ChatCoreService(FakeLLM(["好"]), FakeMemory())
    channel = RaisingChannel()
    # 不应抛出异常；结果仍经 on_reply 正常抛出
    results: list[ReplyResult] = []
    core.on_reply(lambda r: _collect(r, results))
    await core.handle_message(_msg(), "sk-test", channel)

    assert len(results) == 1
    assert results[0].content == "好"


@pytest.mark.anyio
async def test_no_duplicate_user_message():
    """回归测试：本轮用户消息只应出现一次（历史拼接不重复）。"""
    llm = FakeLLM(["好"])
    core = ChatCoreService(llm, FakeMemory())
    channel = FakeChannel()
    await core.handle_message(_msg(), "sk-test", channel)

    # LLM 收到的 messages 里，content="你好" 的 user 消息只出现一次
    user_msgs = [m for m in llm.messages if m["role"] == "user" and m["content"] == "你好"]
    assert len(user_msgs) == 1, f"用户消息重复了 {len(user_msgs)} 次"


@pytest.mark.anyio
async def test_multi_turn_no_duplicate():
    """多轮对话：历史 + 本轮，每轮用户消息各一次，无重复。"""
    llm = FakeLLM(["好"])
    core = ChatCoreService(llm, FakeMemory())
    channel = FakeChannel()

    # 第一轮
    m1 = _msg()
    await core.handle_message(m1, "sk-test", channel)
    session_id = channel.done[1]  # 复用会话

    # 第二轮（同一会话）
    m2 = UnifiedMessage(
        user_id="local", session_id=session_id, content="你在吗",
        timestamp=0.0, channel_type="ws", character_id=None,
    )
    await core.handle_message(m2, "sk-test", channel)

    # 第二轮 LLM 收到的 messages：历史里 你好/好 各一次，本轮 你在吗 一次，无重复
    user_msgs = [m for m in llm.messages if m["role"] == "user"]
    contents = [m["content"] for m in user_msgs]
    assert contents.count("你在吗") == 1, f"本轮消息重复: {contents}"


@pytest.mark.anyio
async def test_extraction_serialized_per_character():
    """同角色的记忆抽取应串行化：两条消息的 add 从未并发执行。"""
    cid = await _create_character("小明", "测试")
    mem = ConcurrencyTrackingMemory()
    core = ChatCoreService(FakeLLM(["好"]), mem)
    channel = FakeChannel()

    # 同一角色连发两条消息，各自触发一次 fire-and-forget 抽取
    await core.handle_message(_msg(cid), "sk-test", channel)
    await core.handle_message(_msg(cid), "sk-test", channel)

    # 等抽取任务全部跑完
    await asyncio.gather(*list(core._extract_tasks))

    assert len(mem.added) == 2
    assert mem.max_active == 1, f"抽取发生了并发，max_active={mem.max_active}"
