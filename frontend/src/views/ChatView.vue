<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Promotion } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { fetchConversations, fetchMessages, searchChatUsers, sendChatMessage } from '../api'
import { useAuthStore } from '../stores/auth'
import type { ChatMessage, ChatUser } from '../types'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const conversations = ref<ChatUser[]>([])
const directory = ref<ChatUser[]>([])
const selected = ref<ChatUser | null>(null)
const messages = ref<ChatMessage[]>([])
const query = ref('')
const draft = ref('')
const loading = ref(false)
const sending = ref(false)
const messageList = ref<HTMLElement | null>(null)
let pollTimer: ReturnType<typeof setInterval> | undefined
let searchTimer: ReturnType<typeof setTimeout> | undefined

const contacts = computed(() => query.value.trim() ? directory.value : conversations.value)

onMounted(async () => {
  await Promise.all([loadConversations(), loadDirectory()])
  const userId = typeof route.query.user === 'string' ? route.query.user : ''
  const username = typeof route.query.name === 'string' ? route.query.name : '社区用户'
  if (userId && userId !== auth.user.value?.id) await selectContact({ id: userId, username, last_message: null, last_message_at: null, unread_count: 0 })
  pollTimer = setInterval(() => void poll(), 3000)
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  if (searchTimer) clearTimeout(searchTimer)
})

watch(query, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void loadDirectory(), 250)
})

async function loadConversations(): Promise<void> {
  try {
    conversations.value = await fetchConversations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '会话加载失败')
  }
}

async function loadDirectory(): Promise<void> {
  try {
    directory.value = await searchChatUsers(query.value.trim())
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '用户列表加载失败')
  }
}

async function selectContact(contact: ChatUser): Promise<void> {
  selected.value = contact
  messages.value = []
  loading.value = true
  await router.replace({ path: '/chat', query: { user: contact.id, name: contact.username } })
  try {
    messages.value = await fetchMessages(contact.id)
    await scrollToBottom()
    await loadConversations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '消息加载失败')
  } finally {
    loading.value = false
  }
}

async function poll(): Promise<void> {
  await loadConversations()
  if (!selected.value) return
  const lastId = messages.value.at(-1)?.id ?? 0
  try {
    const incoming = await fetchMessages(selected.value.id, lastId)
    if (incoming.length) {
      messages.value.push(...incoming)
      await scrollToBottom()
    }
  } catch {
    // 短暂网络波动时保持当前会话，下一轮继续获取。
  }
}

async function send(): Promise<void> {
  const body = draft.value.trim()
  if (!selected.value || !body || sending.value) return
  sending.value = true
  try {
    const message = await sendChatMessage(selected.value.id, body)
    messages.value.push(message)
    draft.value = ''
    await scrollToBottom()
    await loadConversations()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '消息发送失败')
  } finally {
    sending.value = false
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}

function time(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
</script>

<template>
  <main class="chat-page">
    <aside class="chat-sidebar">
      <header><p class="eyebrow">MESSAGES</p><h1>聊天</h1></header>
      <div class="chat-search">
        <el-icon><Search /></el-icon>
        <input v-model="query" placeholder="搜索用户名" aria-label="搜索用户名" />
      </div>
      <p class="chat-list-label">{{ query.trim() ? '用户搜索结果' : '最近会话' }}</p>
      <div class="contact-list">
        <button
          v-for="contact in contacts"
          :key="contact.id"
          :class="['contact-item', { active: selected?.id === contact.id }]"
          @click="selectContact(contact)"
        >
          <span class="avatar">{{ contact.username.slice(0, 1).toUpperCase() }}</span>
          <span class="contact-copy"><strong>{{ contact.username }}</strong><small>{{ contact.last_message || '开始聊天' }}</small></span>
          <span v-if="contact.unread_count" class="unread-badge">{{ contact.unread_count }}</span>
        </button>
        <p v-if="contacts.length === 0" class="no-contacts">{{ query ? '没有找到用户' : '还没有会话，可搜索用户开始交流' }}</p>
      </div>
    </aside>

    <section class="conversation-panel">
      <template v-if="selected">
        <header class="conversation-header">
          <span class="avatar">{{ selected.username.slice(0, 1).toUpperCase() }}</span>
          <div><strong>{{ selected.username }}</strong><small>站内私信</small></div>
        </header>
        <div ref="messageList" v-loading="loading" class="message-list">
          <div
            v-for="message in messages"
            :key="message.id"
            :class="['message-row', { mine: message.sender_id === auth.user.value?.id }]"
          >
            <div class="message-bubble"><p>{{ message.body }}</p><time>{{ time(message.created_at) }}</time></div>
          </div>
          <p v-if="!loading && messages.length === 0" class="conversation-empty">还没有消息，打个招呼吧。</p>
        </div>
        <footer class="message-composer">
          <textarea v-model="draft" maxlength="1000" rows="2" placeholder="输入消息，Ctrl + Enter 发送" @keydown.ctrl.enter.prevent="send"></textarea>
          <el-button type="primary" :icon="Promotion" :loading="sending" :disabled="!draft.trim()" @click="send">发送</el-button>
        </footer>
      </template>
      <div v-else class="chat-empty">
        <div class="empty-icon"><el-icon><Promotion /></el-icon></div>
        <h2>选择一位用户开始交流</h2>
        <p>可以搜索社区创作者，讨论配色、尺寸和制作心得。</p>
      </div>
    </section>
  </main>
</template>
