<template>
  <div class="chat-app">
    <header class="chat-header">
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
          <h1 class="header-title">RAG 智能问答</h1>
          <p class="header-subtitle">
            <span class="online-dot"></span>
            在线
          </p>
        </div>
      </div>
      <a-button
        v-if="messages.length > 0"
        type="text"
        size="small"
        class="clear-btn"
        @click="clearHistory"
        aria-label="清空聊天记录"
      >
        <template #icon><icon-delete :size="16" /></template>
        清空记录
      </a-button>
    </header>

    <main
      ref="listRef"
      class="chat-body"
      role="log"
      aria-live="polite"
      aria-label="聊天消息"
    >
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <p class="empty-title">开始你的智能问答</p>
        <p class="empty-desc">输入问题，AI 将基于本地知识库为你解答</p>
        <div class="quick-questions">
          <button
            v-for="q in suggestions"
            :key="q"
            class="quick-tag"
            @click="quickAsk(q)"
            :aria-label="'快速提问：' + q"
          >
            {{ q }}
          </button>
        </div>
      </div>

      <div
        v-for="(msg, idx) in messages"
        :key="idx"
        class="msg-row"
        :class="msg.role === 'user' ? 'msg-row--self' : ''"
      >
        <div class="msg-avatar" :class="msg.role === 'user' ? 'avatar--user' : 'avatar--bot'">
          <span v-if="msg.role === 'user'">我</span>
          <svg v-else viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" class="msg-svg" aria-hidden="true">
            <defs>
              <linearGradient id="hairGradMsg" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#7c5cff"/>
                <stop offset="100%" style="stop-color:#4a3aff"/>
              </linearGradient>
              <linearGradient id="skinGradMsg" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#fff5ea"/>
                <stop offset="100%" style="stop-color:#ffe4d0"/>
              </linearGradient>
              <linearGradient id="bodyGradMsg" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style="stop-color:#6366f1"/>
                <stop offset="100%" style="stop-color:#4338ca"/>
              </linearGradient>
            </defs>
            <circle cx="32" cy="16" r="12" fill="url(#skinGradMsg)"/>
            <path d="M20 14 Q20 4 32 3 Q44 4 44 14 Q44 10 40 8 Q36 3 32 4 Q28 3 24 8 Q20 10 20 14 Z" fill="url(#hairGradMsg)"/>
            <ellipse cx="26" cy="17" rx="2" ry="2.6" fill="#2d1b69"/>
            <ellipse cx="38" cy="17" rx="2" ry="2.6" fill="#2d1b69"/>
            <circle cx="26.7" cy="16.2" r="0.7" fill="#fff"/>
            <circle cx="38.7" cy="16.2" r="0.7" fill="#fff"/>
            <ellipse cx="22" cy="21" rx="2.2" ry="1.3" fill="#ffb4a2" opacity="0.6"/>
            <ellipse cx="42" cy="21" rx="2.2" ry="1.3" fill="#ffb4a2" opacity="0.6"/>
            <path d="M29 23 Q32 25.5 35 23" stroke="#2d1b69" stroke-width="1.3" fill="none" stroke-linecap="round"/>
            <rect x="16" y="27" width="32" height="22" rx="10" fill="url(#bodyGradMsg)"/>
            <rect x="27" y="32" width="10" height="6" rx="1.5" fill="#818cf8"/>
            <circle cx="32" cy="35" r="1.6" fill="#c7d2fe"/>
          </svg>
        </div>
        <div
          class="msg-bubble"
          :class="[
            msg.role === 'user' ? 'bubble--self' : 'bubble--bot',
            msg.streaming ? 'bubble--streaming' : ''
          ]"
        >
          <div v-if="msg.loading" class="typing-dots" role="status" aria-label="正在输入">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <template v-else>
            {{ msg.content }}
            <span v-if="msg.streaming" class="streaming-dots" aria-hidden="true">/...</span>
          </template>
          <div v-if="msg.isFallback" class="fallback-hint" role="note">
            <span class="fallback-icon">⚠️</span>
            {{ msg.fallbackMessage || 'AI 服务异常，已返回兜底回复' }}
          </div>
        </div>
      </div>
    </main>

    <footer class="chat-footer">
      <div class="input-wrapper">
        <a-textarea
          v-model="inputText"
          placeholder="输入问题，按 Enter 发送，Shift+Enter 换行"
          :auto-size="{ minRows: 1, maxRows: 5 }"
          :disabled="isStreaming"
          @keydown="onKeyDown"
          class="chat-input"
          aria-label="消息输入框"
        />
        <a-button
          type="primary"
          :loading="isStreaming"
          :disabled="!inputText.trim()"
          @click="sendMessage"
          shape="round"
          size="large"
          class="send-btn"
          aria-label="发送消息"
        >
          <template #icon v-if="!isStreaming"><icon-send :size="16" /></template>
          发送
        </a-button>
      </div>
      <p class="footer-hint">AI 回答仅供参考，请核实重要信息</p>
    </footer>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconDelete, IconSend } from '@arco-design/web-vue/es/icon'

const STORAGE_KEY = 'rag_chat_session'
const SESSION_KEY = 'rag_session_id'

const messages = ref([])
const sessionId = ref('')
const inputText = ref('')
const isStreaming = ref(false)
const listRef = ref(null)

const suggestions = [
  '猫和狗有什么区别？',
  '期货交易有哪些规则？',
  '建仓时要注意什么？',
  '焦煤怎么操作？',
]

const loadFromStorage = () => {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    const sid = sessionStorage.getItem(SESSION_KEY)
    if (sid) sessionId.value = sid
    if (saved) {
      messages.value = JSON.parse(saved)
    }
  } catch (e) {
    console.warn('加载历史记录失败', e)
  }
}

const saveToStorage = () => {
  try {
    const toSave = messages.value
      .filter(m => !m.loading)
      .map(m => ({ role: m.role, content: m.content }))
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
    if (sessionId.value) {
      sessionStorage.setItem(SESSION_KEY, sessionId.value)
    }
  } catch (e) {
    console.warn('保存历史记录失败', e)
  }
}

watch(messages, () => {
  if (!isStreaming.value) {
    saveToStorage()
  }
}, { deep: true })

const scrollToBottom = async () => {
  await nextTick()
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight
  }
}

const quickAsk = (q) => {
  inputText.value = q
  sendMessage()
}

const sendMessage = async () => {
  const text = inputText.value.trim()
  if (!text || isStreaming.value) return

  messages.value.push({ role: 'user', content: text })
  inputText.value = ''

  const botMsg = { role: 'assistant', content: '', loading: true, streaming: false }
  messages.value.push(botMsg)

  isStreaming.value = true
  await scrollToBottom()

  try {
    const headers = { 'Content-Type': 'application/json' }
    if (sessionId.value) {
      headers['X-Session-Id'] = sessionId.value
    }

    const response = await fetch('/chat/stream', {
      method: 'POST',
      headers,
      body: JSON.stringify({ query: text }),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const respSessionId = response.headers.get('X-Session-Id')
    if (respSessionId) {
      sessionId.value = respSessionId
    }

    botMsg.loading = false
    botMsg.streaming = true

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue

        let evt
        try {
          evt = JSON.parse(raw)
        } catch {
          continue
        }

        switch (evt.type) {
          case 'session':
            if (evt.session_id) sessionId.value = evt.session_id
            break
          case 'text':
            if (evt.content) {
              botMsg.content += evt.content
              await scrollToBottom()
            }
            break
          case 'fallback':
            botMsg.isFallback = true
            botMsg.fallbackMessage = evt.message
            break
          case 'error':
            throw new Error(evt.message || '服务异常')
          case 'done':
            botMsg.streaming = false
            break
        }
      }
    }

    botMsg.streaming = false
  } catch (err) {
    botMsg.loading = false
    botMsg.streaming = false
    botMsg.content = `请求失败：${err.message}`
    Message.error('对话请求失败')
  } finally {
    isStreaming.value = false
    saveToStorage()
    await scrollToBottom()
  }
}

const onKeyDown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

const clearHistory = () => {
  Modal.confirm({
    title: '确认清空',
    content: '确定要清空所有聊天记录吗？',
    okText: '清空',
    cancelText: '取消',
    onOk: async () => {
      const currentSessionId = sessionId.value
      messages.value = []
      sessionStorage.removeItem(STORAGE_KEY)
      sessionStorage.removeItem(SESSION_KEY)
      sessionId.value = ''
      try {
        await fetch('/chat/history', {
          method: 'DELETE',
          headers: currentSessionId ? { 'X-Session-Id': currentSessionId } : {},
        })
      } catch (e) { /* ignore */ }
      Message.success('已清空聊天记录')
    },
  })
}

onMounted(() => {
  loadFromStorage()
  scrollToBottom()
})
</script>

<style scoped>
.chat-app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  width: 100%;
  background-color: #ededed;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* ===== 顶部 ===== */
.chat-header {
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
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
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

.header-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.header-subtitle {
  margin: 2px 0 0 0;
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 6px;
}

.online-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #07c160;
  box-shadow: 0 0 0 3px rgba(7, 193, 96, 0.18);
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

/* ===== 聊天区 ===== */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
  scroll-behavior: smooth;
}

.chat-body::-webkit-scrollbar {
  width: 5px;
}

.chat-body::-webkit-scrollbar-track {
  background: transparent;
}

.chat-body::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 3px;
}

.chat-body::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.25);
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
  animation: msg-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

@keyframes msg-in {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.msg-row--self {
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
}

.avatar--bot {
  background: linear-gradient(135deg, #e0e7ff 0%, #c7d2fe 100%);
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(99, 102, 241, 0.25);
}

.msg-svg {
  width: 32px;
  height: 32px;
  display: block;
}

.avatar--user {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
}

.msg-bubble {
  max-width: 70%;
  padding: 10px 14px;
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
  white-space: pre-wrap;
  position: relative;
  border-radius: 6px;
}

.bubble--bot {
  background-color: #fff;
  color: #333;
}

.bubble--bot::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 14px;
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 6px solid #fff;
}

.bubble--self {
  background-color: #95ec69;
  color: #333;
}

.bubble--self::after {
  content: '';
  position: absolute;
  right: -6px;
  top: 14px;
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-left: 6px solid #95ec69;
}

.bubble--streaming {
  min-height: 1.6em;
}

/* 流式输出 /... 动态效果 */
.streaming-dots {
  display: inline-block;
  margin-left: 2px;
  color: #999;
  font-weight: 500;
  animation: dots-pulse 1.2s ease-in-out infinite;
}

@keyframes dots-pulse {
  0%, 100% {
    opacity: 0.4;
    letter-spacing: 0;
  }
  50% {
    opacity: 1;
    letter-spacing: 1px;
  }
}

/* loading 动画 */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
  align-items: center;
}

.typing-dots span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #bbb;
  opacity: 0.5;
  animation: typing 1.2s ease-in-out infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes typing {
  0%, 80%, 100% {
    transform: scale(0.8);
    opacity: 0.4;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

/* ===== 空状态 ===== */
.empty-state {
  text-align: center;
  padding: 60px 20px 20px;
  color: #999;
  animation: fade-in 250ms ease-out both;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.empty-icon {
  font-size: 56px;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 16px;
  color: #666;
  margin: 0 0 8px 0;
  font-weight: 500;
}

.empty-desc {
  font-size: 13px;
  color: #999;
  margin: 0 0 24px 0;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  max-width: 500px;
  margin: 0 auto;
}

.quick-tag {
  padding: 6px 14px;
  background-color: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  transition: all 150ms ease-out;
  font-family: inherit;
}

.quick-tag:hover {
  background-color: #f5f5f5;
  border-color: #ccc;
  color: #333;
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.quick-tag:active {
  transform: translateY(0);
}

.quick-tag:focus-visible {
  outline: 2px solid #07c160;
  outline-offset: 2px;
}

/* ===== 底部输入区 ===== */
.chat-footer {
  background-color: #f7f7f7;
  border-top: 1px solid #e5e5e5;
  padding: 12px 16px 8px;
  flex-shrink: 0;
}

.input-wrapper {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  max-width: 800px;
  margin: 0 auto;
}

.chat-input {
  flex: 1;
}

.chat-input :deep(.arco-textarea) {
  border-radius: 6px;
  border-color: #e5e5e5;
  background: #fff;
  font-size: 15px;
  line-height: 1.6;
  transition: border-color 150ms ease-out, box-shadow 150ms ease-out;
}

.chat-input :deep(.arco-textarea:hover) {
  border-color: #ccc;
}

.chat-input :deep(.arco-textarea-focused) {
  border-color: #07c160;
  box-shadow: 0 0 0 3px rgba(7, 193, 96, 0.12);
}

.send-btn {
  background: linear-gradient(135deg, #07c160 0%, #10b981 100%);
  border: none;
  font-weight: 500;
  transition: transform 150ms ease-out, box-shadow 150ms ease-out, opacity 150ms ease-out;
}

.send-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 8px rgba(7, 193, 96, 0.25);
}

.send-btn:active {
  transform: translateY(0);
}

.send-btn:focus-visible {
  outline: 2px solid #07c160;
  outline-offset: 2px;
}

.send-btn[disabled] {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.footer-hint {
  text-align: center;
  font-size: 11px;
  color: #bbb;
  margin: 6px 0 0 0;
}

.fallback-hint {
  margin-top: 8px;
  padding: 6px 10px;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 4px;
  font-size: 12px;
  color: #d46b08;
  display: flex;
  align-items: center;
  gap: 6px;
}

.fallback-icon {
  font-size: 14px;
}

/* ===== 响应式 ===== */
@media (max-width: 640px) {
  .chat-header {
    height: 52px;
    padding: 0 12px;
  }

  .bot-avatar,
  .msg-avatar {
    width: 36px;
    height: 36px;
  }

  .avatar--bot {
    font-size: 20px;
  }

  .header-title {
    font-size: 15px;
  }

  .chat-body {
    padding: 12px 8px;
  }

  .msg-row {
    gap: 8px;
    margin-bottom: 14px;
  }

  .msg-bubble {
    max-width: 75%;
    padding: 8px 12px;
    font-size: 14px;
  }

  .chat-footer {
    padding: 10px 10px 6px;
  }

  .input-wrapper {
    gap: 8px;
  }
}

/* ===== Reduced Motion ===== */
@media (prefers-reduced-motion: reduce) {
  .msg-row,
  .empty-state,
  .streaming-dots,
  .typing-dots span {
    animation: none;
  }

  .quick-tag:hover,
  .send-btn:hover {
    transform: none;
  }

  .chat-body {
    scroll-behavior: auto;
  }

  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
</style>
