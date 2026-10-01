<!-- 设置抽屉（浮层）：n-drawer 容器；密钥输入 + 记忆列表均自绘（浮层候选清单无 n-input） -->
<script setup lang="ts">
import { ref, watch } from 'vue'

import { memoriesApi, type Memory } from '../api/memories'

const props = defineProps<{ modelValue: boolean; apiKey: string; characterId: string | null }>()
const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  save: [key: string]
}>()

const draft = ref(props.apiKey)
const memories = ref<Memory[]>([])
const memoriesLoading = ref(false)

function onClose(): void {
  emit('update:modelValue', false)
}

function onSave(): void {
  emit('save', draft.value.trim())
  emit('update:modelValue', false)
}

function onClear(): void {
  draft.value = ''
  emit('save', '')
}

async function loadMemories(): Promise<void> {
  if (!props.characterId) {
    memories.value = []
    return
  }
  memoriesLoading.value = true
  try {
    memories.value = await memoriesApi.list(props.characterId)
  } catch {
    memories.value = []
  } finally {
    memoriesLoading.value = false
  }
}

async function removeMemory(id: string): Promise<void> {
  try {
    await memoriesApi.remove(id)
    memories.value = memories.value.filter((m) => m.memory_id !== id)
  } catch {
    // 删除失败静默，用户可重试
  }
}

async function resetMemories(): Promise<void> {
  if (!confirm('清空所有角色的全部记忆？此操作不可恢复。')) return
  try {
    await memoriesApi.reset()
    memories.value = []
  } catch {
    // 清空失败静默，用户可重试
  }
}

// 打开抽屉且有角色时加载记忆
watch(
  () => props.modelValue,
  (open) => {
    if (open) loadMemories()
  },
)
</script>

<template>
  <n-drawer
    :show="modelValue"
    :width="360"
    placement="right"
    @update:show="(v: boolean) => emit('update:modelValue', v)"
  >
    <n-drawer-content title="设置" closable @close="onClose">
      <div class="settings-field">
        <label class="field-label">API 密钥（BYOK）</label>
        <input
          v-model="draft"
          class="key-input"
          type="password"
          placeholder="sk-…（仅存本机浏览器，不经过服务端存储）"
          autocomplete="off"
        />
        <p class="field-hint">
          密钥只保存在你的浏览器（localStorage），随 WebSocket 首帧发送，服务端不落盘。
        </p>
      </div>

      <div v-if="characterId" class="settings-field memories">
        <label class="field-label">AI 记住的事</label>
        <p v-if="memoriesLoading" class="field-hint">加载中…</p>
        <p v-else-if="memories.length === 0" class="field-hint">还没有长期记忆。</p>
        <div v-else class="memory-list">
          <div v-for="m in memories" :key="m.memory_id" class="memory-item">
            <span class="memory-text">{{ m.content }}</span>
            <button class="memory-del" title="删除" @click="removeMemory(m.memory_id)">×</button>
          </div>
        </div>
        <button v-if="memories.length > 0" class="reset-btn" @click="resetMemories">清空全部记忆</button>
      </div>

      <template #footer>
        <div class="footer-actions">
          <button class="btn-ghost" @click="onClear">清除</button>
          <button class="btn-primary" @click="onSave">保存</button>
        </div>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<style scoped>
.settings-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.memories {
  margin-top: 20px;
}
.field-label {
  font-size: 13px;
  color: var(--text-dim);
}
.key-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
  color: var(--text);
  font-family: inherit;
  outline: none;
}
.key-input:focus {
  border-color: var(--accent);
}
.field-hint {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.5;
}
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 240px;
  overflow-y: auto;
}
.memory-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-2);
}
.memory-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
  word-break: break-word;
}
.memory-del {
  border: none;
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  padding: 0 2px;
}
.memory-del:hover {
  color: #ff6b6b;
}
.reset-btn {
  margin-top: 8px;
  padding: 8px;
  border: 1px solid #ff6b6b;
  border-radius: 8px;
  background: transparent;
  color: #ff6b6b;
  cursor: pointer;
  font-size: 13px;
}
.reset-btn:hover {
  background: rgba(255, 107, 107, 0.1);
}
.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.btn-ghost,
.btn-primary {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid var(--border);
  cursor: pointer;
  font-size: 14px;
}
.btn-ghost {
  background: transparent;
  color: var(--text);
}
.btn-primary {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}
</style>
