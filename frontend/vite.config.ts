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
    port: 5173,
    proxy: {
      // 开发期把 /api 代理到后端，避免跨域
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true, // WS 代理也要开，否则 /api/v1/ws/chat 连不上
      },
    },
  },
})
