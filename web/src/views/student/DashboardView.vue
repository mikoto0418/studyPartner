<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { Plus, Check, Clock, Calendar, Flame, Trash2, GripVertical, Save, SlidersHorizontal, BookOpen, ClipboardList } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { todoApi } from '../../api/modules/todo'
import { noteApi } from '../../api/modules/note'
import { heatmapApi } from '../../api/modules/heatmap'
import { taskApi, type StudentTask } from '../../api/modules/task'
import { authApi } from '../../api/modules/auth'
import { userApi, type UserOut } from '../../api/modules/user'

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

interface DashboardWidget {
  id: 'focus' | 'score' | 'streak' | 'tasks' | 'notes' | 'heatmap'
}

const defaultWidgets: DashboardWidget[] = [
  { id: 'focus' },
  { id: 'score' },
  { id: 'streak' },
  { id: 'tasks' },
  { id: 'notes' },
  { id: 'heatmap' }
]

const widgetLabels: Record<DashboardWidget['id'], string> = {
  focus: '本次在线专注',
  score: '今日活跃积分',
  streak: '连续活跃天数',
  tasks: '今日任务',
  notes: '学术便签',
  heatmap: '学习活跃度'
}

const widgets = ref<DashboardWidget[]>([...defaultWidgets])
const sortMode = ref(false)
const currentUser = ref<UserOut | null>(null)

const todos = ref<TodoItem[]>([])
const teacherTasks = ref<StudentTask[]>([])
const notes = ref<NoteItem[]>([])
const heatmapWeeks = ref<any[]>([])
const streakDays = ref(0)
const todayScore = ref(0)
const totalStudySeconds = ref(0)

let sessionTimer: number | undefined

const todoDialogVisible = ref(false)
const noteDialogVisible = ref(false)
const taskSubmitDialogVisible = ref(false)
const selectedTeacherTask = ref<StudentTask | null>(null)

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

const taskSubmitForm = ref({
  content: '',
  attachment_ids: ''
})

const noteColors = [
  { name: '暖黄', value: 'bg-amber-50/50 border-amber-200 text-amber-800' },
  { name: '薄荷', value: 'bg-emerald-50/50 border-emerald-200 text-emerald-800' },
  { name: '天空', value: 'bg-blue-50/50 border-blue-200 text-blue-800' },
  { name: '灰白', value: 'bg-zinc-50/50 border-zinc-200 text-zinc-800' }
]

const formattedSessionTime = computed(() => {
  const hrs = Math.floor(totalStudySeconds.value / 3600)
  const mins = Math.floor((totalStudySeconds.value % 3600) / 60)
  const secs = totalStudySeconds.value % 60
  const pad = (num: number) => num.toString().padStart(2, '0')
  return hrs > 0 ? `${pad(hrs)}:${pad(mins)}:${pad(secs)}` : `${pad(mins)}:${pad(secs)}`
})

const activeTeacherTasks = computed(() =>
  teacherTasks.value
    .filter((item) => !['completed', 'cancelled'].includes(item.status))
    .slice(0, 5)
)

const activeTodos = computed(() => todos.value.slice(0, 6))

const widgetGridClass = (id: DashboardWidget['id']) => {
  if (id === 'tasks') return 'lg:col-span-8'
  if (id === 'notes') return 'lg:col-span-4'
  if (id === 'heatmap') return 'lg:col-span-12'
  return 'lg:col-span-4'
}

const isWidgetKnown = (id: string): id is DashboardWidget['id'] => id in widgetLabels

const loadWidgetLayout = (user: UserOut) => {
  const saved = user.student_profile?.extra_info?.dashboard_widgets
  if (!Array.isArray(saved)) return

  const normalized = saved
    .filter((id: string) => isWidgetKnown(id))
    .map((id: DashboardWidget['id']) => ({ id }))

  const missing = defaultWidgets.filter((item) => !normalized.some((savedItem) => savedItem.id === item.id))
  widgets.value = [...normalized, ...missing]
}

const saveWidgetLayout = async () => {
  if (!currentUser.value?.student_profile) {
    ElMessage.warning('当前账号暂无学生档案，排序仅在本页生效')
    return
  }

  const extraInfo = {
    ...(currentUser.value.student_profile.extra_info || {}),
    dashboard_widgets: widgets.value.map((item) => item.id)
  }

  await userApi.updateStudentProfile(currentUser.value.id, { extra_info: extraInfo })
  currentUser.value.student_profile.extra_info = extraInfo
  sortMode.value = false
  ElMessage.success('首页模块顺序已保存')
}

const handleWidgetOrderChange = () => {
  if (sortMode.value) {
    ElMessage.closeAll()
    ElMessage.info('顺序已调整，点击保存排序后生效')
  }
}

const getHeatmapColor = (level: number) => {
  switch (level) {
    case 1: return 'bg-blue-100 dark:bg-blue-950/20 border border-blue-200/30 dark:border-blue-900/20'
    case 2: return 'bg-blue-300 dark:bg-blue-800/40 border border-blue-400/30 dark:border-blue-700/20'
    case 3: return 'bg-blue-500 dark:bg-blue-600 border border-blue-500/30'
    case 4: return 'bg-blue-700 dark:bg-blue-400 border border-blue-700/30'
    default: return 'bg-gray-100 dark:bg-zinc-800 border border-transparent'
  }
}

const calculateStreak = (data: any[]) => {
  const todayStr = new Date().toISOString().split('T')[0]
  const todayItem = data.find((p) => p.date === todayStr)
  todayScore.value = todayItem ? todayItem.count : 0

  let streak = 0
  const checkingDate = new Date()
  const hasActivityToday = data.some((p) => p.date === todayStr && p.count > 0)
  if (!hasActivityToday) checkingDate.setDate(checkingDate.getDate() - 1)

  while (true) {
    const checkStr = checkingDate.toISOString().split('T')[0]
    const dayItem = data.find((p) => p.date === checkStr)
    if (!dayItem || dayItem.count <= 0) break
    streak++
    checkingDate.setDate(checkingDate.getDate() - 1)
  }

  streakDays.value = streak
}

const loadHeatmap = async () => {
  try {
    const res = await heatmapApi.getHeatmapData()
    const data = res.data || []
    calculateStreak(data)

    const scoreMap = new Map<string, number>()
    data.forEach((p: any) => scoreMap.set(p.date, p.count))

    const today = new Date()
    const startDate = new Date()
    startDate.setDate(today.getDate() - 364)
    const calendarStartDate = new Date(startDate)
    calendarStartDate.setDate(startDate.getDate() - startDate.getDay())
    const calendarEndDate = new Date(today)
    calendarEndDate.setDate(today.getDate() + (6 - today.getDay()))

    const weeks: any[][] = []
    let currentWeek: any[] = []
    const cursor = new Date(calendarStartDate)

    while (cursor <= calendarEndDate) {
      const dateStr = cursor.toISOString().split('T')[0]
      const count = scoreMap.get(dateStr) || 0
      const level = count > 15 ? 4 : count > 8 ? 3 : count > 3 ? 2 : count > 0 ? 1 : 0

      currentWeek.push({
        date: dateStr,
        formattedDate: cursor.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' }),
        count,
        level,
        isPadding: cursor < startDate || cursor > today
      })

      if (currentWeek.length === 7) {
        weeks.push(currentWeek)
        currentWeek = []
      }
      cursor.setDate(cursor.getDate() + 1)
    }

    heatmapWeeks.value = weeks
  } catch (error) {
    console.warn('Failed to load heatmap data', error)
    heatmapWeeks.value = []
  }
}

const formatDate = (iso?: string) => {
  if (!iso) return '未设置'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

const openTaskSubmitDialog = (task: StudentTask) => {
  selectedTeacherTask.value = task
  taskSubmitForm.value = { content: '', attachment_ids: '' }
  taskSubmitDialogVisible.value = true
}

const handleSubmitTeacherTask = async () => {
  if (!selectedTeacherTask.value) return
  if (!taskSubmitForm.value.content.trim() && !taskSubmitForm.value.attachment_ids.trim()) {
    ElMessage.warning('请填写提交说明或附件 ID')
    return
  }

  const attachmentIds = taskSubmitForm.value.attachment_ids
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean)

  try {
    await taskApi.submitTask(selectedTeacherTask.value.id, {
      content: taskSubmitForm.value.content.trim() || undefined,
      attachment_ids: attachmentIds
    })
    taskSubmitDialogVisible.value = false
    ElMessage.success('任务已提交')
    const taskRes = await taskApi.listMyTasks()
    teacherTasks.value = taskRes.data || []
    await loadHeatmap()
  } catch (error) {
    console.warn('Failed to submit teacher task', error)
    ElMessage.error('提交任务失败，请稍后重试')
  }
}

const handleToggleTodo = async (item: TodoItem) => {
  const nextStatus = item.status === 'completed' ? 'pending' : 'completed'
  const prevStatus = item.status
  item.status = nextStatus

  try {
    await todoApi.updateTodo(item.id, { status: nextStatus })
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
    ElMessage.success('待办已创建')
    await loadHeatmap()
  } catch (error) {
    ElMessage.error('创建待办失败')
  }
}

const handleDeleteTodo = async (id: string, index: number) => {
  try {
    await todoApi.deleteTodo(id)
    todos.value.splice(index, 1)
    await loadHeatmap()
  } catch (error) {
    ElMessage.error('删除待办失败')
  }
}

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
    noteForm.value = { title: '', content: '', color: noteColors[0].value }
  } catch (error) {
    ElMessage.error('添加便签失败')
  }
}

const handleDeleteNote = async (id: string, index: number) => {
  try {
    await noteApi.deleteNote(id)
    notes.value.splice(index, 1)
  } catch (error) {
    ElMessage.error('删除便签失败')
  }
}

const loadData = async () => {
  try {
    const meRes = await authApi.getMe()
    currentUser.value = meRes.data
    if (currentUser.value) loadWidgetLayout(currentUser.value)
  } catch (error) {
    console.warn('Failed to load current user profile', error)
  }

  try {
    const todoRes = await todoApi.listTodos()
    todos.value = todoRes.data || []
  } catch (error) {
    console.warn('Failed to fetch todos', error)
  }

  try {
    const taskRes = await taskApi.listMyTasks()
    teacherTasks.value = taskRes.data || []
  } catch (error) {
    console.warn('Failed to fetch teacher tasks', error)
  }

  try {
    const noteRes = await noteApi.listNotes()
    notes.value = noteRes.data || []
  } catch (error) {
    console.warn('Failed to fetch notes', error)
  }

  await loadHeatmap()
}

onMounted(() => {
  loadData()
  sessionTimer = window.setInterval(() => {
    totalStudySeconds.value += 1
  }, 1000)
})

onUnmounted(() => {
  if (sessionTimer) clearInterval(sessionTimer)
})
</script>

<template>
  <div class="space-y-5">
    <div class="flex items-center justify-between">
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">我的仪表盘</h3>
        <p class="text-xs text-gray-400 dark:text-zinc-500 mt-1">个人待办、导师任务与学习活跃度集中管理。</p>
      </div>

      <div class="flex items-center gap-2">
        <button
          v-if="sortMode"
          @click="saveWidgetLayout"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs font-medium"
        >
          <Save class="w-3.5 h-3.5" />
          <span>保存排序</span>
        </button>
        <button
          @click="sortMode = !sortMode"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs font-medium text-gray-600 dark:text-zinc-300 hover:bg-gray-50 dark:hover:bg-zinc-800"
        >
          <SlidersHorizontal class="w-3.5 h-3.5" />
          <span>{{ sortMode ? '退出排序' : '排序模式' }}</span>
        </button>
      </div>
    </div>

    <VueDraggable
      v-model="widgets"
      class="grid grid-cols-1 lg:grid-cols-12 gap-6"
      :animation="180"
      handle=".drag-handle"
      :disabled="!sortMode"
      @end="handleWidgetOrderChange"
    >
      <section
        v-for="widget in widgets"
        :key="widget.id"
        class="relative minimal-card"
        :class="[widgetGridClass(widget.id), sortMode ? 'ring-1 ring-blue-500/30' : '']"
      >
        <button
          v-if="sortMode"
          class="drag-handle absolute right-3 top-3 z-10 p-1 rounded border border-gray-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-gray-400 cursor-grab active:cursor-grabbing"
          :title="`拖拽排序：${widgetLabels[widget.id]}`"
        >
          <GripVertical class="w-3.5 h-3.5" />
        </button>

        <div v-if="widget.id === 'focus'" class="p-6 flex items-center justify-between min-h-[158px]">
          <div class="space-y-2">
            <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">本次在线专注</span>
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ formattedSessionTime }}</span>
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

        <div v-else-if="widget.id === 'score'" class="p-6 flex items-center justify-between min-h-[158px]">
          <div class="space-y-2">
            <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">今日活跃积分</span>
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ todayScore }}<span class="ml-1 text-xs text-gray-500">分</span></span>
            <p class="text-[10px] text-gray-500 dark:text-zinc-400 font-medium">每 5 分钟 +1，待办/任务完成 +2/+5</p>
          </div>
          <div class="w-12 h-12 rounded bg-amber-50 dark:bg-amber-950/20 border border-amber-100 dark:border-amber-900/50 flex items-center justify-center text-amber-600 dark:text-amber-500">
            <Calendar class="w-5 h-5" />
          </div>
        </div>

        <div v-else-if="widget.id === 'streak'" class="p-6 flex items-center justify-between min-h-[158px]">
          <div class="space-y-2">
            <span class="text-xs text-gray-400 dark:text-zinc-500 font-medium block">连续活跃天数</span>
            <span class="text-3xl font-bold text-gray-900 dark:text-zinc-50">{{ streakDays }}<span class="ml-1 text-xs text-gray-500">天</span></span>
            <span class="text-[10px] text-blue-600 dark:text-blue-500 font-medium block">保持专注，继续努力！</span>
          </div>
          <div class="w-12 h-12 rounded bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-500">
            <Flame class="w-5 h-5" />
          </div>
        </div>

        <div v-else-if="widget.id === 'tasks'" class="p-6 flex flex-col h-[360px]">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <ClipboardList class="w-4 h-4 text-gray-500 dark:text-zinc-400" />
              <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">今日任务</h3>
            </div>
            <button
              @click="todoDialogVisible = true"
              class="p-1 rounded text-gray-400 hover:text-gray-600 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors"
              title="新增个人待办"
            >
              <Plus class="w-4 h-4" />
            </button>
          </div>

          <div class="flex-1 overflow-y-auto space-y-3 pr-1">
            <div
              v-for="item in activeTeacherTasks"
              :key="`teacher-${item.id}`"
              class="flex items-center gap-3 p-3 rounded-lg border border-blue-100 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/10"
            >
              <BookOpen class="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0" />
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-[9px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-950/40 dark:text-blue-300 font-semibold">导师任务</span>
                  <span class="text-[9px] text-gray-400">截止 {{ formatDate(item.due_date) }}</span>
                </div>
                <p class="mt-1 text-xs font-medium text-gray-800 dark:text-zinc-100 truncate">{{ item.title }}</p>
              </div>
              <span class="text-[9px] px-1.5 py-0.5 rounded font-medium"
                :class="item.priority === 'high' || item.priority === 'urgent'
                  ? 'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400'
                  : 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'"
              >
                {{ item.priority === 'urgent' ? '急' : item.priority === 'high' ? '高' : item.priority === 'medium' ? '中' : '低' }}
              </span>
              <button
                v-if="item.status === 'in_progress' || item.status === 'rejected'"
                @click="openTaskSubmitDialog(item)"
                class="rounded bg-blue-600 px-2 py-1 text-[10px] font-semibold text-white transition hover:bg-blue-500"
                title="提交导师任务"
              >
                提交
              </button>
            </div>

            <div
              v-for="(item, index) in activeTodos"
              :key="`todo-${item.id}`"
              class="flex items-center space-x-3 p-2.5 rounded-lg border border-gray-100 dark:border-zinc-800/50 hover:border-blue-500 bg-white dark:bg-zinc-900 transition-all select-none group"
            >
              <div
                @click="handleToggleTodo(item)"
                class="w-4 h-4 rounded border flex items-center justify-center transition-all cursor-pointer"
                :class="item.status === 'completed' ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300 dark:border-zinc-700'"
              >
                <Check v-if="item.status === 'completed'" class="w-3 h-3 stroke-[3]" />
              </div>

              <span
                @click="handleToggleTodo(item)"
                class="text-xs transition-all flex-1 truncate cursor-pointer"
                :class="item.status === 'completed' ? 'line-through text-gray-400 dark:text-zinc-500' : 'text-gray-700 dark:text-zinc-300'"
              >
                {{ item.title }}
              </span>

              <span
                v-if="item.status !== 'completed'"
                class="text-[9px] px-1.5 py-0.5 rounded font-medium"
                :class="item.priority === 'high'
                  ? 'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400'
                  : item.priority === 'medium'
                    ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/20 dark:text-amber-400'
                    : 'bg-gray-50 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'"
              >
                {{ item.priority === 'high' ? '高' : item.priority === 'medium' ? '中' : '低' }}
              </span>

              <button
                @click="handleDeleteTodo(item.id, index)"
                class="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity p-0.5"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>

            <div v-if="activeTeacherTasks.length === 0 && activeTodos.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
              暂无任务，点击右上角创建个人待办。
            </div>
          </div>
        </div>

        <div v-else-if="widget.id === 'notes'" class="p-6 flex flex-col h-[360px]">
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
              <div v-if="note.title" class="font-semibold mb-1 truncate pr-6">{{ note.title }}</div>
              <div class="whitespace-pre-wrap">{{ note.content }}</div>
              <button
                @click="handleDeleteNote(note.id, index)"
                class="absolute top-2 right-2 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
            <div v-if="notes.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
              点击 + 创建你的第一张学术便签。
            </div>
          </div>
        </div>

        <div v-else-if="widget.id === 'heatmap'" class="p-6">
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
                  :content="day.isPadding ? '范围外无数据' : `${day.formattedDate}：活跃积分 ${day.count}`"
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
      </section>
    </VueDraggable>

    <el-dialog v-model="taskSubmitDialogVisible" title="提交导师任务" width="460px" class="minimalist-dialog">
      <div class="space-y-4">
        <div class="rounded border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/20 dark:text-blue-300">
          {{ selectedTeacherTask?.title || '导师任务' }}
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">提交说明</label>
          <textarea
            v-model="taskSubmitForm.content"
            rows="4"
            placeholder="说明完成内容、关键结论或需要导师查看的问题"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          ></textarea>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">附件文件 ID</label>
          <textarea
            v-model="taskSubmitForm.attachment_ids"
            rows="2"
            placeholder="多个文件 ID 可用逗号或换行分隔"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"
          ></textarea>
        </div>
      </div>
      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="taskSubmitDialogVisible = false" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleSubmitTeacherTask" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">提交</button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="todoDialogVisible" title="创建个人待办" width="400px" class="minimalist-dialog">
      <div class="space-y-4">
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">任务名称</label>
          <input v-model="todoForm.title" type="text" placeholder="做什么？" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">任务详情</label>
          <textarea v-model="todoForm.description" rows="3" placeholder="补充描述..." class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"></textarea>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">优先级</label>
          <select v-model="todoForm.priority" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-700 dark:text-zinc-300">
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

    <el-dialog v-model="noteDialogVisible" title="添加学术便签" width="400px" class="minimalist-dialog">
      <div class="space-y-4">
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">便签主题</label>
          <input v-model="noteForm.title" type="text" placeholder="主题，可留空" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500" />
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">便签正文</label>
          <textarea v-model="noteForm.content" rows="4" placeholder="记录灵感或总结..." class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500"></textarea>
        </div>
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">颜色</label>
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
