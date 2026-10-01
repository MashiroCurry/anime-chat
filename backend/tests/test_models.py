"""模型层往返测试：会话 + 消息落库，以及「消息模型不含任何密钥字段」。"""

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models import Conversation, Message


async def test_message_roundtrip():
    async with async_session_factory() as s:
        conv = Conversation()
        s.add(conv)
        await s.flush()

        s.add(Message(conversation_id=conv.id, role="user", content="hello"))
        s.add(Message(conversation_id=conv.id, role="assistant", content="hi there"))
        await s.commit()

    async with async_session_factory() as s:
        rows = (await s.scalars(select(Message).order_by(Message.created_at))).all()
        assert [m.content for m in rows] == ["hello", "hi there"]
        assert all(m.conversation_id == conv.id for m in rows)


async def test_message_schema_has_no_api_key_column():
    """BYOK 硬保证：消息表没有任何密钥字段，密钥不可能落库。"""
    cols = {c.name for c in Message.__table__.columns}
    assert "api_key" not in cols
    assert "key" not in cols
