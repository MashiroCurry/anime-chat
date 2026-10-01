"""WebSocket 帧协议：M0 锁死的核心契约。

方向约定：
- ClientFrame：客户端 → 服务端（auth / chat / ping）
- ServerFrame：服务端 → 客户端（delta / done / error）

用 Pydantic 判别联合（discriminated union），`type` 字段区分具体帧。
前端 TS 侧维护同构类型（阶段 B 落），两侧共用一个契约。

BYOK 关键点：浏览器 WebSocket 无法设自定义请求头，密钥放 URL query 又会被
access log 记录。因此密钥走「连接后第一帧 auth」，服务端仅在连接内存持有。
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


# ---- 客户端 → 服务端 ----


class AuthFrame(BaseModel):
    """连接后第一帧，携带 BYOK 密钥。服务端只在本连接内存持有，不落盘。"""

    type: Literal["auth"] = "auth"
    api_key: str


class ChatFrame(BaseModel):
    """发起一次对话。character_id 指定使用哪个角色卡的人设（M1a）。"""

    type: Literal["chat"] = "chat"
    conversation_id: str | None = None
    character_id: str | None = None
    message: str


class PingFrame(BaseModel):
    type: Literal["ping"] = "ping"


ClientFrame = Annotated[
    Union[AuthFrame, ChatFrame, PingFrame], Field(discriminator="type")
]


# ---- 服务端 → 客户端 ----


class DeltaFrame(BaseModel):
    """流式增量文本。M0 逐 token 下发，前端批量渲染。"""

    type: Literal["delta"] = "delta"
    text: str


class DoneFrame(BaseModel):
    """本轮生成结束。message_id 为落库后的消息 id，usage 为模型上报的用量。"""

    type: Literal["done"] = "done"
    message_id: str
    conversation_id: str
    usage: dict | None = None


class ErrorFrame(BaseModel):
    """错误。code 为机器可读错误码，message 为人类可读描述（已脱敏）。"""

    type: Literal["error"] = "error"
    code: str
    message: str


ServerFrame = Annotated[
    Union[DeltaFrame, DoneFrame, ErrorFrame],
    Field(discriminator="type"),
]

# 运行时解析器：判别联合是字段类型，不能直接 .model_validate_json()，
# 用 TypeAdapter 承载顶层 JSON 的解析。
client_frame_adapter = TypeAdapter(ClientFrame)
server_frame_adapter = TypeAdapter(ServerFrame)

