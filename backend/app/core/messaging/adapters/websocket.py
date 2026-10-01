"""WebSocket 渠道适配器。

接收 WS 帧（auth / chat / ping）→ 转 UnifiedMessage → 交给 ChatCoreService；
把核心层的 send_delta/send_done/send_error 映射成 WS 帧。
BYOK 密钥只在连接内存持有，绝不落盘、不进日志。
"""

import time

from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.logging import redact
from app.core.messaging.channel import MessageCallback
from app.core.messaging.types import UnifiedMessage
from app.models.character import DEFAULT_OWNER_ID
from app.schemas.frames import (
    AuthFrame,
    ChatFrame,
    DeltaFrame,
    DoneFrame,
    ErrorFrame,
    PingFrame,
    client_frame_adapter,
)


class WebSocketAdapter:
    """WS 适配器：一个连接对应一个实例。"""

    def __init__(self, ws: WebSocket, core) -> None:
        self._ws = ws
        self._core = core
        self._api_key: str | None = None
        self._on_message: MessageCallback | None = None

    # ---- MessageChannel 接口 ----

    def on_message(self, callback: MessageCallback) -> None:
        """注册收消息回调（WS 场景由 run() 主动轮询，回调仅供接口统一）。"""
        self._on_message = callback

    async def send_delta(self, user_id: str, text: str) -> None:
        await self._ws.send_text(DeltaFrame(text=text).model_dump_json())

    async def send_done(self, user_id: str, message_id: str, session_id: str) -> None:
        await self._ws.send_text(
            DoneFrame(message_id=message_id, conversation_id=session_id).model_dump_json()
        )

    async def send_error(self, user_id: str, code: str, message: str) -> None:
        await self._ws.send_text(
            ErrorFrame(code=code, message=redact(message)).model_dump_json()
        )

    # ---- WS 处理循环 ----

    async def run(self) -> None:
        """循环接收帧，处理 auth / chat / ping。"""
        settings = get_settings()
        try:
            while True:
                raw = await self._ws.receive_text()

                try:
                    frame = client_frame_adapter.validate_json(raw)
                except ValidationError as e:
                    await self.send_error("", "bad_frame", f"无法解析帧：{redact(str(e))}")
                    continue

                if isinstance(frame, AuthFrame):
                    self._api_key = frame.api_key or settings.llm_api_key
                    if not self._api_key:
                        await self.send_error("", "no_api_key", "未提供 API key")
                        await self._ws.close(code=1008)
                        return
                    logger.info("ws 连接已认证")  # 不回显任何密钥信息

                elif isinstance(frame, PingFrame):
                    await self._ws.send_text('{"type":"pong"}')

                elif isinstance(frame, ChatFrame):
                    if self._api_key is None:
                        await self.send_error("", "unauthorized", "请先发送 auth 帧")
                        continue
                    unified = UnifiedMessage(
                        user_id=DEFAULT_OWNER_ID,
                        session_id=frame.conversation_id,
                        content=frame.message,
                        timestamp=time.time(),
                        channel_type="ws",
                        character_id=frame.character_id,
                    )
                    await self._core.handle_message(unified, self._api_key, self)

                else:
                    await self.send_error("", "unknown_type", "未知帧类型")

        except WebSocketDisconnect:
            logger.info("ws 连接断开")
        finally:
            # 连接结束即丢弃内存中的密钥，不留痕迹
            self._api_key = None
