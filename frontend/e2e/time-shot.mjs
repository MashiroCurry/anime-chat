// 时间感知验证：前端页面问「现在几点」，截图并打印模型回答。
// 用法：COMPANION_API_KEY=sk-xxx node e2e/time-shot.mjs
// 密钥绝不硬编码、绝不打印。

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

const CHROME = process.env.PLAYWRIGHT_CHROMIUM_PATH
const browser = await chromium.launch(CHROME ? { executablePath: CHROME } : {})
const page = await browser.newPage({ viewport: { width: 720, height: 900 } })
await page.goto(BASE_URL, { waitUntil: 'networkidle' })

// 设置密钥
await page.click('button[aria-label="设置"]')
await page.waitForTimeout(400)
await page.fill('input.key-input', KEY)
await page.click('.btn-primary')
await page.waitForTimeout(600)

// 问时间
await page.fill('.chat-input textarea', '现在几点？')
await page.click('.chat-input .n-button')

// 等流式结束（输入框恢复可用）
await page.waitForFunction(
  () => {
    const ta = document.querySelector('.chat-input textarea')
    return ta && !ta.disabled
  },
  { timeout: 60000 },
)
await page.waitForTimeout(500)

await page.screenshot({ path: `${OUT}/time-verify.png`, fullPage: false })

const bubbles = await page.$$eval('.bubble-row', (els) => els.map((e) => e.textContent.trim()))
console.log('=== 气泡内容 ===')
for (const b of bubbles) console.log(b)

await browser.close()
