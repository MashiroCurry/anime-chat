// 会话历史 REST 客户端：按角色取回长期会话与最近消息（刷新后恢复聊天记录）。
// 服务端 TS 同构类型见 backend/app/schemas/conversation.py。

export interface HistoryMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string | null
}

export interface ConversationHistory {
  conversation_id: string | null
  messages: HistoryMessage[]
}

const BASE = '/api/v1/conversations'

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!r.ok) {
    const detail = await r.text().catch(() => '')
    throw new Error(`请求失败 ${r.status}: ${detail}`)
  }
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

export const conversationsApi = {
  // characterId 为空表示「无角色的默认会话」，此时不带查询参数
  history: (characterId: string | null, limit = 200) =>
    req<ConversationHistory>(
      characterId
        ? `${BASE}/messages?character_id=${encodeURIComponent(characterId)}&limit=${limit}`
        : `${BASE}/messages?limit=${limit}`,
    ),
  // 清空某角色的聊天记录（只删会话/消息，不碰记忆）。返回 204 → undefined
  clear: (characterId: string | null) =>
    req<void>(
      characterId
        ? `${BASE}/messages?character_id=${encodeURIComponent(characterId)}`
        : `${BASE}/messages`,
      { method: 'DELETE' },
    ),
}
