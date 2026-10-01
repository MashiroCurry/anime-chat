<!-- 主界面输入区：n-input + n-button（主界面常驻 Naive UI 恰好 2 个，符合预算） -->
<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ disabled: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

const text = ref('')

function submit(): void {
  const t = text.value.trim()
  if (!t || props.disabled) return
  emit('send', t)
  text.value = ''
}
</script>

<template>
  <div class="chat-input">
    <n-input
      v-model:value="text"
      type="textarea"
      :autosize="{ minRows: 1, maxRows: 4 }"
      placeholder="说点什么…"
      :disabled="disabled"
      @keydown.enter.exact.prevent="submit"
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
