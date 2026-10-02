import type { GlobalThemeOverrides } from 'naive-ui'

// Naive UI 主题覆盖（浅色）。
// 色值必须与 styles/main.css 的 :root 保持同步——override 里不能写 var(--x)，
// seemly 的颜色解析是正则，遇到 var() 会直接抛错。
//
// 坑 1：use-theme 走的是纯 lodash merge，不做颜色派生。light 主题里
//   primaryColor / Hover / Pressed / Suppl 是四个独立常量（默认绿系），
//   只写 primaryColor 会残留默认绿色，必须四个全给。
// 坑 2：Input 的 border 是完整 shorthand（默认 `1px solid rgb(224,224,230)`），
//   不能只写颜色值。
export const themeOverrides: GlobalThemeOverrides = {
  common: {
    // 主色族：四个全写
    primaryColor: '#EC4899',
    primaryColorHover: '#DB2777',
    primaryColorPressed: '#DB2777',
    primaryColorSuppl: '#DB2777',

    // textColorBase 不会派生 textColor1/2/3，必须逐个给
    textColorBase: '#1F2937',
    textColor1: '#111827',
    textColor2: '#1F2937',
    textColor3: '#6B7280',
    textColorDisabled: '#9CA3AF',
    placeholderColor: '#9CA3AF',

    borderColor: '#E5E7EB',
    // drawer 的头/脚分隔线用的是 dividerColor，不是 borderColor
    dividerColor: '#E5E7EB',

    bodyColor: '#FFFFFF',
    cardColor: '#FFFFFF',
    // n-drawer 的 color 取自 modalColor
    modalColor: '#FFFFFF',
    popoverColor: '#FFFFFF',
    inputColor: '#FFFFFF',
    hoverColor: '#F9FAFB',
    pressedColor: '#F3F4F6',

    // 阴影：纯白底不适合重阴影，只留浮层用的极浅一档
    boxShadow1: 'none', // Card（本项目未用）
    boxShadow2: '0 4px 16px rgba(17, 24, 39, 0.08)', // popover / tooltip 等
    boxShadow3: '0 8px 24px rgba(17, 24, 39, 0.08)', // drawer + modal
  },
  Input: {
    color: '#FFFFFF',
    colorHover: '#FFFFFF',
    colorFocus: '#FFFFFF',
    border: '1px solid #E5E7EB',
    borderHover: '1px solid #E5E7EB',
    borderFocus: '1px solid #EC4899',
    borderDisabled: '1px solid #E5E7EB',
    textColor: '#1F2937',
    placeholderColor: '#9CA3AF',
    caretColor: '#EC4899',
    // 关掉 Naive 默认的 `0 0 0 2px rgba(primary, .2)` 聚焦光晕（禁止光晕）
    boxShadowFocus: 'none',
  },
  Drawer: {
    color: '#FFFFFF',
    // 只覆盖 drawer，不动与其共用 boxShadow3 的 modal
    boxShadow: '0 8px 24px rgba(17, 24, 39, 0.08)',
  },
}
