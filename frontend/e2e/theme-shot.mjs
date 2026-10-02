// 换肤验证截图：浅色主题在 375 / 1440 两档宽度下的主界面、设置抽屉、角色面板与真实对话气泡。
// 用法：COMPANION_API_KEY=sk-xxx BASE_URL=http://localhost:5174 node e2e/theme-shot.mjs
// 密钥绝不硬编码、绝不打印到输出。

import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const KEY = process.env.COMPANION_API_KEY ?? ''
const BASE_URL = process.env.BASE_URL ?? 'http://localhost:5174'
const __dirname = dirname(fileURLToPath(import.meta.url))
const OUT = resolve(__dirname, '../../screenshots')

if (!KEY) {
  console.error('请设置环境变量 COMPANION_API_KEY')
  process.exit(1)
}

mkdirSync(OUT, { recursive: true })

// 本机 ms-playwright 里现成的是 chromium-1223，而 playwright 1.63 默认找 1243。
// 不下载新包（避免改环境），允许用 PLAYWRIGHT_CHROMIUM_PATH 指到已有二进制。
const CHROME = process.env.PLAYWRIGHT_CHROMIUM_PATH
const browser = await chromium.launch(CHROME ? { executablePath: CHROME } : {})

/** 打开设置抽屉 → 填密钥 → 保存（保存后抽屉自动关闭并建立 WS 连接）。 */
async function connectWithKey(page) {
  await page.click('button[aria-label="设置"]')
  await page.waitForTimeout(400)
  await page.screenshot({ path: `${OUT}/theme-${page.viewportSize().width}-settings.png` })
  await page.fill('input.key-input', KEY)
  await page.click('.btn-primary')
  await page.waitForTimeout(600)
}

// ---------- 375：移动端 ----------
const mobile = await browser.newPage({ viewport: { width: 375, height: 812 } })
await mobile.goto(BASE_URL, { waitUntil: 'networkidle' })
await mobile.screenshot({ path: `${OUT}/theme-375-empty.png` })
await connectWithKey(mobile)

// ---------- 1440：桌面 ----------
const desktop = await browser.newPage({ viewport: { width: 1440, height: 900 } })
await desktop.goto(BASE_URL, { waitUntil: 'networkidle' })
await desktop.screenshot({ path: `${OUT}/theme-1440-empty.png` })
await connectWithKey(desktop)

// ---------- 真实对话：拿到真实的用户 / AI 气泡 ----------
await desktop.fill('.chat-input textarea', '用一句话打个招呼')
await desktop.click('.chat-input .n-button')
await desktop.waitForTimeout(2500)
await desktop.screenshot({ path: `${OUT}/theme-1440-streaming.png` })
await desktop.waitForTimeout(12000)
await desktop.screenshot({ path: `${OUT}/theme-1440-chat.png` })

await mobile.fill('.chat-input textarea', '你好呀')
await mobile.click('.chat-input .n-button')
await mobile.waitForTimeout(12000)
await mobile.screenshot({ path: `${OUT}/theme-375-chat.png` })

// ---------- 角色面板：验证粉色激活态 ----------
await desktop.click('.character-info')
await desktop.waitForTimeout(400)
await desktop.screenshot({ path: `${OUT}/theme-1440-panel.png` })

// 选中一个角色，拿到 .item.active 的粉色淡底
const firstChar = desktop.locator('.item:not(.create)').first()
if (await firstChar.count()) {
  await firstChar.click()
  await desktop.click('.character-info')
  await desktop.waitForTimeout(400)
  await desktop.screenshot({ path: `${OUT}/theme-1440-panel-active.png` })
}

const msgs = await desktop.$$eval('.bubble-row', (els) => els.map((e) => e.textContent.trim()))
console.log('=== 消息列表（桌面端） ===')
msgs.forEach((m, i) => console.log(`[${i}] ${m.slice(0, 80)}`))

await browser.close()
console.log(`=== 截图完成: ${OUT}`)
