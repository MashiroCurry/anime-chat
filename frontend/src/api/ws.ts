// WebSocket 客户端封装：连 /api/v1/ws/chat，首帧发 auth（BYOK 密钥）。

import type { ClientFrame, ServerFrame } from './frames'

type Handler = (frame: ServerFrame) => void

export class ChatSocket {
  private ws: WebSocket | null = null
  private apiKey: string
  private onFrame: Handler

  constructor(apiKey: string, onFrame: Handler) {
    this.apiKey = apiKey
    this.onFrame = onFrame
  }

  /** 连接：成功后自动发送 auth 帧（密钥只经 WS 帧传递，不进 URL query）。 */
  connect(): void {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}/api/v1/ws/chat`

    this.ws = new WebSocket(url)
    this.ws.onopen = () => {
      this.send({ type: 'auth', api_key: this.apiKey })
    }
    this.ws.onmessage = (ev) => {
      try {
        const frame = JSON.parse(ev.data) as ServerFrame
        this.onFrame(frame)
      } catch {
        // 忽略无法解析的帧
      }
    }
    this.ws.onclose = () => {
      this.onFrame({ type: 'error', code: 'closed', message: '连接已断开' })
    }
    this.ws.onerror = () => {
      this.onFrame({ type: 'error', code: 'ws_error', message: '连接出错' })
    }
  }

  send(frame: ClientFrame): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frame))
    }
  }

  close(): void {
    this.ws?.close()
    this.ws = null
  }
}
