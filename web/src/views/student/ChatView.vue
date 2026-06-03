<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { Send, Sparkles, BrainCircuit, Lightbulb, Plus, Trash2, Edit2, X, MessageSquare } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiChatApi } from '../../api/modules/ai_chat'
import type { ConversationOut, MessageOut } from '../../api/modules/ai_chat'
import { memoryApi } from '../../api/modules/memory'
import type { StudentMemoryOut } from '../../api/modules/memory'
import request from '../../api/request'

// Active states
const conversations = ref<ConversationOut[]>([])
const activeConv = ref<ConversationOut | null>(null)
const messages = ref<MessageOut[]>([])
const messageInput = ref('')
const loading = ref(false)
const listLoading = ref(false)

// Context checkboxes
const contextOptions = ref({
  include_memory: true,
  include_todos: true,
  include_tasks: true,
  include_calendar: true,
  include_knowledge: false
})

// Editing title state
const editingId = ref<string | null>(null)
const editingTitle = ref('')

// Scroll helper
const messagesContainer = ref<HTMLElement | null>(null)
const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// Fetch conversations
const fetchConversations = async (selectFirst = true) => {
  listLoading.value = true
  try {
    const res = await aiChatApi.listConversations({ page_size: 50 })
    conversations.value = res.data?.items || []
    
    if (selectFirst && conversations.value.length > 0) {
      handleSelectConversation(conversations.value[0])
    }
  } catch (err) {
    console.warn("Failed to fetch conversations. Loading fallback.")
    // Mock conversations
    conversations.value = [
      { id: '1', title: '关于 Transformer 的讨论', type: 'student_chat', message_count: 3, created_at: '', updated_at: '' },
      { id: '2', title: '文献阅读与大纲梳理', type: 'student_chat', message_count: 2, created_at: '', updated_at: '' }
    ]
    if (selectFirst) {
      handleSelectConversation(conversations.value[0])
    }
  } finally {
    listLoading.value = false
  }
}

// Select session
const handleSelectConversation = async (conv: ConversationOut) => {
  activeConv.value = conv
  messages.value = []
  loading.value = false
  
  try {
    const res = await aiChatApi.listMessages(conv.id)
    messages.value = res.data?.items || []
    scrollToBottom()
  } catch (err) {
    // Mock messages fallback
    if (conv.id === '1') {
      messages.value = [
        { id: 'm1', conversation_id: conv.id, role: 'assistant', content: '你好！我是你的专属 AI 伴学助手。今天需要我帮你拆解任务、整理学习待办，还是围绕知识库进行深度问答？', created_at: '' },
        { id: 'm2', conversation_id: conv.id, role: 'user', content: '我这周需要写好研究报告的框架，感觉无从下手。', created_at: '' },
        { id: 'm3', conversation_id: conv.id, role: 'assistant', content: '没问题，我们来一步步拆解。写好一份研究报告框架，我们可以分为以下四个阶段：\n\n1. **确定核心论点与背景**：明确研究要解决的核心问题是什么。\n2. **设计逻辑架构**：一般包含：引言、背景与相关工作、方法论设计、核心实验/分析、结论与未来展望。\n3. **拆解模块细节**：为每一章细化三级提纲（如 1.1, 1.2 等）。\n4. **时间规划**：根据你 4 天后需要提交大纲的倒数日，我建议你今天下午先写好第 1-2 章，明天上午完成最难的方法论部分。\n\n需要我现在为你生成一个基于 Markdown 的标准大纲模板吗？', created_at: '' }
      ]
    } else {
      messages.value = [
        { id: 'm4', conversation_id: conv.id, role: 'assistant', content: '关于你的文献任务，有什么进展吗？我们可以整理出一个核心重点列表。', created_at: '' }
      ]
    }
    scrollToBottom()
  }
}

// Create new session
const handleCreateConversation = async () => {
  try {
    const res = await aiChatApi.createConversation({ title: '新对话', type: 'student_chat' })
    const newConv = res.data
    conversations.value.unshift(newConv)
    handleSelectConversation(newConv)
    ElMessage.success('新建会话成功')
  } catch (err) {
    const mockId = Date.now().toString()
    const mockConv: ConversationOut = {
      id: mockId,
      title: `新对话 (${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`,
      type: 'student_chat',
      message_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    }
    conversations.value.unshift(mockConv)
    handleSelectConversation(mockConv)
  }
}

// Rename conversation
const startRename = (conv: ConversationOut) => {
  editingId.value = conv.id
  editingTitle.value = conv.title
}

const saveRename = async (conv: ConversationOut) => {
  if (!editingTitle.value.trim()) return
  try {
    await aiChatApi.updateConversationTitle(conv.id, editingTitle.value.trim())
    conv.title = editingTitle.value.trim()
    editingId.value = null
    ElMessage.success('重命名成功')
  } catch (err) {
    conv.title = editingTitle.value.trim()
    editingId.value = null
  }
}

// Delete conversation
const handleDeleteConversation = async (conv: ConversationOut) => {
  try {
    await ElMessageBox.confirm('确认删除该对话会话及所有消息历史吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    try {
      await aiChatApi.deleteConversation(conv.id)
    } catch (e) {
      // Allow mock delete
    }

    conversations.value = conversations.value.filter(c => c.id !== conv.id)
    if (activeConv.value?.id === conv.id) {
      activeConv.value = conversations.value.length > 0 ? conversations.value[0] : null
      if (activeConv.value) {
        handleSelectConversation(activeConv.value)
      } else {
        messages.value = []
      }
    }
    ElMessage.success('会话已删除')
  } catch (cancel) {
    // Cancel delete
  }
}

// Send Message stream handler
const handleSend = async () => {
  if (!messageInput.value.trim() || !activeConv.value) return
  
  const userText = messageInput.value.trim()
  messageInput.value = ''
  
  // Add user message to UI
  const userMsg: MessageOut = {
    id: `temp-u-${Date.now()}`,
    conversation_id: activeConv.value.id,
    role: 'user',
    content: userText,
    created_at: new Date().toISOString()
  }
  messages.value.push(userMsg)
  scrollToBottom()

  // Add temp assistant message for typing stream
  const assistantMsgId = `temp-a-${Date.now()}`
  const assistantMsg = ref<MessageOut>({
    id: assistantMsgId,
    conversation_id: activeConv.value.id,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  })
  
  loading.value = true
  
  try {
    let hasReceivedChunk = false
    await aiChatApi.sendMessageStream(
      activeConv.value.id,
      userText,
      contextOptions.value,
      // onChunk
      (text) => {
        if (!hasReceivedChunk) {
          hasReceivedChunk = true
          // Push assistant card once streaming starts
          messages.value.push(assistantMsg.value)
        }
        assistantMsg.value.content += text
        scrollToBottom()
      },
      // onDone
      () => {
        loading.value = false
        // Reload history messages to replace temp ids with real DB ids
        if (activeConv.value) {
          aiChatApi.listMessages(activeConv.value.id).then(res => {
            messages.value = res.data?.items || messages.value
          }).catch(() => {})
        }
      },
      // onError
      (err) => {
        loading.value = false
        console.error(err)
        ElMessage.error('模型呼叫发生故障，请检查 API Key 配置或网络。')
        
        // Mock stream fallback for demo preview
        if (!hasReceivedChunk) {
          messages.value.push(assistantMsg.value)
        }
        assistantMsg.value.content = `[伴学演示回复] 收到你的问题：“${userText}”。系统在本地检测到网络配置限制，暂时切换为离线模拟响应。我们提取到你短期内正在聚焦「准备毕业论文大纲」和「动态规划算法」。在进行本项工作时，我建议你把任务进行颗粒化拆解，并在日历中添加 2 个番茄钟日程。`
        scrollToBottom()
      }
    )
  } catch (err) {
    loading.value = false
  }
}

// Memory states
const studentId = ref<string>('')
const shortTermMemories = ref<StudentMemoryOut[]>([])
const longTermMemories = ref<StudentMemoryOut[]>([])
const memoriesLoading = ref(false)

const loadStudentProfileAndMemories = async () => {
  try {
    memoriesLoading.value = true
    const profileRes = await request.get('/auth/me')
    const userId = profileRes.data?.id
    if (userId) {
      studentId.value = userId
      const memoryRes = await memoryApi.getStudentMemory(userId)
      shortTermMemories.value = memoryRes.data?.short_term || []
      longTermMemories.value = memoryRes.data?.long_term || []
    }
  } catch (err) {
    console.warn("Failed to load user profile or memories. Using fallback.")
    shortTermMemories.value = [
      { id: 'm-s1', memory_type: 'short_term', category: 'focus', content: '聚焦: 动态规划算法与神经网络推导', confidence: 0.8, created_at: '', updated_at: '', status: 'active' },
      { id: 'm-s2', memory_type: 'short_term', category: 'focus', content: '准备: 毕业设计开题大纲', confidence: 0.9, created_at: '', updated_at: '', status: 'active' }
    ]
    longTermMemories.value = [
      { id: 'm-l1', memory_type: 'long_term', category: 'learning_preference', content: '偏好系统视频学习', confidence: 0.85, created_at: '', updated_at: '', status: 'active' },
      { id: 'm-l2', memory_type: 'long_term', category: 'study_habit', content: '任务估时容易偏低', confidence: 0.70, created_at: '', updated_at: '', status: 'active' },
      { id: 'm-l3', memory_type: 'long_term', category: 'interest_area', content: '擅长项目驱动模式', confidence: 0.65, created_at: '', updated_at: '', status: 'active' }
    ]
  } finally {
    memoriesLoading.value = false
  }
}

const handleDeleteMemory = async (memoryId: string) => {
  try {
    await ElMessageBox.confirm('是否删除该学情记忆条目？这将影响 AI 伴学助手的个性化建议精度。', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    if (studentId.value && !memoryId.startsWith('m-')) {
      await memoryApi.deleteStudentMemory(studentId.value, memoryId)
    }
    
    shortTermMemories.value = shortTermMemories.value.filter(m => m.id !== memoryId)
    longTermMemories.value = longTermMemories.value.filter(m => m.id !== memoryId)
    ElMessage.success('记忆条目已成功删除')
  } catch (err) {
    if (err !== 'cancel') {
      ElMessage.error('删除记忆条目失败')
    }
  }
}

const quickPrompts = [
  '帮我拆解今日任务',
  '生成论文大纲模板',
  '检查知识库关于“神经网络”'
]

const useQuickPrompt = (prompt: string) => {
  messageInput.value = prompt
  handleSend()
}

onMounted(() => {
  fetchConversations()
  loadStudentProfileAndMemories()
})
</script>

<template>
  <div class="flex h-[calc(100vh-8.5rem)] bg-white dark:bg-zinc-950 rounded-lg border border-gray-200 dark:border-zinc-800 overflow-hidden relative shadow-sm">
    
    <!-- Sidebar: Conversation list -->
    <div class="w-56 h-full border-r border-gray-200 dark:border-zinc-800 bg-gray-50/50 dark:bg-zinc-900/10 flex flex-col flex-shrink-0">
      <div class="p-3">
        <button
          @click="handleCreateConversation"
          class="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-[11px] rounded transition-colors"
        >
          <Plus class="w-3.5 h-3.5" />
          <span>新建伴学对话</span>
        </button>
      </div>

      <!-- Scrollable list -->
      <div class="flex-1 overflow-y-auto px-2 space-y-0.5" v-loading="listLoading">
        <div
          v-for="conv in conversations"
          :key="conv.id"
          @click="handleSelectConversation(conv)"
          class="group flex items-center justify-between p-2 rounded text-xs cursor-pointer select-none transition-colors"
          :class="activeConv?.id === conv.id
            ? 'bg-gray-100 dark:bg-zinc-900 text-gray-900 dark:text-zinc-50 font-medium'
            : 'text-gray-600 dark:text-zinc-400 hover:bg-gray-50 dark:hover:bg-zinc-900/40 hover:text-gray-900 dark:hover:text-zinc-200'"
        >
          <div class="flex items-center space-x-2 min-w-0 flex-1">
            <MessageSquare class="w-3.5 h-3.5 text-gray-400 dark:text-zinc-500 flex-shrink-0" />
            
            <!-- Title / Input edit mode -->
            <input
              v-if="editingId === conv.id"
              v-model="editingTitle"
              @keydown.enter.stop="saveRename(conv)"
              @blur="saveRename(conv)"
              @click.stop
              class="w-full bg-white dark:bg-zinc-800 px-1 border border-blue-500 rounded focus:outline-none"
            />
            <span v-else class="truncate text-[11px]">{{ conv.title }}</span>
          </div>

          <!-- Actions -->
          <div class="flex space-x-0.5 opacity-0 group-hover:opacity-100 transition-opacity ml-1.5" v-if="editingId !== conv.id">
            <button
              @click.stop="startRename(conv)"
              class="p-0.5 hover:bg-gray-200 dark:hover:bg-zinc-800 rounded text-gray-400 hover:text-gray-700 dark:hover:text-zinc-200"
            >
              <Edit2 class="w-3 h-3" />
            </button>
            <button
              @click.stop="handleDeleteConversation(conv)"
              class="p-0.5 hover:bg-gray-200 dark:hover:bg-zinc-800 rounded text-gray-400 hover:text-red-500"
            >
              <Trash2 class="w-3 h-3" />
            </button>
          </div>
        </div>

        <div v-if="conversations.length === 0 && !listLoading" class="text-center py-8 text-[11px] text-gray-400">
          暂无历史对话
        </div>
      </div>
    </div>

    <!-- Center Column: Active Chat Area -->
    <div class="flex-1 flex flex-col h-full bg-white dark:bg-zinc-950 min-w-0">
      
      <!-- Messages List -->
      <div
        ref="messagesContainer"
        class="flex-1 overflow-y-auto p-6 space-y-6"
      >
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="flex"
          :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
        >
          <!-- Message Card -->
          <div
            class="max-w-2xl p-4 rounded-lg text-xs leading-relaxed"
            :class="msg.role === 'user'
              ? 'bg-gray-900 dark:bg-zinc-100 text-white dark:text-zinc-900 rounded-tr-none shadow-sm'
              : 'bg-gray-50 dark:bg-zinc-900 text-gray-800 dark:text-zinc-200 rounded-tl-none border border-gray-100 dark:border-zinc-800/40'"
          >
            <!-- Header for assistant -->
            <div v-if="msg.role === 'assistant'" class="flex items-center space-x-1.5 mb-1.5 text-[10px] text-gray-400 dark:text-zinc-500 font-medium">
              <Sparkles class="w-3.5 h-3.5 text-blue-600 dark:text-blue-500" />
              <span>AI 伴学助手</span>
            </div>
            
            <div class="whitespace-pre-wrap font-normal leading-normal select-text">{{ msg.content }}</div>
          </div>
        </div>

        <!-- AI Streaming Loader -->
        <div v-if="loading && messages.length > 0 && messages[messages.length - 1].role === 'user'" class="flex justify-start">
          <div class="max-w-2xl p-4 rounded-lg bg-gray-50 dark:bg-zinc-900 text-gray-400 rounded-tl-none border border-gray-100 dark:border-zinc-800/40 text-[10px] flex items-center space-x-2">
            <span class="w-1.5 h-1.5 bg-blue-600 rounded-full animate-ping"></span>
            <span>伴学助手正在思考并调阅记忆库中...</span>
          </div>
        </div>

        <div v-if="!activeConv" class="h-full flex flex-col items-center justify-center text-center space-y-4">
          <BrainCircuit class="w-8 h-8 text-gray-300 dark:text-zinc-700" />
          <div class="space-y-1">
            <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">开启你的第一条伴学对话</h3>
            <p class="text-[10px] text-gray-400">选择侧边栏会话或点击新建会话按钮与伴学助手沟通。</p>
          </div>
        </div>
      </div>

      <!-- Bottom controls & input form -->
      <div v-if="activeConv" class="p-6 bg-white dark:bg-zinc-950 border-t border-gray-100 dark:border-zinc-800/80 space-y-4">
        
        <!-- Context integration toggles -->
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-gray-400 select-none pb-1 border-b border-gray-50 dark:border-zinc-900/50">
          <span class="font-medium text-gray-500">上下文关联:</span>
          
          <label class="flex items-center space-x-1.5 cursor-pointer hover:text-gray-600 dark:hover:text-zinc-300">
            <input type="checkbox" v-model="contextOptions.include_memory" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-3 h-3" />
            <span>智能学情记忆 (Memory)</span>
          </label>

          <label class="flex items-center space-x-1.5 cursor-pointer hover:text-gray-600 dark:hover:text-zinc-300">
            <input type="checkbox" v-model="contextOptions.include_todos" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-3 h-3" />
            <span>今日待办 (TODO)</span>
          </label>

          <label class="flex items-center space-x-1.5 cursor-pointer hover:text-gray-600 dark:hover:text-zinc-300">
            <input type="checkbox" v-model="contextOptions.include_tasks" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-3 h-3" />
            <span>导师下发任务</span>
          </label>

          <label class="flex items-center space-x-1.5 cursor-pointer hover:text-gray-600 dark:hover:text-zinc-300">
            <input type="checkbox" v-model="contextOptions.include_calendar" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500 w-3 h-3" />
            <span>日历计划日程</span>
          </label>
        </div>

        <!-- Quick prompts list -->
        <div class="flex flex-wrap gap-2">
          <button
            v-for="p in quickPrompts"
            :key="p"
            @click="useQuickPrompt(p)"
            class="px-2.5 py-0.5 bg-gray-50 dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded text-[10px] text-gray-500 dark:text-zinc-400 hover:border-gray-900 dark:hover:border-zinc-100 hover:text-gray-900 dark:hover:text-zinc-100 transition-colors"
          >
            {{ p }}
          </button>
        </div>

        <!-- Input Box -->
        <form @submit.prevent="handleSend" class="flex items-center space-x-3 w-full border border-gray-200 dark:border-zinc-800 rounded bg-gray-50 dark:bg-zinc-900 focus-within:border-gray-900 dark:focus-within:border-zinc-300 transition-all p-1.5 shadow-sm">
          <input
            v-model="messageInput"
            type="text"
            placeholder="向伴学助手提问，关联个人学情背景..."
            class="flex-1 bg-transparent border-0 outline-none text-xs text-gray-900 dark:text-zinc-50 placeholder-gray-400 pl-2 focus:ring-0"
            :disabled="loading"
          />
          <button
            type="submit"
            class="w-7 h-7 rounded bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 flex items-center justify-center transition-all transform active:scale-95 flex-shrink-0"
            :disabled="loading || !messageInput.trim()"
          >
            <Send class="w-3 h-3" />
          </button>
        </form>
      </div>

    </div>

    <!-- Right Column: Memory Drawer -->
    <div class="w-64 h-full bg-gray-50/30 dark:bg-zinc-900/10 p-5 flex flex-col overflow-y-auto border-l border-gray-200 dark:border-zinc-800 flex-shrink-0">
      <div class="flex items-center space-x-2 mb-4 pb-2 border-b border-gray-150 dark:border-zinc-800">
        <BrainCircuit class="w-4 h-4 text-gray-600 dark:text-zinc-400" />
        <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">AI 学情记忆画像</h3>
      </div>

      <!-- Content blocks -->
      <div class="space-y-5" v-loading="memoriesLoading">
        <!-- Short term focus -->
        <div class="space-y-2">
          <h4 class="text-[10px] font-semibold text-gray-400 dark:text-zinc-500 uppercase tracking-wider">短期关注 (Focus)</h4>
          <div class="flex flex-wrap gap-1.5" v-if="shortTermMemories.length > 0">
            <span 
              v-for="m in shortTermMemories" 
              :key="m.id"
              class="px-2 py-0.5 bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/50 text-blue-700 dark:text-blue-400 text-[10px] rounded flex items-center space-x-1"
            >
              <span>{{ m.content }}</span>
              <button @click.stop="handleDeleteMemory(m.id)" class="text-blue-400 hover:text-blue-600 dark:hover:text-blue-300">
                <X class="w-2.5 h-2.5" />
              </button>
            </span>
          </div>
          <div v-else class="text-[10px] text-gray-450 dark:text-zinc-500 italic">暂无近期关注焦点</div>
        </div>

        <!-- Long term habits -->
        <div class="space-y-2.5">
          <h4 class="text-[10px] font-semibold text-gray-400 dark:text-zinc-500 uppercase tracking-wider">长期习惯 (Habits)</h4>
          
          <div class="space-y-2" v-if="longTermMemories.length > 0">
            <div 
              v-for="m in longTermMemories" 
              :key="m.id"
              class="p-2.5 bg-white dark:bg-zinc-900 border border-gray-100 dark:border-zinc-850 rounded space-y-1 relative group/item"
            >
              <button 
                @click.stop="handleDeleteMemory(m.id)" 
                class="absolute top-1.5 right-1.5 opacity-0 group-hover/item:opacity-100 transition-opacity p-0.5 hover:bg-gray-150 dark:hover:bg-zinc-800 rounded text-gray-400 hover:text-red-500"
              >
                <X class="w-3 h-3" />
              </button>
              
              <div class="flex items-center justify-between text-[10px] font-medium pr-4">
                <span class="truncate">{{ m.content }}</span>
                <span class="text-blue-600 dark:text-blue-500 font-semibold flex-shrink-0 ml-1">{{ Math.round(m.confidence * 100) }}% 置信</span>
              </div>
              <div class="w-full h-1 bg-gray-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div class="h-full bg-gray-900 dark:bg-zinc-300 rounded-full" :style="{ width: `${m.confidence * 100}%` }"></div>
              </div>
            </div>
          </div>
          <div v-else class="text-[10px] text-gray-450 dark:text-zinc-500 italic">暂无长期习惯画像</div>
        </div>

        <!-- AI Tips -->
        <div class="p-3 bg-gray-50 dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded flex items-start space-x-2">
          <Lightbulb class="w-4 h-4 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
          <p class="text-[10px] text-gray-500 dark:text-zinc-400 leading-normal">
            伴学分析：你目前已开启 AI 智能记忆画像关联。每次你提问时，若选中“智能学情记忆”上下文，助手都将带入这些学习偏好与关注重点。
          </p>
        </div>
      </div>
    </div>

  </div>
</template>
