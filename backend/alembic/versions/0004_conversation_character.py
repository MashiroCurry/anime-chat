"""conversations.character_id（一个角色一条长期会话）

Revision ID: 0004_conversation_character
Revises: 0003_drop_live2d
Create Date: 2026-10-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_conversation_character"
down_revision: Union[str, None] = "0003_drop_live2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "conversations", sa.Column("character_id", sa.String(36), nullable=True)
    )
    op.create_index("ix_conversations_character_id", "conversations", ["character_id"])

    # 旧会话的 character_id 全是 NULL，会被「无角色默认会话」误接上；
    # messages 走 ON DELETE CASCADE，一并清掉。当前库里仅有调试数据。
    op.execute("DELETE FROM conversations")


def downgrade() -> None:
    op.drop_index("ix_conversations_character_id", table_name="conversations")
    op.drop_column("conversations", "character_id")
