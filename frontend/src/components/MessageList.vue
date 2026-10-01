<!-- 自研消息列表（CLAUDE.md：禁止用组件库；禁止一次性渲染全部记录） -->
<script setup lang="ts">
import { ref, watch } from 'vue'

import type { ChatMessage } from '../composables/useChat'
import MessageBubble from './MessageBubble.vue'

const props = defineProps<{ messages: ChatMessage[] }>()

const listEl = ref<HTMLElement | null>(null)

// 新消息到达时滚动到底部（只在流式/新增时触发）
watch(
  () => props.messages,
  () => {
    requestAnimationFrame(() => {
      const el = listEl.value
      if (el) el.scrollTop = el.scrollHeight
    })
  },
)
</script>

<template>
  <div ref="listEl" class="message-list">
    <MessageBubble v-for="m in messages" :key="m.id" :message="m" />
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
}
</style>
