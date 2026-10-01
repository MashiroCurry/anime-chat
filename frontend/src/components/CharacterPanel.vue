<!-- 角色列表/切换面板：主界面角色区的内联展开（非浮层），全部自绘 -->
<script setup lang="ts">
import type { Character } from '../types/character'

defineProps<{ characters: Character[]; currentId: string | null }>()
const emit = defineEmits<{
  select: [id: string]
  edit: [character: Character]
  create: []
  remove: [id: string]
}>()

function brief(c: Character): string {
  return c.card?.persona?.identity || c.card?.greeting || '（未填写人设）'
}
</script>

<template>
  <div class="character-panel">
    <button class="item create" @click="emit('create')">＋ 新建角色</button>

    <button
      v-for="c in characters"
      :key="c.id"
      class="item"
      :class="{ active: c.id === currentId }"
      @click="emit('select', c.id)"
    >
      <div class="item-main">
        <div class="item-name">{{ c.name }}</div>
        <div class="item-brief">{{ brief(c) }}</div>
      </div>
      <div class="item-actions">
        <span class="action" title="编辑" @click.stop="emit('edit', c)">编辑</span>
        <span class="action danger" title="删除" @click.stop="emit('remove', c.id)">删除</span>
      </div>
    </button>

    <p v-if="characters.length === 0" class="empty">还没有角色，点击「新建角色」开始。</p>
  </div>
</template>

<style scoped>
.character-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 12px 12px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface-2);
  color: var(--text);
  cursor: pointer;
  text-align: left;
  font-size: 14px;
}
.item:hover {
  border-color: var(--accent);
}
.item.active {
  border-color: var(--accent);
  background: rgba(91, 140, 255, 0.12);
}
.item.create {
  justify-content: center;
  border-style: dashed;
  color: var(--accent);
  background: transparent;
}
.item-main {
  flex: 1;
  min-width: 0;
}
.item-name {
  font-weight: 600;
}
.item-brief {
  font-size: 12px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.item-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}
.action {
  font-size: 12px;
  color: var(--text-dim);
}
.action:hover {
  color: var(--text);
}
.action.danger:hover {
  color: #ff6b6b;
}
.empty {
  padding: 12px;
  text-align: center;
  color: var(--text-dim);
  font-size: 13px;
}
</style>
