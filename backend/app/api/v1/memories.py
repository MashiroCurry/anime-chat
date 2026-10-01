"""记忆管理 REST API：查看 / 删除某角色的长期记忆。"""

from fastapi import APIRouter, HTTPException, Request

from app.models.character import DEFAULT_OWNER_ID
from app.services.memory.base import Memory

router = APIRouter(prefix="/memories", tags=["memories"])


@router.get("", response_model=list[Memory])
async def list_memories(request: Request, character_id: str) -> list[Memory]:
    if not character_id:
        raise HTTPException(status_code=400, detail="缺少 character_id")
    memory = request.app.state.memory
    return await memory.list(user_id=DEFAULT_OWNER_ID, character_id=character_id)


@router.delete("/{memory_id}", status_code=204)
async def delete_memory(request: Request, memory_id: str) -> None:
    memory = request.app.state.memory
    await memory.delete(memory_id, user_id=DEFAULT_OWNER_ID)


@router.delete("", status_code=204)
async def reset_memories(request: Request) -> None:
    """清空全部记忆（vector store + history.db）。历史库全局，无法按角色清。"""
    memory = request.app.state.memory
    await memory.reset()
