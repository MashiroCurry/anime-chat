// 角色卡类型 —— 与后端 app/schemas/character.py 同构。

export interface Persona {
  identity: string
  personality: string
  speaking_style: string
  worldview: string
  relationship: string
}

export interface Example {
  user: string
  assistant: string
}

export interface LLMConfig {
  model: string
  temperature: number
}

export interface MemoryConfig {
  enabled: boolean
  top_k: number
}

export interface CharacterCard {
  persona: Persona
  examples: Example[]
  greeting: string
  llm: LLMConfig
  memory: MemoryConfig
}

export interface Character {
  id: string
  owner_id: string
  name: string
  avatar_url: string | null
  card: CharacterCard
  visibility: string
  created_at: string | null
  updated_at: string | null
}

// 新建空角色卡的默认值
export function emptyCard(): CharacterCard {
  return {
    persona: { identity: '', personality: '', speaking_style: '', worldview: '', relationship: '' },
    examples: [],
    greeting: '',
    llm: { model: 'deepseek-chat', temperature: 0.8 },
    memory: { enabled: true, top_k: 8 },
  }
}
