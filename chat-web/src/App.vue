<template>
  <div class="app">
    <header class="app-header">
      <div class="header-left">
        <div class="bot-avatar" aria-label="AI 助手">
          <svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" class="bot-svg">
            <defs>
              <linearGradient id="hairGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#7c5cff"/>
                <stop offset="100%" style="stop-color:#4a3aff"/>
              </linearGradient>
              <linearGradient id="skinGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#fff5ea"/>
                <stop offset="100%" style="stop-color:#ffe4d0"/>
              </linearGradient>
              <linearGradient id="bodyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#6366f1"/>
                <stop offset="100%" style="stop-color:#4338ca"/>
              </linearGradient>
            </defs>
            <ellipse cx="32" cy="58" rx="20" ry="4" fill="rgba(0,0,0,0.1)"/>
            <rect x="14" y="28" width="36" height="28" rx="12" fill="url(#bodyGrad)"/>
            <circle cx="32" cy="16" r="14" fill="url(#skinGrad)"/>
            <path d="M18 14 Q18 4 32 4 Q46 4 46 14 Q46 10 42 8 Q38 2 32 3 Q26 2 22 8 Q18 10 18 14 Z" fill="url(#hairGrad)"/>
            <path d="M20 12 Q22 6 28 5 Q30 9 27 12 Z" fill="#fff" opacity="0.4"/>
            <ellipse cx="26" cy="18" rx="2.2" ry="3" fill="#2d1b69"/>
            <ellipse cx="38" cy="18" rx="2.2" ry="3" fill="#2d1b69"/>
            <circle cx="26.8" cy="17" r="0.8" fill="#fff"/>
            <circle cx="38.8" cy="17" r="0.8" fill="#fff"/>
            <ellipse cx="22" cy="22" rx="2.5" ry="1.5" fill="#ffb4a2" opacity="0.6"/>
            <ellipse cx="42" cy="22" rx="2.5" ry="1.5" fill="#ffb4a2" opacity="0.6"/>
            <path d="M29 24 Q32 27 35 24" stroke="#2d1b69" stroke-width="1.5" fill="none" stroke-linecap="round"/>
            <circle cx="10" cy="36" r="3" fill="#a5b4fc" opacity="0.8"/>
            <circle cx="54" cy="36" r="3" fill="#a5b4fc" opacity="0.8"/>
            <rect x="26" y="38" width="12" height="8" rx="2" fill="#818cf8"/>
            <circle cx="32" cy="42" r="2" fill="#c7d2fe"/>
          </svg>
        </div>

        <div class="header-info">
          <nav class="nav-tabs" role="tablist" aria-label="对话模式">
            <router-link
              to="/"
              class="nav-tab"
              :class="{ 'nav-tab--active': $route.name === 'rag' }"
              role="tab"
              :aria-selected="$route.name === 'rag'"
            >
              RAG 智能对话
            </router-link>
            <router-link
              to="/agent"
              class="nav-tab"
              :class="{ 'nav-tab--active': $route.name === 'agent' }"
              role="tab"
              :aria-selected="$route.name === 'agent'"
            >
              Agent 智能对话
            </router-link>
          </nav>
          <p class="header-subtitle">
            <span class="online-dot"></span>
            在线
          </p>
        </div>
      </div>

      <div class="header-right">
        <a-select
          v-model="currentModel"
          size="small"
          class="model-select"
          @change="onModelChange"
          aria-label="选择模型"
        >
          <a-option v-for="m in modelOptions" :key="m.value" :value="m.value">
            {{ m.label }}
          </a-option>
        </a-select>
        <a-button
          type="text"
          size="small"
          class="clear-btn"
          @click="onClear"
          aria-label="清空聊天记录"
        >
          <template #icon><icon-delete :size="16" /></template>
          清空记录
        </a-button>
      </div>
    </header>

    <router-view :model="currentModel" @clear="onClear" />
  </div>
</template>

<script setup>
import { ref, provide, watch } from 'vue'
import { useRoute } from 'vue-router'
import { IconDelete } from '@arco-design/web-vue/es/icon'

const route = useRoute()

const STORAGE_MODEL_KEY = 'chat_model'
const DEFAULT_MODEL = 'deepseek-v4-flash'

const modelOptions = [
  { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
  { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' },
]

const savedModel = sessionStorage.getItem(STORAGE_MODEL_KEY)
const currentModel = ref(
  savedModel && modelOptions.some(m => m.value === savedModel)
    ? savedModel
    : DEFAULT_MODEL
)

const onModelChange = () => {
  sessionStorage.setItem(STORAGE_MODEL_KEY, currentModel.value)
}

let clearHandler = null
const chatStore = {
  registerClearHandler: (handler) => {
    clearHandler = handler
  },
}

provide('chatStore', chatStore)

const onClear = () => {
  if (clearHandler) {
    clearHandler()
  }
}

watch(() => route.name, () => {
  clearHandler = null
})
</script>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background-color: #ededed;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  height: 56px;
  background-color: #fff;
  border-bottom: 1px solid #e5e5e5;
  flex-shrink: 0;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.04);
  z-index: 10;
  gap: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.bot-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(99, 102, 241, 0.3);
}

.bot-svg {
  width: 36px;
  height: 36px;
  display: block;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-tabs {
  display: flex;
  align-items: center;
  background-color: #f0f0f0;
  border-radius: 20px;
  padding: 3px;
  gap: 2px;
}

.nav-tab {
  position: relative;
  padding: 4px 14px;
  font-size: 12px;
  font-weight: 400;
  color: #999;
  text-decoration: none;
  border-radius: 18px;
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  white-space: nowrap;
  z-index: 1;
}

.nav-tab--active {
  font-size: 14px;
  font-weight: 600;
  color: #4338ca;
  background-color: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.header-subtitle {
  margin: 0;
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 10px;
}

.online-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #07c160;
  box-shadow: 0 0 0 3px rgba(7, 193, 96, 0.18);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.model-select {
  width: 180px;
}

.model-select :deep(.arco-select-view) {
  background-color: #eef2ff;
  border-color: #c7d2fe;
  color: #4338ca;
}

.model-select :deep(.arco-select-view:hover) {
  border-color: #818cf8;
  background-color: #e0e7ff;
}

.model-select :deep(.arco-select-view-input) {
  color: #4338ca;
}

.model-select :deep(.arco-select-view-suffix-icon) {
  color: #6366f1;
}

.clear-btn {
  color: #666;
  transition: color 150ms ease-out, background-color 150ms ease-out;
}

.clear-btn:hover {
  color: #fa5151;
  background-color: rgba(250, 81, 81, 0.08);
}

.clear-btn:focus-visible {
  outline: 2px solid #07c160;
  outline-offset: 2px;
}

@media (max-width: 640px) {
  .app-header {
    height: 52px;
    padding: 0 12px;
    gap: 8px;
  }

  .bot-avatar {
    width: 36px;
    height: 36px;
  }

  .nav-tab {
    font-size: 14px;
    padding: 2px 8px;
  }

  .model-select {
    width: 120px;
    font-size: 13px;
  }

  .clear-btn .arco-btn-content > span:not(.arco-icon) {
    display: none;
  }
}
</style>
