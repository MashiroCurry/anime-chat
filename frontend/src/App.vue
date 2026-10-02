<!-- 主界面：角色区 + 消息流 + 输入框 + 设置入口；角色管理（内联面板）+ 角色编辑（全屏视图） -->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { charactersApi } from './api/characters'
import CharacterPanel from './components/CharacterPanel.vue'
import ChatInput from './components/ChatInput.vue'
import MessageList from './components/MessageList.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'
import { useChat } from './composables/useChat'
import type { Character, CharacterCard } from './types/character'
import CharacterEditor from './views/CharacterEditor.vue'

const {
  messages,
  apiKey,
  characterId,
  connected,
  streaming,
  send,
  setApiKey,
  setCharacterId,
} = useChat()

const showSettings = ref(false)
const showPanel = ref(false)
const showEditor = ref(false)
const editingCharacter = ref<Character | null>(null)
const characters = ref<Character[]>([])

const currentCharacter = computed(
  () => characters.value.find((c) => c.id === characterId.value) ?? null,
)

onMounted(loadCharacters)

async function loadCharacters(): Promise<void> {
  characters.value = await charactersApi.list()
}

function toggleSettings(): void {
  showSettings.value = !showSettings.value
}

function togglePanel(): void {
  showPanel.value = !showPanel.value
}

function selectCharacter(id: string): void {
  setCharacterId(id)
  showPanel.value = false
}

function openCreate(): void {
  editingCharacter.value = null
  showEditor.value = true
  showPanel.value = false
}

function openEdit(c: Character): void {
  editingCharacter.value = c
  showEditor.value = true
}

async function removeCharacter(id: string): Promise<void> {
  if (!confirm('确定删除这个角色？')) return
  await charactersApi.remove(id)
  if (characterId.value === id) setCharacterId(null)
  await loadCharacters()
}

async function saveCharacter(name: string, card: CharacterCard): Promise<void> {
  if (editingCharacter.value) {
    await charactersApi.update(editingCharacter.value.id, { name, card })
  } else {
    const created = await charactersApi.create(name, card)
    setCharacterId(created.id)
  }
  showEditor.value = false
  await loadCharacters()
}

function onImportFile(e: Event): void {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = async () => {
    const dataUrl = reader.result as string
    const base64 = dataUrl.split(',')[1] ?? ''
    try {
      const created = await charactersApi.import(base64)
      setCharacterId(created.id)
      await loadCharacters()
    } catch (err) {
      alert(`导入失败：${(err as Error).message}`)
    } finally {
      input.value = ''
    }
  }
  reader.readAsDataURL(file)
}
</script>

<template>
  <div class="app-shell">
    <!-- 角色编辑：全屏视图，非浮层非路由 -->
    <div v-if="showEditor" class="phone-frame">
      <CharacterEditor
        :character="editingCharacter"
        @save="saveCharacter"
        @cancel="showEditor = false"
      />
    </div>

    <!-- 主界面 -->
    <div v-else class="phone-frame">
      <header class="character-bar">
        <div class="avatar-placeholder">{{ currentCharacter ? currentCharacter.name[0] : '✦' }}</div>
        <button class="character-info" @click="togglePanel">
          <div class="character-name">{{ currentCharacter ? currentCharacter.name : 'AI 伴侣' }}</div>
          <div class="character-status" :class="{ online: connected }">
            {{ connected ? '在线' : '未连接' }}
          </div>
        </button>
        <button class="icon-btn" aria-label="设置" @click="toggleSettings">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </header>

      <!-- 角色列表：内联展开（非浮层），是角色区的延伸 -->
      <CharacterPanel
        v-if="showPanel"
        :characters="characters"
        :current-id="characterId"
        @select="selectCharacter"
        @edit="openEdit"
        @create="openCreate"
        @remove="removeCharacter"
      />

      <!-- 导入入口：隐藏的 file input，放在角色面板下方，通过面板触发 -->
      <div v-if="showPanel" class="import-row">
        <label class="import-btn">
          导入角色卡（JSON / PNG）
          <input type="file" accept=".json,.png,.webp" hidden @change="onImportFile" />
        </label>
      </div>

      <MessageList :messages="messages" />

      <ChatInput
        :disabled="!apiKey || !connected || streaming"
        @send="send"
      />
    </div>

    <SettingsDrawer
      v-model="showSettings"
      :api-key="apiKey"
      :character-id="characterId"
      @save="setApiKey"
    />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: var(--bg);
}
.phone-frame {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 720px;
  height: 100vh;
  background: var(--surface);
}
.character-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}
.avatar-placeholder {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: var(--on-accent);
  font-size: 20px;
  flex-shrink: 0;
}
.character-info {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
  padding: 0;
}
.character-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.character-status {
  font-size: 12px;
  color: var(--text-dim);
}
/* 白底小字用 --accent-hover：--accent 在白底仅 3.5:1，正文字号不达标 */
.character-status.online {
  color: var(--accent-hover);
}
.icon-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
}
.icon-btn:hover {
  background: var(--surface-2);
}
.import-row {
  padding: 0 12px 10px;
  border-bottom: 1px solid var(--border);
}
.import-btn {
  display: block;
  text-align: center;
  padding: 8px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  color: var(--text-dim);
  font-size: 13px;
  cursor: pointer;
}
.import-btn:hover {
  color: var(--accent-hover);
  border-color: var(--accent);
}
</style>
