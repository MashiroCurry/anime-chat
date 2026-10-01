"""characters table

Revision ID: 0002_character
Revises: 0001_initial
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_character"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("avatar_url", sa.String(1024), nullable=True),
        sa.Column("card", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("live2d", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="private"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_characters_owner_id", "characters", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_characters_owner_id", table_name="characters")
    op.drop_table("characters")
