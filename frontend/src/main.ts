import { createApp, h } from 'vue'
import { NConfigProvider, lightTheme } from 'naive-ui'

import App from './App.vue'
import './styles/main.css'
import { themeOverrides } from './styles/theme'

// 所有 Naive UI 组件必须包裹在 <n-config-provider>，主题用 lightTheme + themeOverrides（CLAUDE.md 硬性要求）。
// 模板内组件经 unplugin-vue-components 按需引入；这里的 NConfigProvider 是显式导入（主题系统基础）。
const app = createApp({
  render: () =>
    h(
      NConfigProvider,
      { theme: lightTheme, themeOverrides },
      { default: () => h(App) },
    ),
})

app.mount('#app')
