"""微信渠道适配器（预留骨架，不实现具体协议）。

未来接入微信时，在这里实现 MessageChannel 接口 + webhook 处理。
关键前置设计已预留：
- verifySignature()：微信签名校验
- MediaId 转文本的降级路径（语音/图片消息）
- 身份映射（OpenID → internalUserId，经 IdentityService）
- ChannelException（48h 客服窗口限制、5s 被动回复超时）
"""

import hashlib

from app.core.messaging.channel import MessageCallback
from app.core.messaging.exceptions import (
    ChannelException,
    CODE_MEDIA_CONVERT_FAILED,
    CODE_WECHAT_48H_LIMIT,
    CODE_WECHAT_TIMEOUT,
)
from app.core.messaging.identity import IdentityService
from app.core.messaging.types import UnifiedMessage


class WeChatAdapter:
    """微信适配器骨架。核心层（ChatCoreService）完全不用改，接入时填这里 + 注册 webhook。"""

    def __init__(self, identity: IdentityService) -> None:
        self._identity = identity
        self._on_message: MessageCallback | None = None
        # 累积流式 delta：微信不适合逐字推，send_done 时一次性发完整消息
        self._pending_deltas: dict[str, list[str]] = {}

    # ---- MessageChannel 接口 ----

    def on_message(self, callback: MessageCallback) -> None:
        """注册核心层消息处理回调。webhook 收到消息、完成身份映射后调用。"""
        self._on_message = callback

    async def send_delta(self, user_id: str, text: str) -> None:
        """累积增量，不直接发送（微信被动回复限 5 秒，逐字推会超时）。"""
        self._pending_deltas.setdefault(user_id, []).append(text)

    async def send_done(self, user_id: str, message_id: str, session_id: str) -> None:
        """累积完成，一次性推送完整回复。"""
        content = "".join(self._pending_deltas.pop(user_id, []))
        # 未来：检查 48h 客服窗口，超时抛 ChannelException
        # if not _within_48h(user_id):
        #     raise ChannelException(CODE_WECHAT_48H_LIMIT, "已超过 48 小时客服消息窗口", retryable=False)
        # 未来：调用微信 API 主动推送 content
        raise NotImplementedError("微信适配器尚未实现：send_done 需调微信 API 推送")

    async def send_error(self, user_id: str, code: str, message: str) -> None:
        raise NotImplementedError("微信适配器尚未实现：send_error")

    # ---- 微信签名校验（预留）----

    def verify_signature(self, signature: str, timestamp: str, nonce: str, token: str) -> bool:
        """微信服务器签名校验：sha1(sort([token, timestamp, nonce])) == signature。

        用于验证 webhook 请求确实来自微信服务器。token 从 config 的 wechat_token 读取。
        """
        parts = sorted([token, timestamp, nonce])
        sha1 = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()
        return sha1 == signature

    # ---- webhook 处理（预留，未来实现）----

    # async def handle_webhook(self, body: bytes, signature: str, timestamp: str, nonce: str):
    #     """微信回调入口：校验签名 → 解析 XML → 身份映射 → 交给核心层。"""
    #     # 1. 校验签名（token 从 config 读）
    #     if not self.verify_signature(signature, timestamp, nonce, token):
    #         return "invalid signature"
    #
    #     # 2. 解析 XML 得到 MsgType + FromUserName(OpenID) + Content/MediaId
    #     msg = self._parse_xml(body)
    #
    #     # 3. 语音/图片消息：MediaId 转文本（降级）
    #     content = await self._content_from_message(msg)
    #     if content is None:
    #         # 降级：无法转文本时，回一条「请发文字消息」给用户
    #         raise ChannelException(CODE_MEDIA_CONVERT_FAILED, "语音/图片暂不支持，请发文字", retryable=False)
    #
    #     # 4. 身份映射：OpenID → internalUserId（核心层只认 internalUserId）
    #     internal_id = await self._identity.resolve("wechat", msg["FromUserName"])
    #
    #     # 5. 构造 UnifiedMessage，交给核心层（注意 5 秒被动回复超时 → 转主动推送）
    #     unified = UnifiedMessage(
    #         user_id=internal_id,
    #         session_id=None,
    #         content=content,
    #         timestamp=time.time(),
    #         channel_type="wechat",
    #         character_id=None,  # 未来从会话/绑定关系解析
    #     )
    #     if self._on_message:
    #         await self._on_message(unified)
    #
    # async def _content_from_message(self, msg: dict) -> str | None:
    #     """把微信消息转文本。语音（MediaId）需下载 + ASR；图片需 OCR。"""
    #     if msg["MsgType"] == "text":
    #         return msg["Content"]
    #     if msg["MsgType"] == "voice":
    #         # 未来：调 media 下载接口拿音频 → ASR 转文本（如 FunASR）
    #         # 失败/未接入时返回 None → 触发降级提示
    #         return None
    #     return None

    # ---- 微信 5 秒被动回复超时说明 ----
    # 微信要求被动回复必须在收到消息 5 秒内返回，否则连接断开。
    # 本项目是 LLM 流式生成（>5 秒），所以架构上必须：
    #   1. 收到消息后立即回「收到」占位（或空回复），让微信不超时
    #   2. LLM 生成完成后，通过客服消息接口「主动推送」完整回复
    # 核心层通过 on_reply 回调把完整结果抛给本 Adapter，由这里做主动推送。
    # 若主动推送时发现超过 48h 客服窗口，抛 ChannelException(CODE_WECHAT_48H_LIMIT)，
    # 核心层识别后降级（记录日志，不崩溃，结果由用户下次主动触发时被动回复）。
