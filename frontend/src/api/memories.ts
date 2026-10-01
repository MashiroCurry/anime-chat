// 记忆 REST 客户端。

export interface Memory {
  memory_id: string
  content: string
  user_id: string | null
  character_id: string | null
  score: number | null
}

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    const detail = await r.text().catch(() => '')
    throw new Error(`请求失败 ${r.status}: ${detail}`)
  }
  if (r.status === 204) return undefined as T
  return r.json() as Promise<T>
}

export const memoriesApi = {
  list: (characterId: string) =>
    req<Memory[]>(`/api/v1/memories?character_id=${encodeURIComponent(characterId)}`),

  remove: (memoryId: string) =>
    req<void>(`/api/v1/memories/${memoryId}`, { method: 'DELETE' }),

  // 清空全部记忆（vector store + history.db）
  reset: () => req<void>(`/api/v1/memories`, { method: 'DELETE' }),
}
