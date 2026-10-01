"""角色卡 Schema。card 的内部结构见 CharacterCard，整体存 JSONB。

前端 TS 侧维护同构类型（src/types/character.ts）。
"""

from pydantic import BaseModel, Field


class Persona(BaseModel):
    identity: str = ""
    personality: str = ""
    speaking_style: str = ""
    worldview: str = ""
    relationship: str = ""


class Example(BaseModel):
    user: str
    assistant: str


class LLMConfig(BaseModel):
    model: str = "deepseek-chat"
    temperature: float = 0.8


class MemoryConfig(BaseModel):
    enabled: bool = True
    top_k: int = 8


class CharacterCard(BaseModel):
    """完整角色卡内容。空字段用空字符串，build_system_prompt 时省略。"""

    persona: Persona = Field(default_factory=Persona)
    examples: list[Example] = Field(default_factory=list)
    greeting: str = ""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)


class CharacterCreate(BaseModel):
    name: str
    card: CharacterCard = Field(default_factory=CharacterCard)


class CharacterUpdate(BaseModel):
    name: str | None = None
    card: CharacterCard | None = None


class CharacterOut(BaseModel):
    id: str
    owner_id: str
    name: str
    avatar_url: str | None = None
    card: CharacterCard
    visibility: str
    created_at: str | None = None
    updated_at: str | None = None

    model_config = {"from_attributes": True}
