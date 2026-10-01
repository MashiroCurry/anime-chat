"""drop live2d column（放弃 Live2D 渲染）

Revision ID: 0003_drop_live2d
Revises: 0002_character
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003_drop_live2d"
down_revision: Union[str, None] = "0002_character"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("characters", "live2d")


def downgrade() -> None:
    op.add_column("characters", sa.Column("live2d", postgresql.JSONB(), nullable=True))
