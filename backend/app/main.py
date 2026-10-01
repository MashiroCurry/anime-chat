"""FastAPI 入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app.api.v1 import characters, health, memories, ws
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.messaging.identity import SingleUserIdentityService
from app.services.chat import ChatCoreService
from app.services.llm import get_llm_provider
from app.services.memory import Mem0MemoryService, NoopMemoryService


def _create_memory_service(settings: Settings):
    """创建记忆服务单例。配置不全或初始化失败时降级 Noop，不阻塞聊天（反馈 #6）。"""
    if not settings.embedding_api_key:
        logger.warning("embedding_api_key 未配置，记忆功能降级为 Noop（聊天不受影响）")
        return NoopMemoryService()
    try:
        return Mem0MemoryService(settings)
    except Exception as e:  # noqa: BLE001 初始化失败必须降级
        logger.warning("mem0 初始化失败，降级为 Noop：{}", e)
        return NoopMemoryService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    app.state.memory = _create_memory_service(settings)
    # 身份映射服务单例：外部渠道 ID → 内部用户 ID（当前单用户，未来换 DB 实现）
    app.state.identity = SingleUserIdentityService()
    # 核心对话服务单例：LLM + 记忆，与消息渠道解耦
    app.state.core = ChatCoreService(get_llm_provider(), app.state.memory)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(ws.router, prefix="/api/v1")
    app.include_router(characters.router, prefix="/api/v1")
    app.include_router(memories.router, prefix="/api/v1")
    return app


app = create_app()
