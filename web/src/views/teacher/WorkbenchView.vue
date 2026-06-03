<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Sparkles, Send, Brain, Users, ClipboardCheck, Clock, RefreshCw } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { userApi } from '../../api/modules/user'
import { aiChatApi } from '../../api/modules/ai_chat'
import type { ConversationOut, MessageOut } from '../../api/modules/ai_chat'

// State
const studentsCount = ref(0)
const pendingSubmissions = ref<any[]>([])
const loadingStats = ref(false)

// AI Chat Assistant State
const conversation = ref<ConversationOut | null>(null)
const messages = ref<MessageOut[]>([])
const inputMessage = ref('')
const isResponding = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

// Mock prompt suggestions
const quickPrompts = [
  "请分析近期学生普遍反馈的Transformer难点，帮我给个讲解思路",
  "帮我草拟一份《AI Agent记忆机制设计》的研究任务，设定P0优先级要求",
  "如何针对学习活跃度偏低的学生，制定有效的日常代办辅导方案？"
]

// Initialize stats
const loadStats = async () => {
  loadingStats.value = true
  try {
    const res = await userApi.listUsers({ role_code: 'student', page_size: 1 })
    studentsCount.value = res.data?.total || 0
  } catch (error) {
    studentsCount.value = 8 // Fallback
  } finally {
    loadingStats.value = false
  }

  // Populate mock pending task submissions for the teacher to review
  pendingSubmissions.value = [
    { id: 'sub-1', student_name: '李自学', task_title: '文献阅读与研究方法梳理', submitted_at: '今天 10:24' },
    { id: 'sub-2', student_name: '王科研', task_title: '毕业论文大纲草拟', submitted_at: '昨天 17:15' }
  ]
}

// Setup AI Teaching Assistant Conversation
const setupAiAssistant = async () => {
  try {
    // Look for existing teacher assistant conversation
    const listRes = await aiChatApi.listConversations({ type: 'teacher_assistant', page_size: 1 })
    const list = listRes.data?.items || []
    
    if (list.length > 0) {
      conversation.value = list[0]
      loadMessages(list[0].id)
    } else {
      // Create a new one
      const createRes = await aiChatApi.createConversation({
        title: '教师智脑助教',
        type: 'teacher_assistant'
      })
      conversation.value = createRes.data
    }
  } catch (err) {
    console.error("Failed to setup AI Teaching Assistant", err)
  }
}

// Load messages
const loadMessages = async (convId: string) => {
  try {
    const res = await aiChatApi.listMessages(convId, { page_size: 50 })
    messages.value = res.data?.items || []
    scrollToBottom()
  } catch (err) {
    console.error(err)
  }
}

// Send Message
const handleSendMessage = async (customText?: string) => {
  const textToSend = customText || inputMessage.value.trim()
  if (!textToSend || !conversation.value || isResponding.value) return

  if (!customText) {
    inputMessage.value = ''
  }

  // Optimistic UI push
  const tempUserMsg: MessageOut = {
    id: `temp-u-${Date.now()}`,
    conversation_id: conversation.value.id,
    role: 'user',
    content: textToSend,
    created_at: new Date().toISOString()
  }
  messages.value.push(tempUserMsg)
  scrollToBottom()

  // Prepare Assistant buffer
  const tempAssistantMsg = ref<MessageOut>({
    id: `temp-a-${Date.now()}`,
    conversation_id: conversation.value.id,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  })
  messages.value.push(tempAssistantMsg.value)
  isResponding.value = true

  // Stream call
  await aiChatApi.sendMessageStream(
    conversation.value.id,
    textToSend,
    {
      include_memory: false,
      include_todos: false,
      include_tasks: false,
      include_calendar: false,
      include_knowledge: false
    },
    (chunk) => {
      tempAssistantMsg.value.content += chunk
      scrollToBottom()
    },
    () => {
      isResponding.value = false
      // Load real messages to fetch IDs
      loadMessages(conversation.value!.id)
    },
    (err) => {
      isResponding.value = false
      ElMessage.error("AI 助教思考中断，请重试")
      console.error(err)
    }
  )
}

// Scroll chat helper
const scrollToBottom = () => {
  setTimeout(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  }, 50)
}

onMounted(() => {
  loadStats()
  setupAiAssistant()
})
</script>

<template>
  <div class="h-[calc(100vh-8rem)] flex items-stretch gap-6 -m-4 p-4 overflow-hidden">
    
    <!-- Left Workspace Dashboard Grid (7 cols) -->
    <div class="flex-1 flex flex-col gap-6 overflow-y-auto pr-2">
      <!-- 1. Row stats -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-6 flex-shrink-0">
        <!-- 指导学生 -->
        <div class="minimal-card p-5 flex items-center justify-between">
          <div class="space-y-1">
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">指导学生总数</span>
            <span class="text-2xl font-bold text-gray-800 dark:text-zinc-50 font-mono">{{ studentsCount }}</span>
          </div>
          <div class="w-10 h-10 rounded bg-blue-50 dark:bg-blue-950/20 flex items-center justify-center text-blue-600 dark:text-blue-500 border border-blue-100/30">
            <Users class="w-4 h-4" />
          </div>
        </div>

        <!-- 待批改 -->
        <div class="minimal-card p-5 flex items-center justify-between">
          <div class="space-y-1">
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">待批改任务数</span>
            <span class="text-2xl font-bold text-amber-600 dark:text-amber-500 font-mono">{{ pendingSubmissions.length }}</span>
          </div>
          <div class="w-10 h-10 rounded bg-amber-50 dark:bg-amber-950/20 flex items-center justify-center text-amber-600 dark:text-amber-500 border border-amber-100/30">
            <ClipboardCheck class="w-4 h-4" />
          </div>
        </div>

        <!-- 本周活跃 -->
        <div class="minimal-card p-5 flex items-center justify-between">
          <div class="space-y-1">
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">今日活跃学生</span>
            <span class="text-2xl font-bold text-emerald-600 dark:text-emerald-500 font-mono">4</span>
          </div>
          <div class="w-10 h-10 rounded bg-emerald-50 dark:bg-emerald-950/20 flex items-center justify-center text-emerald-600 dark:text-emerald-500 border border-emerald-100/30">
            <Sparkles class="w-4 h-4" />
          </div>
        </div>

        <!-- 课程大纲 -->
        <div class="minimal-card p-5 flex items-center justify-between">
          <div class="space-y-1">
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">人均本周学时</span>
            <span class="text-2xl font-bold text-indigo-600 dark:text-indigo-500 font-mono">14.8</span>
          </div>
          <div class="w-10 h-10 rounded bg-indigo-50 dark:bg-indigo-950/20 flex items-center justify-center text-indigo-600 dark:text-indigo-500 border border-indigo-100/30">
            <Clock class="w-4 h-4" />
          </div>
        </div>
      </div>

      <!-- 2. Pending Submissions to Grade -->
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col min-h-[300px]">
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between flex-shrink-0">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <ClipboardCheck class="w-4 h-4 text-blue-600" />
            <span>近期提交待批改作业列表</span>
          </h4>
          <span class="text-[10px] text-gray-400">请前往「任务管理」页面做具体评分批改</span>
        </div>

        <!-- List -->
        <div class="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
          <div
            v-for="sub in pendingSubmissions"
            :key="sub.id"
            class="p-4 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/30 dark:bg-zinc-950/20 flex items-center justify-between text-xs hover:border-blue-500/50 transition-all"
          >
            <div class="space-y-1">
              <span class="font-bold text-gray-800 dark:text-zinc-200 block">{{ sub.task_title }}</span>
              <div class="flex items-center space-x-2 text-[10px] text-gray-400">
                <span class="font-medium text-gray-600 dark:text-zinc-300">提交学生: {{ sub.student_name }}</span>
                <span>&bull;</span>
                <span>提交时间: {{ sub.submitted_at }}</span>
              </div>
            </div>

            <router-link
              to="/teacher/tasks"
              class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold shadow-sm transition-colors"
            >
              去批改
            </router-link>
          </div>

          <div v-if="pendingSubmissions.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
            太棒了！目前没有待批改的作业。
          </div>
        </div>
      </div>
    </div>

    <!-- Right AI Assistant Sideboard (5 cols equivalent width) -->
    <div class="w-96 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-full flex-shrink-0">
      <!-- Title -->
      <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between flex-shrink-0">
        <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
          <Brain class="w-4 h-4 text-purple-500 animate-pulse" />
          <span>AI 教师教学辅助中心</span>
        </h4>
        <span class="text-[9px] bg-purple-50 dark:bg-purple-950/40 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded font-bold">
          智脑助教
        </span>
      </div>

      <!-- Chat messages flow -->
      <div
        ref="chatContainer"
        class="flex-1 overflow-y-auto my-4 space-y-4 pr-1 text-xs"
      >
        <div class="p-3 bg-gray-50 dark:bg-zinc-950 rounded-lg border border-gray-100 dark:border-zinc-800/50 leading-relaxed text-gray-500">
          <p class="font-semibold text-purple-600 mb-1 flex items-center space-x-1">
            <Sparkles class="w-3.5 h-3.5" />
            <span>欢迎使用教师辅导智脑助手！</span>
          </p>
          我是您的专属教学 AI，您可以直接向我询问学生的学情分析、教学计划制定或者任务设计。
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          class="flex flex-col space-y-1"
          :class="msg.role === 'user' ? 'items-end' : 'items-start'"
        >
          <span class="text-[9px] text-gray-400 px-1 font-mono">
            {{ msg.role === 'user' ? '您' : 'AI 助教' }}
          </span>
          <div
            class="p-3 rounded-lg max-w-[85%] leading-relaxed whitespace-pre-wrap"
            :class="
              msg.role === 'user'
                ? 'bg-blue-600 text-white rounded-tr-none'
                : 'bg-gray-100 dark:bg-zinc-800 text-gray-800 dark:text-zinc-200 rounded-tl-none border border-gray-200/50 dark:border-zinc-700/50'
            "
          >
            {{ msg.content }}
          </div>
        </div>

        <div v-if="isResponding && messages[messages.length-1]?.content === ''" class="flex items-center space-x-2 text-gray-400 px-2">
          <RefreshCw class="w-3.5 h-3.5 animate-spin" />
          <span>正在思考...</span>
        </div>
      </div>

      <!-- Prompt recommendations panel -->
      <div v-if="messages.length <= 1" class="pb-3 space-y-2 flex-shrink-0">
        <span class="text-[9px] text-gray-400 block font-medium">推荐教学提问 Prompt：</span>
        <div class="flex flex-col gap-1.5">
          <button
            v-for="(pr, idx) in quickPrompts"
            :key="idx"
            @click="handleSendMessage(pr)"
            class="text-left p-2 rounded bg-gray-50 hover:bg-purple-50/50 dark:bg-zinc-950 dark:hover:bg-zinc-900 text-[10px] text-gray-500 hover:text-purple-700 dark:hover:text-purple-400 border border-gray-100 dark:border-zinc-800 transition-all truncate"
          >
            {{ pr }}
          </button>
        </div>
      </div>

      <!-- Send Input block -->
      <div class="flex items-center space-x-2 flex-shrink-0">
        <input
          v-model="inputMessage"
          @keyup.enter="handleSendMessage()"
          type="text"
          placeholder="问问助教关于大纲或研究任务..."
          :disabled="isResponding"
          class="flex-1 px-3 py-2.5 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded-lg text-xs focus:outline-none focus:border-purple-500 disabled:opacity-50"
        />
        <button
          @click="handleSendMessage()"
          :disabled="isResponding || !inputMessage.trim()"
          class="p-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg transition-colors focus:outline-none disabled:opacity-50"
        >
          <Send class="w-4 h-4" />
        </button>
      </div>
    </div>

  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 4px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
