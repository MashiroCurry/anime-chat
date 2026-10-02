"""会话历史 Schema。前端 TS 侧维护同构类型（src/api/conversations.ts）。

created_at 用 str 并由路由手工 isoformat，与 CharacterOut 的处理保持一致
（见 api/v1/characters.py 的 _to_out），不用 from_attributes。
"""

from pydantic import BaseModel, Field


class MessageOut(BaseModel):
    id: str
    role: str  # user / assistant / system
    content: str
    created_at: str | None = None


class ConversationMessages(BaseModel):
    """某角色的长期会话 + 最近消息。无会话时 conversation_id 为 None（空态）。"""

    conversation_id: str | None = None
    messages: list[MessageOut] = Field(default_factory=list)
