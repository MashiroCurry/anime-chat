"""mem0 自托管实现：AsyncMemory + pgvector。

实现 base.MemoryService 的 async 接口。character_id 为空时直接跳过（不落
default 桶，避免串记忆）——见 M1b 计划反馈 #3。
"""

from mem0 import AsyncMemory
from mem0.configs.base import MemoryConfig

from app.core.config import Settings
from app.services.memory.base import Memory


def _build_mem0_config(settings: Settings) -> dict:
    """构建 mem0 config。

    字段名（openai_base_url / embedding_dims / collection_name）随 mem0 版本变过，
    升级 mem0 时只改这一个函数。当前锁定 mem0ai==2.2.1。
    """
    embedder_config: dict = {
        "model": settings.embedding_model,
        "api_key": settings.embedding_api_key,
        # 注意：不设 embedding_dims——SiliconFlow 的 bge-m3 不接受 dimensions 参数
        # （mem0 会把 embedding_dims 作为 dimensions 传给 API，导致 400）。
        # 维度只用于 pgvector 建表，见下方 embedding_model_dims。
    }
    if settings.embedding_provider == "ollama":
        embedder_config["ollama_base_url"] = settings.embedding_base_url
    else:
        # OpenAI 兼容端点（SiliconFlow / vLLM / LM Studio 等）
        embedder_config["openai_base_url"] = settings.embedding_base_url

    # psycopg 不认 SQLAlchemy 的 +asyncpg 后缀，转成标准 postgresql://
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")

    return {
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.llm_model,
                "api_key": settings.llm_api_key,
                "openai_base_url": settings.llm_base_url,
                "temperature": 0.1,
            },
        },
        "embedder": {
            "provider": settings.embedding_provider,
            "config": embedder_config,
        },
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": dsn,
                "collection_name": settings.memory_table,
                # pgvector 建表需要向量维度（embedder 不传 dims 给 API，这里单独给建表用）
                "embedding_model_dims": settings.embedding_dims,
            },
        },
        # 抽取语言等指令（注入 mem0 的抽取 prompt）
        "custom_instructions": settings.memory_custom_instructions,
    }


def _to_memory(result: dict) -> Memory:
    """把 mem0 返回的单条 dict 转成 base.Memory。"""
    return Memory(
        memory_id=result.get("id", ""),
        content=result.get("memory", "") or result.get("text", ""),
        score=result.get("score"),
    )


def _to_memory_list(results) -> list[Memory]:
    """兼容 search/get_all 的两种返回形态：dict{"results": [...]} 或 list。"""
    if isinstance(results, dict):
        results = results.get("results", [])
    if not results:
        return []
    return [_to_memory(r) for r in results]


class Mem0MemoryService:
    """mem0 实现。单例复用，勿每请求新建（初始化建连接）。"""

    def __init__(self, settings: Settings) -> None:
        config = MemoryConfig.model_validate(_build_mem0_config(settings))
        self._memory = AsyncMemory(config=config)

    async def add(
        self, messages: list[dict], *, user_id: str, character_id: str | None = None
    ) -> None:
        if not character_id:
            return  # 不落 default 桶
        await self._memory.add(
            messages,
            user_id=user_id,
            agent_id=character_id,
        )

    async def search(
        self, query: str, *, user_id: str, character_id: str | None = None, top_k: int = 8
    ) -> list[Memory]:
        if not character_id:
            return []
        results = await self._memory.search(
            query,
            filters={"user_id": user_id, "agent_id": character_id},
            top_k=top_k,
        )
        return _to_memory_list(results)

    async def list(
        self, *, user_id: str, character_id: str | None = None
    ) -> list[Memory]:
        if not character_id:
            return []
        results = await self._memory.get_all(
            filters={"user_id": user_id, "agent_id": character_id},
        )
        return _to_memory_list(results)

    async def delete(self, memory_id: str, *, user_id: str) -> None:
        await self._memory.delete(memory_id)

    async def reset(self) -> None:
        """清空全部记忆：vector store collection + history.db 一起清。"""
        await self._memory.reset()
