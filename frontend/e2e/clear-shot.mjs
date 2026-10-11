// 清空聊天记录验证：发 3 条 → 打开设置清空 → 聊天清空、记忆不受影响 → 再发 1 条只剩这 1 条。
// 用法：COMPANION_API_KEY=sk-xxx BASE_URL=http://localhost:5173 node e2e/clear-shot.mjs
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

async function waitBubbleCount(page, n, timeout = 15000) {
  await page.waitForFunction(
    (target) => document.querySelectorAll('.bubble-row').length === target,
    n,
    { timeout },
  )
}

async function send(page, text) {
  await page.fill('.chat-input textarea', text)
  await page.click('.chat-input .n-button')
  await waitIdle(page)
  await page.waitForTimeout(300)
}

const results = []
const check = (name, pass, detail) => {
  results.push({ name, pass, detail })
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`)
}

const page = await browser.newPage({ viewport: VIEWPORT })
// 自动接受 confirm 弹窗（清空聊天记录的确认）
page.on('dialog', (d) => d.accept())
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

// 记录基线（该角色可能已有历史），再发 3 条（含可被记忆抽取的事实）
const baseCount = (await bubbles(page)).length
await send(page, '你好，我叫小北')
await send(page, '我最喜欢的颜色是青柠绿')
await send(page, '记住我住在上海')
// 记忆抽取是异步 fire-and-forget，多等几秒让它落库
await page.waitForTimeout(8000)

const beforeCount = (await bubbles(page)).length
check(
  '发送后新增 3 对消息（3 用户 + 3 助手）',
  beforeCount === baseCount + 6,
  `基线 ${baseCount} → ${beforeCount} 条`,
)

// 打开设置，等记忆列表加载稳定，记录「AI 记住的事」区块内容
await page.click('button[aria-label="设置"]')
await page.waitForTimeout(400)
await page.waitForFunction(
  () => !(document.querySelector('.memories')?.textContent ?? '').includes('加载中'),
  { timeout: 10000 },
)
await page.waitForTimeout(500)
const memoriesBefore = (await page.locator('.memories').textContent())?.trim() ?? ''
console.log(`  [记忆区] 清空前：「${memoriesBefore}」`)

// 清空聊天记录（自动接受 confirm）
await page.click('.chat-history .reset-btn')
await waitBubbleCount(page, 0)
await page.waitForTimeout(300)
await page.screenshot({ path: `${OUT}/clear-after-clear-drawer.png` })

const afterCount = (await bubbles(page)).length
check('清空后聊天记录为 0 条', afterCount === 0, `${afterCount} 条`)

const memoriesAfter = (await page.locator('.memories').textContent())?.trim() ?? ''
check(
  '设置里的「AI 记住的事」不受影响',
  memoriesAfter === memoriesBefore,
  `清空后：「${memoriesAfter}」`,
)

// 关抽屉，再发 1 条，确认只剩这 1 对
await page.keyboard.press('Escape')
await page.waitForTimeout(600)
await page.screenshot({ path: `${OUT}/clear-empty-chat.png` })

await send(page, '清空后新的一句话')
const finalBubbles = await bubbles(page)
check(
  '清空后发新消息只剩 1 对（1 用户 + 1 助手）',
  finalBubbles.length === 2 && finalBubbles.some((b) => b.includes('清空后新的一句话')),
  `${finalBubbles.length} 条`,
)

await browser.close()

const failed = results.filter((r) => !r.pass)
console.log(`\n=== ${results.length - failed.length}/${results.length} 通过 ===`)
process.exit(failed.length ? 1 : 0)
