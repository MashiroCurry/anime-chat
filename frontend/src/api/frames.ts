// WebSocket 帧协议 —— 与后端 app/schemas/frames.py 同构，两侧共用一个契约。
// 方向：ClientFrame 客户端→服务端；ServerFrame 服务端→客户端。

// ---- 客户端 → 服务端 ----

export interface AuthFrame {
  type: 'auth'
  api_key: string
}

export interface ChatFrame {
  type: 'chat'
  conversation_id?: string | null
  character_id?: string | null
  message: string
}

export interface PingFrame {
  type: 'ping'
}

export type ClientFrame = AuthFrame | ChatFrame | PingFrame

// ---- 服务端 → 客户端 ----

export interface DeltaFrame {
  type: 'delta'
  text: string
}

export interface DoneFrame {
  type: 'done'
  message_id: string
  conversation_id: string
  usage?: Record<string, unknown> | null
}

export interface ErrorFrame {
  type: 'error'
  code: string
  message: string
}

export type ServerFrame = DeltaFrame | DoneFrame | ErrorFrame
