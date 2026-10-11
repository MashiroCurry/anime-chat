<!-- 主界面输入区：n-input + n-button（主界面常驻 Naive UI 恰好 2 个，符合预算） -->
<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')
const inputEl = ref<{ focus: () => void } | null>(null)
const containerEl = ref<HTMLElement | null>(null)
// 用户是否主动离开了输入区（点击/触摸到输入框容器外）。
// 用于避免回复结束后抢焦点、避免移动端误弹软键盘。
const userLeftInput = ref(false)

function focusInput(): void {
  void nextTick(() => inputEl.value?.focus())
}

function onPointerDown(e: PointerEvent): void {
  if (containerEl.value && !containerEl.value.contains(e.target as Node)) {
    userLeftInput.value = true
  }
}

function onFocus(): void {
  userLeftInput.value = false
}

function submit(): void {
  const t = text.value.trim()
  if (!t || props.disabled) return
  userLeftInput.value = false // 发送动作视为「想继续输入」
  emit('send', t)
  text.value = ''
  focusInput()
}

// 流式回复结束、输入框从禁用变可用时，若用户没主动离开，则重新聚焦
watch(
  () => props.disabled,
  (disabled, wasDisabled) => {
    if (wasDisabled && !disabled && !userLeftInput.value) focusInput()
  },
)

onMounted(() => document.addEventListener('pointerdown', onPointerDown))
onBeforeUnmount(() => document.removeEventListener('pointerdown', onPointerDown))
</script>

<template>
  <div ref="containerEl" class="chat-input">
    <n-input
      ref="inputEl"
      v-model:value="text"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 4 }"
      placeholder="说点什么…"
      :disabled="disabled"
      @keydown.enter.exact.prevent="submit"
      @focus="onFocus"
    />
    <n-button type="primary" :disabled="disabled || !text.trim()" @click="submit">
      发送
    </n-button>
  </div>
</template>

<style scoped>
.chat-input {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  padding: 10px 12px;
  border-top: 1px solid var(--border);
}
.chat-input :deep(.n-input) {
  flex: 1;
}
</style>
