// 端到端截图脚本：验证「填密钥 → WS 流式对话 → 渲染」完整链路。
// 用法：COMPANION_API_KEY=sk-xxx BASE_URL=http://localhost:5173 node e2e/screenshot.mjs
// 密钥绝不硬编码、绝不打印到输出。

import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const KEY = process.env.COMPANION_API_KEY ?? ''
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5173'
const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(__dirname, '../../screenshots')

if (!KEY) {
  console.error('请设置环境变量 COMPANION_API_KEY')
  process.exit(1)
}

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 420, height: 820 } })
await page.goto(BASE_URL, { waitUntil: 'networkidle' })

await page.screenshot({ path: `${OUT}/01-initial.png` })

await page.click('button[aria-label="设置"]')
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/02-settings.png` })

await page.fill('input.key-input', KEY)
await page.click('.btn-primary')
await page.waitForTimeout(800)

await page.fill('.chat-input textarea', '用一句话介绍你自己')
await page.click('.chat-input .n-button')
await page.waitForTimeout(1800)
await page.screenshot({ path: `${OUT}/03-streaming.png` })

await page.waitForTimeout(9000)
await page.screenshot({ path: `${OUT}/04-done.png` })

const msgs = await page.$$eval('.bubble-row', (els) => els.map((e) => e.textContent.trim()))
console.log('=== 消息列表 ===')
msgs.forEach((m, i) => console.log(`[${i}] ${m}`))

await browser.close()
console.log(`=== 截图完成: ${OUT}`)
