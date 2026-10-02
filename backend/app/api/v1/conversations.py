"""会话历史 REST API：取某角色的长期会话与最近消息。

前端刷新/换设备后靠这个接口恢复聊天记录。一个角色一条会话，
查询条件就是 conversations.character_id（有索引）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Conversation, Message
from app.schemas.conversation import ConversationMessages, MessageOut

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _to_out(m: Message) -> MessageOut:
    return MessageOut(
        id=m.id,
        role=m.role,
        content=m.content,
        created_at=m.created_at.isoformat() if m.created_at else None,
    )


@router.get("/messages", response_model=ConversationMessages)
async def get_conversation_messages(
    character_id: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> ConversationMessages:
    """取某角色会话的最近 limit 条消息（时间正序）。

    没有会话时返回空态而非 404 —— 没聊过是正常态。
    limit 上限 500：CLAUDE.md 禁止一次性渲染全部聊天记录。
    """
    # 省略 character_id 或传空串都表示「无角色的默认会话」
    if not character_id:
        character_id = None

    cond = (
        Conversation.character_id.is_(None)
        if character_id is None
        else Conversation.character_id == character_id
    )
    conversation = await session.scalar(
        select(Conversation)
        .where(cond)
        .order_by(Conversation.created_at.asc())
        .limit(1)
    )
    if conversation is None:
        return ConversationMessages()

    # 先倒序取最近 limit 条，再翻正 —— 与 core.py 拉上下文历史的写法一致
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    rows = (await session.scalars(stmt)).all()

    return ConversationMessages(
        conversation_id=conversation.id,
        messages=[_to_out(m) for m in reversed(rows)],
    )
