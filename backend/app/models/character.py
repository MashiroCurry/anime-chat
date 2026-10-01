"""角色模型。card 存完整角色卡（JSONB），persona/examples/greeting/llm/memory。"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# 单用户模式：无鉴权，所有角色挂在这个固定 owner 下（M1a 决定）
DEFAULT_OWNER_ID = "local"


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String(64), index=True, default=DEFAULT_OWNER_ID
    )
    name: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # 完整角色卡：persona / examples / greeting / llm / memory
    # PostgreSQL 用 JSONB，SQLite（测试）回退到 JSON
    card: Mapped[dict] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
