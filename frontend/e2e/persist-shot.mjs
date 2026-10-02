// 持久化验证：发消息 → 刷新 → 记录还在 + 输入框直接可用；另用独立 context 验证跨设备共享。
// 用法：COMPANION_API_KEY=sk-xxx BASE_URL=http://localhost:5173 node e2e/persist-shot.mjs
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

const CHROME = process.env.PLAYWRIGHT_CHROMIUM_PATH
const browser = await chromium.launch(CHROME ? { executablePath: CHROME } : {})
const VIEWPORT = { width: 1440, height: 900 }

const bubbles = (page) =>
  page.$$eval('.bubble-row', (els) => els.map((e) => e.textContent.trim()))

/** 等流式结束：输入框重新可用即代表 streaming=false。 */
async function waitIdle(page) {
  await page.waitForFunction(
    () => {
      const ta = document.querySelector('.chat-input textarea')
      return ta && !ta.disabled
    },
    { timeout: 60000 },
  )
}

const results = []
const check = (name, pass, detail) => {
  results.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

// ================= 主流程：桌面端 =================
const desktopCtx = await browser.newContext({ viewport: VIEWPORT })
const page = await desktopCtx.newPage()
await page.goto(BASE_URL, { waitUntil: 'networkidle' })

// 首次进入：设置密钥 + 选角色
await page.click('button[aria-label="设置"]')
await page.waitForTimeout(400)
await page.fill('input.key-input', KEY)
await page.click('.btn-primary')
await page.waitForTimeout(600)

await page.click('.character-info')
await page.waitForTimeout(300)
const charName = (
  await page.locator('.item:not(.create)').first().locator('.item-name').textContent()
)?.trim()
await page.locator('.item:not(.create)').first().click()
await page.waitForTimeout(800)

// 发一条有辨识度的消息
const SENTINEL = '我最喜欢的颜色是青柠绿'
await page.fill('.chat-input textarea', SENTINEL)
await page.click('.chat-input .n-button')
await waitIdle(page)
await page.waitForTimeout(500)
await page.screenshot({ path: `${OUT}/persist-1440-before-reload.png` })

const before = await bubbles(page)
check('发送后消息已上屏', before.some((b) => b.includes(SENTINEL)), `${before.length} 条`)

// ================= 刷新 =================
await page.reload({ waitUntil: 'networkidle' })
await page.waitForTimeout(2500)
await page.screenshot({ path: `${OUT}/persist-1440-after-reload.png` })

const after = await bubbles(page)
const inputDisabled = await page.locator('.chat-input textarea').isDisabled()
const status = (await page.locator('.character-status').textContent())?.trim()
const shownName = (await page.locator('.character-name').textContent())?.trim()

check(
  '刷新后聊天记录仍在',
  after.some((b) => b.includes(SENTINEL)),
  `刷新后 ${after.length} 条（刷新前 ${before.length} 条）`,
)
check('刷新后输入框直接可用', !inputDisabled)
check('刷新后角色已恢复', shownName === charName, `显示「${shownName}」`)
check('刷新后 WS 已自动重连', status === '在线', `状态「${status}」`)

// ================= 跨设备：独立 context（模拟手机）=================
const phoneCtx = await browser.newContext({ viewport: { width: 375, height: 812 } })
const phone = await phoneCtx.newPage()
await phone.goto(BASE_URL, { waitUntil: 'networkidle' })
await phone.waitForTimeout(800)

// 新设备没有 localStorage，需重新选一次角色；选完历史应当自动出现
await phone.click('.character-info')
await phone.waitForTimeout(300)
await phone.locator('.item:not(.create)').first().click()
await phone.waitForTimeout(1500)
await phone.screenshot({ path: `${OUT}/persist-375-cross-device.png` })

const phoneBubbles = await bubbles(phone)
check(
  '新设备选完角色即看到同一段对话',
  phoneBubbles.some((b) => b.includes(SENTINEL)),
  `${phoneBubbles.length} 条`,
)

await browser.close()

const failed = results.filter((r) => !r.pass)
console.log(`\n=== ${results.length - failed.length}/${results.length} 通过 ===`)
process.exit(failed.length ? 1 : 0)
