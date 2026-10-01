// 聊天状态与流式渲染。
//
// 性能硬约束（CLAUDE.md）：
// - 禁止逐 token 触发重渲染 → token 先写普通缓冲区，requestAnimationFrame 批量 flush
// - 禁止大型对象进深度响应式 → 消息数组用 shallowRef，消息对象不被深度代理
import { ref, shallowRef } from 'vue'

import { ChatSocket } from '../api/ws'
import type { ServerFrame } from '../api/frames'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}

const KEY_STORAGE = 'companion.api_key'

function readStoredKey(): string {
  return localStorage.getItem(KEY_STORAGE) ?? ''
}

let seq = 0
function nextId(): string {
  return `m${Date.now()}_${seq++}`
}

export function useChat() {
  // shallowRef：数组引用是响应式的，内部消息对象不深度代理
  const messages = shallowRef<ChatMessage[]>([])
  const apiKey = ref(readStoredKey())
  const characterId = ref<string | null>(null)
  const connected = ref(false)
  const streaming = ref(false)
  const lastError = ref('')

  let socket: ChatSocket | null = null
  let conversationId: string | null = null
  let activeAssistant: ChatMessage | null = null
  let pendingText = '' // 非响应式缓冲区
  let rafId: number | null = null

  function flush(): void {
    if (!activeAssistant) return
    // 不可变更新：创建新对象替换数组中的旧对象。
    // shallowRef 只跟踪 .value 引用，原地改对象属性不会触发 MessageBubble 重渲染。
    const updated: ChatMessage = {
      ...activeAssistant,
      content: activeAssistant.content + pendingText,
      streaming: streaming.value,
    }
    pendingText = ''
    messages.value = messages.value.map((m) => (m.id === updated.id ? updated : m))
    activeAssistant = updated
  }

  function scheduleFlush(): void {
    if (rafId !== null) return
    rafId = requestAnimationFrame(() => {
      rafId = null
      flush()
    })
  }

  function onFrame(frame: ServerFrame): void {
    switch (frame.type) {
      case 'delta':
        pendingText += frame.text
        scheduleFlush()
        break
      case 'done':
        streaming.value = false
        flush()
        conversationId = frame.conversation_id
        break
      case 'error':
        streaming.value = false
        flush()
        lastError.value = frame.message
        break
    }
  }

  function connect(): void {
    if (!apiKey.value) return
    socket?.close()
    socket = new ChatSocket(apiKey.value, onFrame)
    socket.connect()
    connected.value = true
  }

  function disconnect(): void {
    socket?.close()
    socket = null
    connected.value = false
  }

  function send(text: string): void {
    const content = text.trim()
    if (!content || !apiKey.value) return

    if (!socket) connect()
    if (!socket) return

    const assistant: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: '',
      streaming: true,
    }
    messages.value = [
      ...messages.value,
      { id: nextId(), role: 'user', content },
      assistant,
    ]
    activeAssistant = assistant
    pendingText = ''
    lastError.value = ''
    streaming.value = true

    socket.send({
      type: 'chat',
      message: content,
      conversation_id: conversationId,
      character_id: characterId.value,
    })
  }

  function setCharacterId(id: string | null): void {
    characterId.value = id
    // 切换角色后清空当前会话，避免不同角色混在一个上下文
    conversationId = null
    messages.value = []
  }

  function setApiKey(key: string): void {
    apiKey.value = key
    if (key) {
      localStorage.setItem(KEY_STORAGE, key)
    } else {
      localStorage.removeItem(KEY_STORAGE)
    }
    // 密钥变更后重连
    disconnect()
    if (key) connect()
  }

  return {
    messages,
    apiKey,
    characterId,
    connected,
    streaming,
    lastError,
    connect,
    disconnect,
    send,
    setApiKey,
    setCharacterId,
  }
}
