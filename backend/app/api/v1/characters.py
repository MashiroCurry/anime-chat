"""角色管理 REST API：CRUD + 导入 Character Card。"""

import base64

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.character import DEFAULT_OWNER_ID, Character
from app.schemas.character import CharacterCard, CharacterCreate, CharacterOut, CharacterUpdate
from app.services.character import parse_character_card

router = APIRouter(prefix="/characters", tags=["characters"])


def _to_out(c: Character) -> CharacterOut:
    return CharacterOut(
        id=c.id,
        owner_id=c.owner_id,
        name=c.name,
        avatar_url=c.avatar_url,
        card=CharacterCard.model_validate(c.card),
        visibility=c.visibility,
        created_at=c.created_at.isoformat() if c.created_at else None,
        updated_at=c.updated_at.isoformat() if c.updated_at else None,
    )


@router.get("", response_model=list[CharacterOut])
async def list_characters(session: AsyncSession = Depends(get_session)) -> list[CharacterOut]:
    stmt = (
        select(Character)
        .where(Character.owner_id == DEFAULT_OWNER_ID)
        .order_by(Character.created_at)
    )
    rows = (await session.scalars(stmt)).all()
    return [_to_out(c) for c in rows]


@router.post("", response_model=CharacterOut, status_code=201)
async def create_character(
    payload: CharacterCreate, session: AsyncSession = Depends(get_session)
) -> CharacterOut:
    character = Character(name=payload.name, card=payload.card.model_dump())
    session.add(character)
    await session.commit()
    await session.refresh(character)
    return _to_out(character)


@router.get("/{character_id}", response_model=CharacterOut)
async def get_character(
    character_id: str, session: AsyncSession = Depends(get_session)
) -> CharacterOut:
    character = await session.get(Character, character_id)
    if character is None or character.owner_id != DEFAULT_OWNER_ID:
        raise HTTPException(status_code=404, detail="角色不存在")
    return _to_out(character)


@router.put("/{character_id}", response_model=CharacterOut)
async def update_character(
    character_id: str,
    payload: CharacterUpdate,
    session: AsyncSession = Depends(get_session),
) -> CharacterOut:
    character = await session.get(Character, character_id)
    if character is None or character.owner_id != DEFAULT_OWNER_ID:
        raise HTTPException(status_code=404, detail="角色不存在")
    if payload.name is not None:
        character.name = payload.name
    if payload.card is not None:
        character.card = payload.card.model_dump()
    await session.commit()
    await session.refresh(character)
    return _to_out(character)


@router.delete("/{character_id}", status_code=204)
async def delete_character(
    character_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    character = await session.get(Character, character_id)
    if character is None or character.owner_id != DEFAULT_OWNER_ID:
        raise HTTPException(status_code=404, detail="角色不存在")
    await session.delete(character)
    await session.commit()


class CharacterImport(BaseModel):
    """导入体：文件内容（JSON 文本或 PNG 二进制）的 base64。"""

    content_base64: str


@router.post("/import", response_model=CharacterOut, status_code=201)
async def import_character(
    payload: CharacterImport, session: AsyncSession = Depends(get_session)
) -> CharacterOut:
    try:
        content = base64.b64decode(payload.content_base64)
        name, card = parse_character_card(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    character = Character(name=name, card=card.model_dump())
    session.add(character)
    await session.commit()
    await session.refresh(character)
    return _to_out(character)
