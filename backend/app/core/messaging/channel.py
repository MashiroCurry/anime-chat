"""MessageChannel 接口：消息收发统一标准（三层架构的接口层）。

每个渠道（WebSocket / 微信 / QQ）都必须实现这个接口。核心层（ChatCoreService）
只依赖这个接口，完全不感知消息来自哪个渠道。

流式设计：对话是逐 token 流的，核心层统一用 send_delta/send_done 输出，
呈现差异由 Adapter 吸收（WS 逐帧推，微信累积后发完整消息）。
"""

from collections.abc import Awaitable, Callable
from typing import Protocol

from app.core.messaging.types import UnifiedMessage

# 收消息回调：Adapter 把外部消息转成 UnifiedMessage 后，调用这个回调推给核心层
MessageCallback = Callable[[UnifiedMessage], Awaitable[None]]


class MessageChannel(Protocol):
    """消息收发接口。每个渠道适配器实现它。"""

    def on_message(self, callback: MessageCallback) -> None:
        """注册收消息回调。Adapter 启动时调用一次，把回调存起来。"""
        ...

    async def send_delta(self, user_id: str, text: str) -> None:
        """流式增量文本。"""
        ...

    async def send_done(self, user_id: str, message_id: str, session_id: str) -> None:
        """本轮生成结束。message_id 为落库后的消息 id，session_id 为会话 id。"""
        ...

    async def send_error(self, user_id: str, code: str, message: str) -> None:
        """错误。message 必须已脱敏。"""
        ...
