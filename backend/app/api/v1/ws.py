"""WebSocket 对话端点（薄层）：把连接交给 WebSocketAdapter。

核心对话逻辑在 ChatCoreService，WS 收发在 WebSocketAdapter，本文件只做接线。
"""

from fastapi import APIRouter, WebSocket

from app.core.messaging.adapters import WebSocketAdapter

router = APIRouter(tags=["chat"])


@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket) -> None:
    await ws.accept()
    core = ws.app.state.core
    adapter = WebSocketAdapter(ws, core)
    await adapter.run()
