import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { NaiveUiResolver } from 'unplugin-vue-components/resolvers'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    // Naive UI 按需引入（CLAUDE.md 硬性要求，禁止全量引入）
    Components({
      resolvers: [NaiveUiResolver()],
    }),
  ],
  server: {
    // 监听所有网卡：手机连同一 Wi-Fi 时用局域网 IP 访问。
    // 默认只绑 127.0.0.1，手机连不上。
    host: '0.0.0.0',
    port: 5173,
    // 端口被占用时直接报错，不静默换到 5174 —— 否则手机上会输错端口
    strictPort: true,
    proxy: {
      // 开发期把 /api 代理到后端，避免跨域。
      // target 用 127.0.0.1 是对的：代理发生在电脑本机，
      // 手机只跟 5173 打交道，不需要直连 8000，也就不需要 CORS。
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true, // WS 代理也要开，否则 /api/v1/ws/chat 连不上
      },
    },
  },
})
