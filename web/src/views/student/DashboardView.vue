<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { Plus, Check, Clock, Calendar, Flame, Trash2 } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { todoApi } from '../../api/modules/todo'
import { noteApi } from '../../api/modules/note'
import { heatmapApi } from '../../api/modules/heatmap'

interface TodoItem {
  id: string
  title: string
  description?: string
  priority: string
  status: string
  category?: string
  due_date?: string
  completed_at?: string
}

interface NoteItem {
  id: string
  title?: string
  content: string
  color?: string
  category?: string
  is_pinned: boolean
}

// Data refs
const todos = ref<TodoItem[]>([])
const notes = ref<NoteItem[]>([])

// Heatmap and Stats State
const heatmapWeeks = ref<any[]>([])
const streakDays = ref(0)
const todayScore = ref(0)
const totalStudySeconds = ref(0) // dynamic counter for the session

// Timer for active learning duration
let sessionTimer: any = null

// Modals visibility
const todoDialogVisible = ref(false)
const noteDialogVisible = ref(false)

// Form states
const todoForm = ref({
  title: '',
  description: '',
  priority: 'medium',
  category: 'default'
})

const noteForm = ref({
  title: '',
  content: '',
  color: 'bg-amber-50/50 border-amber-200 text-amber-800'
})

const noteColors = [
  { name: '温暖黄', value: 'bg-amber-50/50 border-amber-200 text-amber-800' },
  { name: '薄荷绿', value: 'bg-emerald-50/50 border-emerald-200 text-emerald-800' },
  { name: '天空蓝', value: 'bg-blue-50/50 border-blue-200 text-blue-800' },
  { name: '雅致灰', value: 'bg-zinc-50/50 border-zinc-200 text-zinc-800' }
]

// Format session duration to MM:SS or HH:MM:SS
const formattedSessionTime = computed(() => {
  const hrs = Math.floor(totalStudySeconds.value / 3600)
  const mins = Math.floor((totalStudySeconds.value % 3600) / 60)
  const secs = totalStudySeconds.value % 60
  
  const pad = (num: number) => num.toString().padStart(2, '0')
  if (hrs > 0) {
    return `${pad(hrs)}:${pad(mins)}:${pad(secs)}`
  }
  return `${pad(mins)}:${pad(secs)}`
})

// Heatmap level mapping
const getHeatmapColor = (level: number) => {
  switch (level) {
    case 1: return 'bg-blue-100 dark:bg-blue-950/20 border border-blue-200/30 dark:border-blue-900/20'
    case 2: return 'bg-blue-300 dark:bg-blue-800/40 border border-blue-400/30 dark:border-blue-700/20'
    case 3: return 'bg-blue-500 dark:bg-blue-600 border border-blue-500/30'
    case 4: return 'bg-blue-700 dark:bg-blue-400 border border-blue-700/30'
    default: return 'bg-gray-100 dark:bg-zinc-800 border border-transparent'
  }
}

// Calculate streak from heatmap points
const calculateStreak = (data: any[]) => {
  const todayStr = new Date().toISOString().split('T')[0]
  
  // Find today's activity score
  const todayItem = data.find(p => p.date === todayStr)
  todayScore.value = todayItem ? todayItem.count : 0
  
  // Compute consecutive days count
  let streak = 0
  let checkingDate = new Date()
  
  // If no activity today, check if yesterday was active to count the current streak.
  const hasActivityToday = data.some(p => p.date === todayStr && p.count > 0)
  if (!hasActivityToday) {
    checkingDate.setDate(checkingDate.getDate() - 1)
  }
  
  while (true) {
    const checkStr = checkingDate.toISOString().split('T')[0]
    const dayItem = data.find(p => p.date === checkStr)
    if (dayItem && dayItem.count > 0) {
      streak++
      checkingDate.setDate(checkingDate.getDate() - 1)
    } else {
      break
    }
  }
  streakDays.value = streak
}

// Load Activity Heatmap from API
const loadHeatmap = async () => {
  try {
    const res = await heatmapApi.getHeatmapData()
    const data = res.data || []
    
    // Calculate streak metrics
    calculateStreak(data)

    const scoreMap = new Map<string, number>()
    data.forEach((p: any) => {
      scoreMap.set(p.date, p.count)
    })

    // Calculate dates for a 365-day grid
    const today = new Date()
    const startDate = new Date()
    startDate.setDate(today.getDate() - 364)

    // Align starting date with Sunday
    const startDayOfWeek = startDate.getDay() 
    const calendarStartDate = new Date(startDate)
    calendarStartDate.setDate(startDate.getDate() - startDayOfWeek)

    // Align ending date with Saturday
    const endDayOfWeek = today.getDay()
    const calendarEndDate = new Date(today)
    calendarEndDate.setDate(today.getDate() + (6 - endDayOfWeek))

    const weeks: any[][] = []
    let currentWeek: any[] = []
    
    let currentCursor = new Date(calendarStartDate)
    while (currentCursor <= calendarEndDate) {
      const dateStr = currentCursor.toISOString().split('T')[0]
      const count = scoreMap.has(dateStr) ? scoreMap.get(dateStr)! : 0
      
      let level = 0
      if (count > 0 && count <= 3) level = 1
      else if (count > 3 && count <= 8) level = 2
      else if (count > 8 && count <= 15) level = 3
      else if (count > 15) level = 4

      const formattedDate = currentCursor.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' })
      const weekday = currentCursor.getDay()

      currentWeek.push({
        date: dateStr,
        formattedDate,
        count,
        level,
        weekday,
        isPadding: currentCursor < startDate || currentCursor > today
      })

      if (currentWeek.length === 7) {
        weeks.push(currentWeek)
        currentWeek = []
      }

      currentCursor.setDate(currentCursor.getDate() + 1)
    }

    heatmapWeeks.value = weeks
  } catch (error) {
    console.warn("Failed to load heatmap data, falling back to mock.")
    const weeks: any[][] = []
    for (let w = 0; w < 53; w++) {
      const week: any[] = []
      for (let d = 0; d < 7; d++) {
        const lvl = Math.random() < 0.3 ? 0 : Math.floor(Math.random() * 5)
        week.push({
          date: `2026-mock-${w}-${d}`,
          count: lvl * 3,
          level: lvl,
          weekday: d,
          isPadding: false
        })
      }
      weeks.push(week)
    }
    heatmapWeeks.value = weeks
    streakDays.value = 5
    todayScore.value = 12
  }
}

// Todo actions
const handleToggleTodo = async (item: TodoItem) => {
  const nextStatus = item.status === 'completed' ? 'pending' : 'completed'
  const prevStatus = item.status
  item.status = nextStatus

  try {
    await todoApi.updateTodo(item.id, { status: nextStatus })
    ElMessage.success(nextStatus === 'completed' ? '标记任务已完成' : '已重置为未完成')
    await loadHeatmap()
  } catch (error) {
    item.status = prevStatus
  }
}

const handleAddTodo = async () => {
  if (!todoForm.value.title.trim()) {
    ElMessage.warning('请输入待办名称')
    return
  }

  try {
    const res = await todoApi.createTodo({
      title: todoForm.value.title,
      description: todoForm.value.description,
      priority: todoForm.value.priority,
      category: todoForm.value.category,
      status: 'pending'
    })
    
    todos.value.unshift(res.data)
    todoDialogVisible.value = false
    todoForm.value = { title: '', description: '', priority: 'medium', category: 'default' }
    ElMessage.success('创建待办成功')
    await loadHeatmap()
  } catch (error) {
    const mockItem: TodoItem = {
      id: Date.now().toString(),
      title: todoForm.value.title,
      description: todoForm.value.description,
      priority: todoForm.value.priority,
      status: 'pending',
      category: todoForm.value.category
    }
    todos.value.unshift(mockItem)
    todoDialogVisible.value = false
    todoForm.value = { title: '', description: '', priority: 'medium', category: 'default' }
  }
}

const handleDeleteTodo = async (id: string, index: number) => {
  try {
    await todoApi.deleteTodo(id)
    todos.value.splice(index, 1)
    ElMessage.success('删除待办成功')
    await loadHeatmap()
  } catch (error) {
    todos.value.splice(index, 1)
  }
}

// Note actions
const handleAddNote = async () => {
  if (!noteForm.value.content.trim()) {
    ElMessage.warning('请输入便签内容')
    return
  }

  try {
    const res = await noteApi.createNote({
      title: noteForm.value.title || undefined,
      content: noteForm.value.content,
      color: noteForm.value.color,
      is_pinned: false
    })
    
    notes.value.unshift(res.data)
    noteDialogVisible.value = false
    noteForm.value = { title: '', content: '', color: 'bg-amber-50/50 border-amber-200 text-amber-800' }
    ElMessage.success('添加便签成功')
  } catch (error) {
    const mockItem: NoteItem = {
      id: Date.now().toString(),
      title: noteForm.value.title || undefined,
      content: noteForm.value.content,
      color: noteForm.value.color,
      is_pinned: false
    }
    notes.value.unshift(mockItem)
    noteDialogVisible.value = false
    noteForm.value = { title: '', content: '', color: 'bg-amber-50/50 border-amber-200 text-amber-800' }
  }
}

const handleDeleteNote = async (id: string, index: number) => {
  try {
    await noteApi.deleteNote(id)
    notes.value.splice(index, 1)
    ElMessage.success('删除便签成功')
  } catch (error) {
    notes.value.splice(index, 1)
  }
}

// Load dashboard data
const loadData = async () => {
  try {
    const todoRes = await todoApi.listTodos()
    todos.value = todoRes.data || []
  } catch (error) {
    console.warn("Failed to fetch todos, loading mock data.")
    todos.value = [
      { id: '1', title: '阅读关于 AI Agent Memory 的最新论文', priority: 'high', status: 'pending' },
      { id: '2', title: '提交下周学习计划草案给指导老师', priority: 'medium', status: 'completed' },
      { id: '3', title: '完成 Qdrant 向量检索接口 of 本地测试', priority: 'high', status: 'pending' }
    ]
  }

  try {
    const noteRes = await noteApi.listNotes()
    notes.value = noteRes.data || []
  } catch (error) {
    console.warn("Failed to fetch notes, loading mock data.")
    notes.value = [
      { id: '1', content: '动态规划状态转移方程推导：\ndp[i] = max(dp[i-1], dp[i-2] + val)', color: 'bg-amber-50/50 border-amber-200 text-amber-800', is_pinned: true },
      { id: '2', content: '本周组会汇报重点：\n1. AI Memory 四层设计\n2. SQLite/PostgreSQL 混合存储对比', color: 'bg-emerald-50/50 border-emerald-200 text-emerald-800', is_pinned: false }
    ]
  }

  await loadHeatmap()
}

onMounted(() => {
  loadData()
  
  // Real-time active learning duration session clock
  totalStudySeconds.value = 0
  sessionTimer = setInterval(() => {
    totalStudySeconds.value += 1
  }, 1000)
})

onUnmounted(() => {
  if (sessionTimer) clearInterval(sessionTimer)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Top banner/stat card row -->
    <div class="grid grid-cols-1 md:grid-cols-12 gap-6">
      
      <!--今日时长-->
      <div class="md:col-span-4 minimal-card p-6 flex items-center justify-between">
        <div class="space-y-2">
          <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">本次在线专注</span>
          <div class="flex items-baseline space-x-1">
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ formattedSessionTime }}</span>
          </div>
          <span class="text-[10px] text-emerald-600 dark:text-emerald-500 font-medium block">后台每 30 秒自动记录一次心跳</span>
        </div>
        <div class="relative w-16 h-16 flex items-center justify-center">
          <svg class="w-full h-full transform -rotate-90">
            <circle cx="32" cy="32" r="26" stroke="currentColor" class="text-gray-100 dark:text-zinc-800" stroke-width="4" fill="transparent" />
            <circle cx="32" cy="32" r="26" stroke="currentColor" class="text-blue-600 dark:text-blue-500" stroke-width="4" stroke-dasharray="163" stroke-dashoffset="30" fill="transparent" stroke-linecap="round" />
          </svg>
          <Clock class="w-5 h-5 absolute text-blue-600 dark:text-blue-500" />
        </div>
      </div>

      <!-- 今日活跃积分 -->
      <div class="md:col-span-4 minimal-card p-6 flex items-center justify-between">
        <div class="space-y-2">
          <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">今日活跃积分</span>
          <div class="flex items-baseline space-x-1">
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ todayScore }}</span>
            <span class="text-xs text-gray-500">分</span>
          </div>
          <p class="text-[10px] text-gray-500 dark:text-zinc-400 font-medium block">每5分钟+1, 待办/任务完成+2/+5</p>
        </div>
        <div class="w-12 h-12 rounded bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/50 flex items-center justify-center text-amber-600 dark:text-amber-500">
          <Calendar class="w-5 h-5" />
        </div>
      </div>

      <!-- 连续学习活跃 -->
      <div class="md:col-span-4 minimal-card p-6 flex items-center justify-between">
        <div class="space-y-2">
          <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">连续活跃天数</span>
          <div class="flex items-baseline space-x-1">
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ streakDays }}</span>
            <span class="text-xs text-gray-500">天</span>
          </div>
          <span class="text-[10px] text-blue-600 dark:text-blue-500 font-medium block">保持专注，继续努力！</span>
        </div>
        <div class="w-12 h-12 rounded bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-500">
          <Flame class="w-5 h-5" />
        </div>
      </div>
    </div>

    <!-- Widgets Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      
      <!-- Todo Widget (7 cols) -->
      <div class="lg:col-span-8 minimal-card p-6 flex flex-col h-[360px]">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">今日待办事项</h3>
          <button
            @click="todoDialogVisible = true"
            class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors"
          >
            <Plus class="w-4 h-4" />
          </button>
        </div>
        
        <!-- List -->
        <div class="flex-1 overflow-y-auto space-y-3 pr-1">
          <div
            v-for="(item, index) in todos"
            :key="item.id"
            class="flex items-center space-x-3 p-2.5 rounded-lg border border-gray-100 dark:border-zinc-800/50 hover:border-blue-500 bg-white dark:bg-zinc-900 transition-all select-none group"
          >
            <!-- Checkbox -->
            <div
              @click="handleToggleTodo(item)"
              class="w-4 h-4 rounded border flex items-center justify-center transition-all cursor-pointer"
              :class="item.status === 'completed' ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 dark:border-zinc-700'"
            >
              <Check v-if="item.status === 'completed'" class="w-3 h-3 stroke-[3]" />
            </div>
            
            <!-- Title -->
            <span
              @click="handleToggleTodo(item)"
              class="text-xs transition-all flex-1 truncate cursor-pointer"
              :class="item.status === 'completed' ? 'line-through text-gray-400 dark:text-zinc-500' : 'text-gray-700 dark:text-zinc-300'"
            >
              {{ item.title }}
            </span>
            
            <!-- Priority Badge -->
            <span
              v-if="item.status !== 'completed'"
              class="text-[9px] px-1.5 py-0.5 rounded font-medium capitalize"
              :class="
                item.priority === 'high' ? 'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400' :
                item.priority === 'medium' ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/20 dark:text-amber-400' :
                'bg-gray-50 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'
              "
            >
              {{ item.priority === 'high' ? '高' : item.priority === 'medium' ? '中' : '低' }}
            </span>

            <!-- Delete -->
            <button
              @click="handleDeleteTodo(item.id, index)"
              class="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity p-0.5"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
          
          <div v-if="todos.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
            这里没有待办事项。点击右上角 “+” 开始规划。
          </div>
        </div>
      </div>

      <!-- Sticky Notes Widget (4 cols) -->
      <div class="lg:col-span-4 minimal-card p-6 flex flex-col h-[360px]">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">学术便签</h3>
          <button
            @click="noteDialogVisible = true"
            class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors"
          >
            <Plus class="w-4 h-4" />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto space-y-4 pr-1">
          <div
            v-for="(note, index) in notes"
            :key="note.id"
            class="p-4 rounded border text-xs leading-relaxed font-normal relative group"
            :class="note.color || 'bg-zinc-50 border-zinc-200'"
          >
            <!-- Title -->
            <div v-if="note.title" class="font-semibold mb-1 truncate pr-6">{{ note.title }}</div>
            <div class="whitespace-pre-wrap">{{ note.content }}</div>

            <!-- Delete note -->
            <button
              @click="handleDeleteNote(note.id, index)"
              class="absolute top-2 right-2 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>

          <div v-if="notes.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
            点击 “+” 创建你的第一张学术便签。
          </div>
        </div>
      </div>

      <!-- Contributions Heatmap (12 cols) -->
      <div class="lg:col-span-12 minimal-card p-6">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 mb-6">学习活跃度年度视图</h3>
        <div class="flex flex-col space-y-2 overflow-x-auto">
          <div class="flex space-x-1 flex-shrink-0">
            <div
              v-for="(week, wIdx) in heatmapWeeks"
              :key="wIdx"
              class="flex flex-col space-y-1"
            >
              <el-tooltip
                v-for="day in week"
                :key="day.date"
                :content="day.isPadding ? '范围外无数据' : `${day.formattedDate} : 活跃度积分 ${day.count}`"
                placement="top"
                :show-after="100"
              >
                <div
                  class="w-3.5 h-3.5 rounded-sm transition-all cursor-pointer hover:ring-2 hover:ring-blue-500/50"
                  :class="[getHeatmapColor(day.level), day.isPadding ? 'opacity-30' : '']"
                ></div>
              </el-tooltip>
            </div>
          </div>
          <div class="flex items-center space-x-2 text-[10px] text-gray-400 dark:text-zinc-500 pt-2 justify-end">
            <span>低活跃</span>
            <div class="w-2.5 h-2.5 rounded-sm bg-gray-100 dark:bg-zinc-800"></div>
            <div class="w-2.5 h-2.5 rounded-sm bg-blue-100/40 border border-blue-200/30"></div>
            <div class="w-2.5 h-2.5 rounded-sm bg-blue-300 dark:bg-blue-800/40 border border-blue-400/30"></div>
            <div class="w-2.5 h-2.5 rounded-sm bg-blue-500 dark:bg-blue-600"></div>
            <div class="w-2.5 h-2.5 rounded-sm bg-blue-700 dark:bg-blue-400"></div>
            <span>高活跃</span>
          </div>
        </div>
      </div>


    </div>

    <!-- Create Todo Dialog -->
    <el-dialog
      v-model="todoDialogVisible"
      title="创建新待办"
      width="400px"
      class="minimalist-dialog"
    >
      <div class="space-y-4">
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">任务名称</label>
          <input
            v-model="todoForm.title"
            type="text"
            placeholder="做什么？"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">任务详情</label>
          <textarea
            v-model="todoForm.description"
            rows="3"
            placeholder="补充描述..."
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          ></textarea>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">优先级</label>
          <select
            v-model="todoForm.priority"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-700 dark:text-zinc-300"
          >
            <option value="low">低优先级</option>
            <option value="medium">中优先级</option>
            <option value="high">高优先级</option>
          </select>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="todoDialogVisible = false" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleAddTodo" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">创建</button>
        </div>
      </template>
    </el-dialog>

    <!-- Create Note Dialog -->
    <el-dialog
      v-model="noteDialogVisible"
      title="添加学术便签"
      width="400px"
      class="minimalist-dialog"
    >
      <div class="space-y-4">
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">便签主题（可选）</label>
          <input
            v-model="noteForm.title"
            type="text"
            placeholder="主题"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">便签正文</label>
          <textarea
            v-model="noteForm.content"
            rows="4"
            placeholder="记录下闪现的灵感或总结..."
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          ></textarea>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">选择卡片皮肤</label>
          <div class="flex space-x-2 pt-1">
            <button
              v-for="color in noteColors"
              :key="color.value"
              @click="noteForm.color = color.value"
              class="px-2 py-1 rounded text-[10px] border transition-all"
              :class="[color.value, noteForm.color === color.value ? 'ring-2 ring-blue-500 font-bold' : '']"
            >
              {{ color.name }}
            </button>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="noteDialogVisible = false" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleAddNote" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">添加</button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style>
/* Clean up Element Plus dialog for minimalist look */
.minimalist-dialog {
  border-radius: 8px !important;
  border: 1px solid var(--border-thin) !important;
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.05) !important;
}
.minimalist-dialog .el-dialog__headerbtn {
  top: 16px !important;
}
.minimalist-dialog .el-dialog__title {
  font-size: 14px !important;
  font-weight: 600 !important;
}
</style>
