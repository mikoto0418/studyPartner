<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { Send, Sparkles, BrainCircuit, Lightbulb, Plus, Trash2, Edit2, X, MessageSquare, RefreshCw } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { aiChatApi } from '../../api/modules/ai_chat'
import type { ConversationOut, MessageOut } from '../../api/modules/ai_chat'
import { memoryApi } from '../../api/modules/memory'
import type { StudentMemoryOut } from '../../api/modules/memory'
import request from '../../api/request'

const escapeHtml = (value: string) => {
  const entities: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }

  return value.replace(/[&<>"']/g, (char) => entities[char])
}

const sanitizeUrl = (value: string) => {
  const trimmed = value.trim()

  if (/^(https?:|mailto:)/i.test(trimmed) || trimmed.startsWith('/')) {
    return trimmed
  }

  return '#'
}

const renderInlineMarks = (value: string) => value
  .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  .replace(/__([^_]+)__/g, '<strong>$1</strong>')
  .replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  .replace(/_([^_\n]+)_/g, '<em>$1</em>')

const renderInlineMarkdown = (value: string) => {
  const codeParts = value.split(/(`[^`]*`)/g)

  return codeParts.map((part) => {
    if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
      return `<code>${escapeHtml(part.slice(1, -1))}</code>`
    }

    let html = ''
    let cursor = 0
    const linkPattern = /\[([^\]]+)\]\(([^)\s]+)\)/g
    let match: RegExpExecArray | null

    while ((match = linkPattern.exec(part)) !== null) {
      html += renderInlineMarks(escapeHtml(part.slice(cursor, match.index)))
      const label = renderInlineMarks(escapeHtml(match[1]))
      const href = escapeHtml(sanitizeUrl(match[2]))
      html += `<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`
      cursor = match.index + match[0].length
    }

    html += renderInlineMarks(escapeHtml(part.slice(cursor)))
    return html
  }).join('')
}

const isTableDivider = (value: string) => /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(value)

const isBlockStart = (value: string, index: number, lines: string[]) => {
  const trimmed = value.trim()

  return /^```/.test(trimmed)
    || /^#{1,4}\s+/.test(trimmed)
    || /^>\s?/.test(trimmed)
    || /^[-*+]\s+/.test(trimmed)
    || /^\d+\.\s+/.test(trimmed)
    || /^-{3,}$/.test(trimmed)
    || (index + 1 < lines.length && value.includes('|') && isTableDivider(lines[index + 1]))
}

const parseTableRow = (value: string) => value
  .trim()
  .replace(/^\|/, '')
  .replace(/\|$/, '')
  .split('|')
  .map((cell) => renderInlineMarkdown(cell.trim()))

const renderListItem = (value: string) => {
  const taskMatch = value.match(/^\[( |x|X)\]\s+(.*)$/)

  if (!taskMatch) {
    return renderInlineMarkdown(value)
  }

  const checked = taskMatch[1].toLowerCase() === 'x'
  return `<span class="md-task ${checked ? 'md-task--checked' : ''}"><span class="md-task-box"></span><span>${renderInlineMarkdown(taskMatch[2])}</span></span>`
}

const renderMessageContent = (source: string) => {
  const lines = source.replace(/\r\n/g, '\n').split('\n')
  const blocks: string[] = []
  let index = 0

  while (index < lines.length) {
    const line = lines[index]
    const trimmed = line.trim()

    if (!trimmed) {
      index += 1
      continue
    }

    const fence = trimmed.match(/^```([\w-]+)?/)
    if (fence) {
      const codeLines: string[] = []
      index += 1

      while (index < lines.length && !lines[index].trim().startsWith('```')) {
        codeLines.push(lines[index])
        index += 1
      }

      if (index < lines.length) index += 1

      const language = fence[1] ? `<span>${escapeHtml(fence[1])}</span>` : ''
      blocks.push(`<pre>${language}<code>${escapeHtml(codeLines.join('\n'))}</code></pre>`)
      continue
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/)
    if (heading) {
      const level = Math.min(heading[1].length + 1, 5)
      blocks.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`)
      index += 1
      continue
    }

    if (/^-{3,}$/.test(trimmed)) {
      blocks.push('<hr>')
      index += 1
      continue
    }

    if (trimmed.startsWith('>')) {
      const quoteLines: string[] = []

      while (index < lines.length && lines[index].trim().startsWith('>')) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ''))
        index += 1
      }

      blocks.push(`<blockquote>${quoteLines.map(renderInlineMarkdown).join('<br>')}</blockquote>`)
      continue
    }

    if (line.includes('|') && index + 1 < lines.length && isTableDivider(lines[index + 1])) {
      const headers = parseTableRow(line)
      const rows: string[][] = []
      index += 2

      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(parseTableRow(lines[index]))
        index += 1
      }

      blocks.push([
        '<div class="md-table-wrap"><table>',
        `<thead><tr>${headers.map((cell) => `<th>${cell}</th>`).join('')}</tr></thead>`,
        `<tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody>`,
        '</table></div>'
      ].join(''))
      continue
    }

    if (/^[-*+]\s+/.test(trimmed)) {
      const items: string[] = []

      while (index < lines.length && /^[-*+]\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*+]\s+/, ''))
        index += 1
      }

      blocks.push(`<ul>${items.map((item) => `<li>${renderListItem(item)}</li>`).join('')}</ul>`)
      continue
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = []

      while (index < lines.length && /^\d+\.\s+/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s+/, ''))
        index += 1
      }

      blocks.push(`<ol>${items.map((item) => `<li>${renderInlineMarkdown(item)}</li>`).join('')}</ol>`)
      continue
    }

    const paragraph: string[] = []

    while (index < lines.length && lines[index].trim() && !isBlockStart(lines[index], index, lines)) {
      paragraph.push(lines[index])
      index += 1
    }

    blocks.push(`<p>${paragraph.map(renderInlineMarkdown).join('<br>')}</p>`)
  }

  return blocks.join('')
}

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
    console.warn('Failed to fetch conversations', err)
    conversations.value = []
    activeConv.value = null
    messages.value = []
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
    console.warn('Failed to load conversation messages', err)
    messages.value = []
    ElMessage.error('加载会话消息失败')
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
    console.warn('Failed to create conversation', err)
    ElMessage.error('新建会话失败')
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
    console.warn('Failed to rename conversation', err)
    ElMessage.error('重命名失败')
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
    
    await aiChatApi.deleteConversation(conv.id)
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
        if (activeConv.value) {
          handleSelectConversation(activeConv.value)
        }
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
const summarizingMemory = ref(false)

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
    console.warn('Failed to load user profile or memories', err)
    shortTermMemories.value = []
    longTermMemories.value = []
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
    
    if (studentId.value) {
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

const todayString = () => new Date().toISOString().slice(0, 10)

const handleSummarizeMemory = async () => {
  if (!studentId.value || summarizingMemory.value) return
  summarizingMemory.value = true
  try {
    await memoryApi.generateDailyReview({ date: todayString() })
    await loadStudentProfileAndMemories()
    ElMessage.success('今日复盘与 Memory 已同步生成')
  } catch (err) {
    console.warn('Failed to summarize memory', err)
  } finally {
    summarizingMemory.value = false
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
            
            <div
              class="student-chat-markdown select-text"
              :class="msg.role === 'user' ? 'student-chat-markdown--user' : 'student-chat-markdown--assistant'"
              v-html="renderMessageContent(msg.content)"
            ></div>
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
      <div class="flex items-center justify-between gap-2 mb-4 pb-2 border-b border-gray-150 dark:border-zinc-800">
        <div class="flex items-center space-x-2 min-w-0">
          <BrainCircuit class="w-4 h-4 text-gray-600 dark:text-zinc-400" />
          <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50 truncate">AI 学情记忆画像</h3>
        </div>
        <button
          @click="handleSummarizeMemory"
          :disabled="summarizingMemory || !studentId"
          class="inline-flex h-6 w-6 flex-shrink-0 items-center justify-center rounded border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-50 disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800"
          title="手动总结今日 Memory"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="summarizingMemory ? 'animate-spin' : ''" />
        </button>
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

<style scoped>
.student-chat-markdown {
  max-width: 100%;
  font-size: 12px;
  line-height: 1.75;
  overflow-wrap: anywhere;
}

.student-chat-markdown :deep(*) {
  letter-spacing: 0;
}

.student-chat-markdown :deep(> * + *) {
  margin-top: 0.72rem;
}

.student-chat-markdown :deep(p) {
  margin: 0;
}

.student-chat-markdown :deep(h2),
.student-chat-markdown :deep(h3),
.student-chat-markdown :deep(h4),
.student-chat-markdown :deep(h5) {
  position: relative;
  margin: 0.85rem 0 0.42rem;
  padding-left: 0.65rem;
  font-weight: 700;
  line-height: 1.35;
}

.student-chat-markdown :deep(h2) {
  font-size: 0.92rem;
}

.student-chat-markdown :deep(h3) {
  font-size: 0.84rem;
}

.student-chat-markdown :deep(h4),
.student-chat-markdown :deep(h5) {
  font-size: 0.76rem;
}

.student-chat-markdown :deep(h2::before),
.student-chat-markdown :deep(h3::before),
.student-chat-markdown :deep(h4::before),
.student-chat-markdown :deep(h5::before) {
  content: "";
  position: absolute;
  left: 0;
  top: 0.22em;
  width: 3px;
  height: 1em;
  border-radius: 999px;
  background: #2563eb;
}

.student-chat-markdown :deep(strong) {
  font-weight: 700;
}

.student-chat-markdown :deep(em) {
  color: #64748b;
  font-style: normal;
}

.dark .student-chat-markdown :deep(em) {
  color: #a1a1aa;
}

.student-chat-markdown :deep(a) {
  color: #2563eb;
  font-weight: 650;
  text-decoration: none;
  border-bottom: 1px solid rgba(37, 99, 235, 0.28);
}

.student-chat-markdown :deep(a:hover) {
  border-bottom-color: rgba(37, 99, 235, 0.72);
}

.student-chat-markdown :deep(ul),
.student-chat-markdown :deep(ol) {
  margin: 0.48rem 0 0;
  padding-left: 1.05rem;
}

.student-chat-markdown :deep(li) {
  padding-left: 0.12rem;
  margin-top: 0.34rem;
}

.student-chat-markdown :deep(li::marker) {
  color: #2563eb;
  font-weight: 700;
}

.student-chat-markdown :deep(blockquote) {
  margin: 0.7rem 0 0;
  padding: 0.62rem 0.78rem;
  border-left: 3px solid rgba(37, 99, 235, 0.75);
  border-radius: 0 6px 6px 0;
  background: rgba(37, 99, 235, 0.055);
  color: #475569;
}

.dark .student-chat-markdown :deep(blockquote) {
  background: rgba(37, 99, 235, 0.12);
  color: #d4d4d8;
}

.student-chat-markdown :deep(code) {
  padding: 0.1rem 0.3rem;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.05);
  color: #0f172a;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
}

.dark .student-chat-markdown :deep(code) {
  border-color: rgba(82, 82, 91, 0.9);
  background: rgba(9, 9, 11, 0.72);
  color: #e4e4e7;
}

.student-chat-markdown :deep(pre) {
  position: relative;
  margin: 0.78rem 0 0;
  padding: 0.95rem;
  overflow-x: auto;
  border: 1px solid rgba(203, 213, 225, 0.75);
  border-radius: 8px;
  background: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.dark .student-chat-markdown :deep(pre) {
  border-color: rgba(63, 63, 70, 0.9);
  background: #09090b;
}

.student-chat-markdown :deep(pre > span) {
  display: inline-block;
  margin-bottom: 0.55rem;
  padding: 0.12rem 0.42rem;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 0.62rem;
  font-weight: 700;
}

.dark .student-chat-markdown :deep(pre > span) {
  background: rgba(37, 99, 235, 0.16);
  color: #60a5fa;
}

.student-chat-markdown :deep(pre code) {
  display: block;
  padding: 0;
  border: 0;
  background: transparent;
  color: #334155;
  line-height: 1.7;
  white-space: pre;
}

.dark .student-chat-markdown :deep(pre code) {
  color: #d4d4d8;
}

.student-chat-markdown :deep(.md-table-wrap) {
  margin-top: 0.78rem;
  max-width: 100%;
  overflow-x: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.dark .student-chat-markdown :deep(.md-table-wrap) {
  border-color: #27272a;
  background: #09090b;
}

.student-chat-markdown :deep(table) {
  width: 100%;
  border-collapse: collapse;
  min-width: 360px;
}

.student-chat-markdown :deep(th),
.student-chat-markdown :deep(td) {
  padding: 0.52rem 0.7rem;
  border-bottom: 1px solid #f1f5f9;
  text-align: left;
  vertical-align: top;
}

.dark .student-chat-markdown :deep(th),
.dark .student-chat-markdown :deep(td) {
  border-bottom-color: #27272a;
}

.student-chat-markdown :deep(th) {
  background: #f8fafc;
  color: #334155;
  font-size: 0.68rem;
  font-weight: 700;
}

.dark .student-chat-markdown :deep(th) {
  background: #18181b;
  color: #e4e4e7;
}

.student-chat-markdown :deep(tr:last-child td) {
  border-bottom: 0;
}

.student-chat-markdown :deep(hr) {
  margin: 0.9rem 0;
  border: 0;
  border-top: 1px solid #e5e7eb;
}

.dark .student-chat-markdown :deep(hr) {
  border-top-color: #27272a;
}

.student-chat-markdown :deep(.md-task) {
  display: inline-flex;
  align-items: flex-start;
  gap: 0.45rem;
}

.student-chat-markdown :deep(.md-task-box) {
  position: relative;
  top: 0.33rem;
  width: 0.82rem;
  height: 0.82rem;
  flex: 0 0 auto;
  border: 1px solid #cbd5e1;
  border-radius: 3px;
  background: #fff;
}

.student-chat-markdown :deep(.md-task--checked .md-task-box) {
  border-color: #2563eb;
  background: #2563eb;
}

.student-chat-markdown :deep(.md-task--checked .md-task-box::after) {
  content: "";
  position: absolute;
  left: 0.22rem;
  top: 0.09rem;
  width: 0.26rem;
  height: 0.48rem;
  border: solid #fff;
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}

.student-chat-markdown--user {
  color: inherit;
}

.student-chat-markdown--user :deep(h2::before),
.student-chat-markdown--user :deep(h3::before),
.student-chat-markdown--user :deep(h4::before),
.student-chat-markdown--user :deep(h5::before) {
  background: rgba(255, 255, 255, 0.82);
}

.student-chat-markdown--user :deep(a),
.student-chat-markdown--user :deep(li::marker) {
  color: currentColor;
}

.student-chat-markdown--user :deep(a) {
  border-bottom-color: rgba(255, 255, 255, 0.45);
}

.student-chat-markdown--user :deep(code) {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  color: inherit;
}

.dark .student-chat-markdown--user :deep(a) {
  border-bottom-color: rgba(9, 9, 11, 0.35);
}

.dark .student-chat-markdown--user :deep(h2::before),
.dark .student-chat-markdown--user :deep(h3::before),
.dark .student-chat-markdown--user :deep(h4::before),
.dark .student-chat-markdown--user :deep(h5::before) {
  background: rgba(9, 9, 11, 0.82);
}
</style>
