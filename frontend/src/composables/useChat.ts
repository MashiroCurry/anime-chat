// 聊天状态与流式渲染。
//
// 性能硬约束（CLAUDE.md）：
// - 禁止逐 token 触发重渲染 → token 先写普通缓冲区，requestAnimationFrame 批量 flush
// - 禁止大型对象进深度响应式 → 消息数组用 shallowRef，消息对象不被深度代理
import { ref, shallowRef } from 'vue'

import { conversationsApi } from '../api/conversations'
import { ChatSocket } from '../api/ws'
import type { ServerFrame } from '../api/frames'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}

const KEY_STORAGE = 'companion.api_key'
// 记住选中的角色：刷新后才知道该恢复哪一段对话
const CHAR_STORAGE = 'companion.character_id'

function readStoredKey(): string {
  return localStorage.getItem(KEY_STORAGE) ?? ''
}

function readStoredCharacterId(): string | null {
  return localStorage.getItem(CHAR_STORAGE)
}

let seq = 0
function nextId(): string {
  return `m${Date.now()}_${seq++}`
}

export function useChat() {
  // shallowRef：数组引用是响应式的，内部消息对象不深度代理
  const messages = shallowRef<ChatMessage[]>([])
  const apiKey = ref(readStoredKey())
  const characterId = ref<string | null>(readStoredCharacterId())
  const connected = ref(false)
  const streaming = ref(false)
  const lastError = ref('')

  let socket: ChatSocket | null = null
  let conversationId: string | null = null
  let activeAssistant: ChatMessage | null = null
  let pendingText = '' // 非响应式缓冲区
  let rafId: number | null = null
  let historySeq = 0 // 快速切换角色时丢弃过期的历史响应

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
    // connected 由真实握手结果驱动；并比对实例，避免旧连接的 close 回调
    // 在重连成功后把状态误置为「未连接」
    const next = new ChatSocket(apiKey.value, onFrame, (open) => {
      if (socket === next) connected.value = open
    })
    socket = next
    next.connect()
  }

  function disconnect(): void {
    socket?.close()
    socket = null
    connected.value = false
  }

  /** 拉回该角色的历史消息（刷新/切角色后恢复）。服务端按 character_id 锚定会话。 */
  async function loadHistory(): Promise<void> {
    const seq = ++historySeq
    try {
      const history = await conversationsApi.history(characterId.value)
      if (seq !== historySeq) return // 已切到别的角色，丢弃过期响应
      conversationId = history.conversation_id
      messages.value = history.messages.map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
      }))
    } catch (err) {
      if (seq !== historySeq) return
      lastError.value = (err as Error).message
    }
  }

  function send(text: string): void {
    const content = text.trim()
    if (!content || !apiKey.value) return

    if (!socket) connect()
    if (!socket) return

    historySeq++ // 作废在途的历史拉取，否则它返回时会覆盖刚发出的消息

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
    if (id) {
      localStorage.setItem(CHAR_STORAGE, id)
    } else {
      localStorage.removeItem(CHAR_STORAGE)
    }
    // 切换角色后清空当前会话，避免不同角色混在一个上下文，再拉该角色的历史
    conversationId = null
    messages.value = []
    void loadHistory()
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
    loadHistory,
    send,
    setApiKey,
    setCharacterId,
  }
}
