"""记忆层抽象接缝。

M0 只提供 NoopMemoryService（search 返回空），不接 mem0。
接口必须是 async：M1 接 mem0 时用 AsyncMemory；若在 async 请求路径里
调用同步 Memory，会阻塞整个事件循环（详见技术方案 3.6 节）。
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Memory:
    """一条长期记忆。M0 占位，M1 对齐 mem0 的实际返回结构。"""

    memory_id: str
    content: str
    user_id: str | None = None
    character_id: str | None = None
    score: float | None = None


class MemoryService(Protocol):
    """记忆读写接口。上层调用方不感知底层是 mem0 还是其它实现。"""

    async def add(self, messages: list[dict], *, user_id: str, character_id: str | None = None) -> None:
        """从对话中抽取并写入记忆。写路径由后台 worker 调用，不阻塞请求。"""
        ...

    async def search(
        self, query: str, *, user_id: str, character_id: str | None = None, top_k: int = 8
    ) -> list[Memory]:
        """语义召回相关记忆。请求路径调用，必须非阻塞（async）。"""
        ...

    async def list(self, *, user_id: str, character_id: str | None = None) -> list[Memory]:
        """列出用户可见记忆，供记忆管理面板展示。"""
        ...

    async def delete(self, memory_id: str, *, user_id: str) -> None:
        """删除一条记忆，须同步清理底层存储。"""
        ...

    async def reset(self) -> None:
        """清空全部记忆（vector store + history.db）。历史库是全局的，无法按角色清。"""
        ...


class NoopMemoryService:
    """M0 空实现：不记忆、不召回，接口契约与真实实现一致。"""

    async def add(self, messages: list[dict], *, user_id: str, character_id: str | None = None) -> None:
        return None

    async def search(
        self, query: str, *, user_id: str, character_id: str | None = None, top_k: int = 8
    ) -> list[Memory]:
        return []

    async def list(self, *, user_id: str, character_id: str | None = None) -> list[Memory]:
        return []

    async def delete(self, memory_id: str, *, user_id: str) -> None:
        return None

    async def reset(self) -> None:
        return None
