import { chromium } from 'playwright'
import { readFileSync } from 'node:fs'
const KEY = readFileSync('D:/Desktop/聊天软件/密钥.txt', 'utf-8').trim()
const EXE = process.env.LOCALAPPDATA + '/ms-playwright/chromium-1223/chrome-win64/chrome.exe'
const browser = await chromium.launch({ executablePath: EXE })
const page = await browser.newPage({ viewport: { width: 420, height: 820 } })
await page.goto('http://localhost:5173', { waitUntil: 'networkidle' })

await page.click('button[aria-label="设置"]')
await page.waitForTimeout(300)
await page.fill('input.key-input', KEY)
await page.click('.btn-primary')
await page.waitForTimeout(800)

await page.click('.character-info')
await page.waitForTimeout(400)
const names = await page.$$eval('.item-name', els => els.map(e => e.textContent.trim()))
console.log('可用角色:', names)
await page.click('.item:not(.create)')
await page.waitForTimeout(400)
console.log('当前角色:', await page.textContent('.character-name'))

await page.fill('.chat-input textarea', '用一句话说说你现在的心情')
await page.click('.chat-input .n-button')
await page.waitForTimeout(9000)
const msgs = await page.$$eval('.bubble-row', els => els.map(e => e.textContent.trim()))
console.log('=== 对话 ===')
msgs.forEach((m,i) => console.log(`[${i}] ${m}`))
await page.screenshot({ path: 'D:/Desktop/聊天软件/screenshots/restart-verify.png' })
await browser.close()
