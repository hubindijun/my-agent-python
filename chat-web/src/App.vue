<template>
  <div class="chat-app">
    <header class="chat-header">
      <div class="header-left">
        <div class="bot-avatar">🤖</div>
        <div class="header-info">
          <h1 class="header-title">RAG 智能问答</h1>
          <p class="header-subtitle">
            <span class="online-dot"></span>
            在线
          </p>
        </div>
      </div>
      <a-button type="text" size="small" @click="clearHistory" v-if="messages.length > 0">
        <template #icon><icon-delete /></template>
        清空记录
      </a-button>
    </header>

    <div ref="listRef" class="chat-body">
      <div v-if="messages.length === 0" class="empty-state">
        <div class="empty-icon">💬</div>
        <p class="empty-title">开始你的智能问答</p>
        <p class="empty-desc">输入问题，AI 将基于本地知识库为你解答</p>
        <div class="quick-questions">
          <span
            v-for="q in suggestions"
            :key="q"
            class="quick-tag"
            @click="quickAsk(q)"
          >
            {{ q }}
          </span>
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
          <span v-else>🤖</span>
        </div>
        <div class="msg-bubble" :class="msg.role === 'user' ? 'bubble--self' : 'bubble--bot'">
          <div v-if="msg.loading" class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <template v-else>
            {{ msg.content }}
            <span v-if="msg.streaming" class="cursor-blink"></span>
          </template>
        </div>
      </div>
    </div>

    <div class="chat-footer">
      <div class="input-wrapper">
        <a-textarea
          v-model="inputText"
          placeholder="输入问题，按 Enter 发送，Shift+Enter 换行"
          :auto-size="{ minRows: 1, maxRows: 5 }"
          :disabled="isStreaming"
          @keydown="onKeyDown"
          class="chat-input"
        />
        <a-button
          type="primary"
          :loading="isStreaming"
          :disabled="!inputText.trim()"
          @click="sendMessage"
          shape="round"
          size="large"
        >
          发送
        </a-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { IconDelete } from '@arco-design/web-vue/es/icon'

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

// sessionStorage: 刷新保留，关闭浏览器/标签页丢失
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

    // 从响应头拿 session_id（SSE 的 header 也可以读）
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
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') {
            botMsg.streaming = false
          } else if (data.startsWith('[ERROR]')) {
            throw new Error(data.slice(7))
          } else if (data.startsWith('[SESSION] ')) {
            const sid = data.slice(10).trim()
            if (sid) sessionId.value = sid
          } else {
            botMsg.content += data
            await scrollToBottom()
          }
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
      messages.value = []
      sessionStorage.removeItem(STORAGE_KEY)
      sessionStorage.removeItem(SESSION_KEY)
      sessionId.value = ''
      // 通知后端清空
      try {
        await fetch('/chat/history', {
          method: 'DELETE',
          headers: sessionId.value ? { 'X-Session-Id': sessionId.value } : {},
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
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bot-avatar {
  width: 40px;
  height: 40px;
  border-radius: 6px;
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
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
}

/* ===== 聊天区 ===== */
.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 12px;
  background-color: #ededed;
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
  max-width: 800px;
  margin-left: auto;
  margin-right: auto;
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
  background: linear-gradient(135deg, #67c23a 0%, #95d475 100%);
  font-size: 22px;
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

/* 光标闪烁 */
.cursor-blink {
  display: inline-block;
  width: 2px;
  height: 16px;
  background-color: #666;
  margin-left: 2px;
  vertical-align: middle;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* loading 动画 */
.typing-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #bbb;
  animation: typing 1.4s infinite;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-6px);
    opacity: 1;
  }
}

/* ===== 空状态 ===== */
.empty-state {
  text-align: center;
  padding: 60px 20px 20px;
  color: #999;
}

.empty-icon {
  font-size: 56px;
  margin-bottom: 16px;
}

.empty-title {
  font-size: 16px;
  color: #666;
  margin: 0 0 8px 0;
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
  transition: all 0.2s;
}

.quick-tag:hover {
  background-color: #f5f5f5;
  border-color: #ccc;
  color: #333;
}

/* ===== 底部输入区 ===== */
.chat-footer {
  background-color: #f7f7f7;
  border-top: 1px solid #e5e5e5;
  padding: 12px 16px;
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
}
</style>
