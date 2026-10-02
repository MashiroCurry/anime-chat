// WebSocket 客户端封装：连 /api/v1/ws/chat，首帧发 auth（BYOK 密钥）。

import type { ClientFrame, ServerFrame } from './frames'

type Handler = (frame: ServerFrame) => void

type StatusHandler = (open: boolean) => void

export class ChatSocket {
  private ws: WebSocket | null = null
  private apiKey: string
  private onFrame: Handler
  private onStatus?: StatusHandler
  // 握手完成前不丢帧：先入队，onopen 时 auth 优先发出，再 flush
  private ready = false
  private queue: ClientFrame[] = []

  constructor(apiKey: string, onFrame: Handler, onStatus?: StatusHandler) {
    this.apiKey = apiKey
    this.onFrame = onFrame
    this.onStatus = onStatus
  }

  /** 连接：成功后先发 auth 帧（必须最先），再补发排队中的帧。 */
  connect(): void {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${proto}://${location.host}/api/v1/ws/chat`

    this.ws = new WebSocket(url)
    this.ws.onopen = () => {
      this.ready = true
      // 密钥只经 WS 帧传递，不进 URL query；服务端要求 auth 必须是第一帧
      this.ws?.send(JSON.stringify({ type: 'auth', api_key: this.apiKey }))
      for (const f of this.queue) this.ws?.send(JSON.stringify(f))
      this.queue = []
      this.onStatus?.(true)
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
      this.ready = false
      this.queue = []
      this.onStatus?.(false)
      this.onFrame({ type: 'error', code: 'closed', message: '连接已断开' })
    }
    this.ws.onerror = () => {
      this.onFrame({ type: 'error', code: 'ws_error', message: '连接出错' })
    }
  }

  send(frame: ClientFrame): void {
    if (this.ready && this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(frame))
      return
    }
    // 尚未 OPEN 时排队而不是静默丢弃
    this.queue.push(frame)
  }

  close(): void {
    this.ready = false
    this.queue = []
    this.ws?.close()
    this.ws = null
  }
}
