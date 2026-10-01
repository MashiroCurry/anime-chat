<!-- 自研消息气泡（CLAUDE.md：禁止用组件库） -->
<script setup lang="ts">
import type { ChatMessage } from '../composables/useChat'

defineProps<{ message: ChatMessage }>()
</script>

<template>
  <div class="bubble-row" :class="message.role">
    <div class="bubble">
      <span class="bubble-text">{{ message.content }}</span>
      <span v-if="message.streaming" class="cursor" aria-hidden="true"></span>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
  margin: 4px 0;
}
.bubble-row.user {
  justify-content: flex-end;
}
.bubble-row.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.user .bubble {
  background: var(--accent);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.assistant .bubble {
  background: var(--surface-2);
  color: var(--text);
  border-bottom-left-radius: 4px;
}
.cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: -0.15em;
  background: var(--accent);
  animation: blink 1s steps(1) infinite;
}
@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
