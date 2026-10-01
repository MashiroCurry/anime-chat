// 角色 REST 客户端。

import type { Character, CharacterCard } from '../types/character'

const BASE = '/api/v1/characters'

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

export const charactersApi = {
  list: () => req<Character[]>(BASE),

  create: (name: string, card: CharacterCard) =>
    req<Character>(BASE, { method: 'POST', body: JSON.stringify({ name, card }) }),

  update: (id: string, data: { name?: string; card?: CharacterCard }) =>
    req<Character>(`${BASE}/${id}`, { method: 'PUT', body: JSON.stringify(data) }),

  remove: (id: string) => req<void>(`${BASE}/${id}`, { method: 'DELETE' }),

  import: (contentBase64: string) =>
    req<Character>(`${BASE}/import`, {
      method: 'POST',
      body: JSON.stringify({ content_base64: contentBase64 }),
    }),
}
