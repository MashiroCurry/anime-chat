"""健康检查：确认服务存活，并探测 DB 连通性。"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict:
    """返回服务状态。DB 探活失败会抛 500，由调用方判断。"""
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
