"""异步数据库引擎与会话。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# SQLite（仅测试）用 NullPool：避免连接跨事件循环复用导致死锁
_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if settings.database_url.startswith("sqlite"):
    _engine_kwargs["poolclass"] = NullPool

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：请求作用域的数据库会话。"""
    async with async_session_factory() as session:
        yield session
