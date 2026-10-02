<!-- 角色创建/编辑视图（全屏，非浮层非路由）。表单全部自绘，不新增 Naive UI。 -->
<script setup lang="ts">
import { reactive } from 'vue'

import { emptyCard, type Character, type CharacterCard } from '../types/character'

const props = defineProps<{ character: Character | null }>()
const emit = defineEmits<{ save: [name: string, card: CharacterCard]; cancel: [] }>()

const name = reactive({ value: props.character?.name ?? '' })
const card = reactive<CharacterCard>(
  props.character ? JSON.parse(JSON.stringify(props.character.card)) : emptyCard(),
)

function addExample(): void {
  card.examples.push({ user: '', assistant: '' })
}
function removeExample(i: number): void {
  card.examples.splice(i, 1)
}

function submit(): void {
  if (!name.value.trim()) {
    alert('请填写角色名')
    return
  }
  emit('save', name.value.trim(), JSON.parse(JSON.stringify(card)))
}
</script>

<template>
  <div class="editor">
    <header class="editor-bar">
      <button class="ghost" @click="emit('cancel')">← 返回</button>
      <span class="title">{{ character ? '编辑角色' : '新建角色' }}</span>
      <button class="primary" @click="submit">保存</button>
    </header>

    <div class="form">
      <label class="field">
        <span class="label">角色名 *</span>
        <input v-model="name.value" class="input" placeholder="给角色起个名字" />
      </label>

      <section class="group">
        <h3 class="group-title">人设</h3>
        <label class="field">
          <span class="label">身份 / 背景故事</span>
          <textarea v-model="card.persona.identity" class="input" rows="3" placeholder="它是谁？有什么背景？" />
        </label>
        <label class="field">
          <span class="label">性格</span>
          <textarea v-model="card.persona.personality" class="input" rows="2" placeholder="性格标签与描述" />
        </label>
        <label class="field">
          <span class="label">说话风格</span>
          <textarea v-model="card.persona.speaking_style" class="input" rows="2" placeholder="口头禅、语气、句式习惯" />
        </label>
        <label class="field">
          <span class="label">世界观</span>
          <textarea v-model="card.persona.worldview" class="input" rows="2" placeholder="故事发生在什么世界？" />
        </label>
        <label class="field">
          <span class="label">与用户的关系</span>
          <input v-model="card.persona.relationship" class="input" placeholder="比如：恋人、朋友、宠物" />
        </label>
      </section>

      <label class="field">
        <span class="label">开场白</span>
        <textarea v-model="card.greeting" class="input" rows="2" placeholder="首次对话时角色说的第一句话" />
      </label>

      <section class="group">
        <h3 class="group-title">对话示例（few-shot）</h3>
        <div v-for="(ex, i) in card.examples" :key="i" class="example-row">
          <div class="example-fields">
            <input v-model="ex.user" class="input" placeholder="用户说" />
            <input v-model="ex.assistant" class="input" placeholder="角色说" />
          </div>
          <button class="ghost small" @click="removeExample(i)">删除</button>
        </div>
        <button class="ghost" @click="addExample">＋ 添加示例</button>
      </section>

      <section class="group">
        <h3 class="group-title">模型参数</h3>
        <label class="field">
          <span class="label">温度 temperature（0–2）</span>
          <input v-model.number="card.llm.temperature" class="input" type="number" min="0" max="2" step="0.1" />
        </label>
      </section>
    </div>
  </div>
</template>

<style scoped>
.editor {
  display: flex;
  flex-direction: column;
  max-width: 720px;
  margin: 0 auto;
  height: 100vh;
  background: var(--surface);
}
.editor-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.title {
  flex: 1;
  text-align: center;
  font-weight: 600;
}
.form {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.group-title {
  font-size: 13px;
  color: var(--text-dim);
  font-weight: 600;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.label {
  font-size: 13px;
  color: var(--text-dim);
}
.input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  /* 白底 + 浅灰边框，与主输入框（n-input）保持一致 */
  background: var(--surface);
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  outline: none;
}
.input:focus {
  border-color: var(--accent);
}
.example-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}
.example-fields {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.ghost {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  font-size: 14px;
}
.ghost.small {
  padding: 6px 10px;
  font-size: 12px;
}
.primary {
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: var(--on-accent);
  cursor: pointer;
  font-size: 14px;
}
.primary:hover {
  background: var(--accent-hover);
}
</style>
