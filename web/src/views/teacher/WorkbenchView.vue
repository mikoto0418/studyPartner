<script setup lang="ts">
import { computed, nextTick, onMounted, ref, type Component } from 'vue'
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  GitBranch,
  LineChart,
  MessageSquare,
  RefreshCw,
  Send,
  Sparkles,
  Target,
  Users,
  Wand2
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { aiChatApi } from '../../api/modules/ai_chat'
import { learningPathApi } from '../../api/modules/learning_path'
import { taskApi, type TaskDetails, type TaskOut } from '../../api/modules/task'
import type { ConversationOut, MessageOut } from '../../api/modules/ai_chat'
import type { ClassOut, ClassOverviewOut } from '../../api/modules/learning_path'
import { localizeMemorySummaryText } from '../../utils/memoryLabels'

interface PendingSubmissionItem {
  id: string
  task_title: string
  student_name: string
  submitted_at: string
  created_at: string
}

interface DashboardMetricCard {
  label: string
  value: number | string
  unit: string
  hint: string
  icon: Component
  tone: 'blue' | 'emerald' | 'red' | 'amber' | 'indigo'
}

interface AgentAction {
  title: string
  description: string
  icon: Component
  prompt: string
}

const classes = ref<ClassOut[]>([])
const selectedClassId = ref('')
const overview = ref<ClassOverviewOut | null>(null)
const teacherTasks = ref<TaskOut[]>([])
const pendingSubmissions = ref<PendingSubmissionItem[]>([])
const loadingDashboard = ref(false)
const loadingOverview = ref(false)

const conversation = ref<ConversationOut | null>(null)
const messages = ref<MessageOut[]>([])
const inputMessage = ref('')
const isResponding = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const selectedClass = computed(() => classes.value.find((item) => item.id === selectedClassId.value) || null)
const metrics = computed(() => overview.value?.metrics || {})
const trend = computed(() => overview.value?.trend || [])
const insights = computed(() => overview.value?.insights || [])
const unresolvedInsights = computed(() => insights.value.filter((item) => item.status !== 'resolved' && item.status !== 'dismissed'))
const highPriorityInsights = computed(() => unresolvedInsights.value.filter((item) => item.severity === 'high').slice(0, 3))
const visibleInsights = computed(() => unresolvedInsights.value.slice(0, 4))
const attentionStudents = computed(() => (overview.value?.attention_students || []).slice(0, 5))
const recentPaths = computed(() => (overview.value?.recent_paths || []).slice(0, 4))
const pendingStudentCount = computed(() => new Set(pendingSubmissions.value.map((item) => item.student_name)).size)
const todoCount = computed(() => pendingSubmissions.value.length + unresolvedInsights.value.length)
const currentClassName = computed(() => overview.value?.class_info.name || selectedClass.value?.name || '未选择班级')
const memorySummary = computed(() => localizeMemorySummaryText(overview.value?.memory_summary?.summary))
const maxTrendProgress = computed(() => Math.max(...trend.value.map((item) => Number(item.avg_progress || 0)), 1))

const toneClassMap: Record<DashboardMetricCard['tone'], { icon: string; value: string; soft: string }> = {
  blue: {
    icon: 'border-blue-100 bg-blue-50 text-blue-600 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300',
    value: 'text-blue-700 dark:text-blue-300',
    soft: 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300'
  },
  emerald: {
    icon: 'border-emerald-100 bg-emerald-50 text-emerald-600 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300',
    value: 'text-emerald-700 dark:text-emerald-300',
    soft: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300'
  },
  red: {
    icon: 'border-red-100 bg-red-50 text-red-600 dark:border-red-900/50 dark:bg-red-950/20 dark:text-red-300',
    value: 'text-red-700 dark:text-red-300',
    soft: 'bg-red-50 text-red-700 dark:bg-red-950/30 dark:text-red-300'
  },
  amber: {
    icon: 'border-amber-100 bg-amber-50 text-amber-600 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300',
    value: 'text-amber-700 dark:text-amber-300',
    soft: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
  },
  indigo: {
    icon: 'border-indigo-100 bg-indigo-50 text-indigo-600 dark:border-indigo-900/50 dark:bg-indigo-950/20 dark:text-indigo-300',
    value: 'text-indigo-700 dark:text-indigo-300',
    soft: 'bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300'
  }
}

const displayNameOf = (item: { display_name?: string; nickname?: string; username?: string }) => {
  return item.display_name || item.nickname?.trim() || item.username || '未设置姓名'
}

const formatDate = (iso?: string) => {
  if (!iso) return '未设置'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

const formatSubmittedAt = (iso?: string) => {
  if (!iso) return '未知时间'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const insightSeverityText = (severity: string) => ({
  high: '高优先级',
  medium: '中优先级',
  low: '低优先级'
}[severity] || '待关注')

const insightSeverityClass = (severity: string) => ({
  high: 'bg-red-50 text-red-700 border-red-100 dark:bg-red-950/30 dark:text-red-300 dark:border-red-900',
  medium: 'bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900',
  low: 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900'
}[severity] || 'bg-gray-50 text-gray-600 border-gray-100 dark:bg-zinc-800 dark:text-zinc-300 dark:border-zinc-700')

const dashboardMetricCards = computed<DashboardMetricCard[]>(() => [
  {
    label: '班级人数',
    value: Number(metrics.value.student_count || selectedClass.value?.member_count || 0),
    unit: '人',
    hint: '当前选中班级',
    icon: Users,
    tone: 'blue'
  },
  {
    label: '平均路径进度',
    value: Math.round(Number(metrics.value.avg_progress || 0)),
    unit: '%',
    hint: '已发布路径均值',
    icon: Activity,
    tone: 'emerald'
  },
  {
    label: '需关注学生',
    value: attentionStudents.value.length,
    unit: '人',
    hint: '由真实学情洞察聚合',
    icon: AlertTriangle,
    tone: 'red'
  },
  {
    label: '待处理事项',
    value: todoCount.value,
    unit: '项',
    hint: `涉及 ${pendingStudentCount.value} 名提交学生`,
    icon: ClipboardCheck,
    tone: 'amber'
  },
  {
    label: '学情记忆',
    value: Number(metrics.value.memory_count || 0),
    unit: '条',
    hint: '班级真实记忆条目',
    icon: Brain,
    tone: 'indigo'
  }
])

const agentActions: AgentAction[] = [
  {
    title: '生成班级简报',
    description: '汇总班级变化、风险与下一步安排',
    icon: FileText,
    prompt: '请基于当前班级真实数据，生成一份给教师看的班级学情简报。结构包含：班级态势、关键风险、需关注学生、下一步教学动作。'
  },
  {
    title: '设计干预计划',
    description: '把需关注学生转成一周行动清单',
    icon: Target,
    prompt: '请基于当前班级真实数据，为需关注学生设计一份一周干预计划。要求按学生分组，给出触发原因、教师动作、验证方式和复盘时间点。'
  },
  {
    title: '草拟分层任务',
    description: '根据洞察生成可发布的任务草案',
    icon: Wand2,
    prompt: '请基于当前班级真实数据，草拟一组分层学习任务。要求区分基础巩固、标准推进和挑战扩展，并说明每组适用学生与验收标准。'
  },
  {
    title: '整理反馈话术',
    description: '生成面向学生的具体反馈',
    icon: MessageSquare,
    prompt: '请基于当前班级真实数据，生成一批教师可直接修改后发送给学生的反馈话术。要求语气具体、鼓励但不空泛，并引用学生卡点原因。'
  }
]

const buildClassSnapshot = () => {
  if (!overview.value) {
    return '当前没有选中的班级概况。请提醒教师先创建班级或选择已有班级后再执行分析。'
  }

  const insightLines = insights.value.slice(0, 6).map((item, index) => {
    const studentsText = item.affected_student_ids.length ? `${item.affected_student_ids.length}名学生` : '班级整体'
    return `${index + 1}. ${item.title}｜${insightSeverityText(item.severity)}｜影响：${studentsText}｜摘要：${item.summary}`
  })
  const studentLines = attentionStudents.value.map((item, index) => {
    return `${index + 1}. ${item.name || '未设置姓名'}｜进度：${item.progress_percent || 0}%｜原因：${item.reason || '未记录原因'}`
  })
  const pathLines = recentPaths.value.map((item, index) => {
    return `${index + 1}. ${item.title}｜平均进度：${item.avg_progress || 0}%｜目标：${item.goal}`
  })
  const submissionLines = pendingSubmissions.value.slice(0, 5).map((item, index) => {
    return `${index + 1}. ${item.student_name}｜${item.task_title}｜${item.submitted_at}`
  })

  return [
    `当前班级：${overview.value.class_info.name}`,
    `班级说明：${overview.value.class_info.description || '未填写'}`,
    `班级指标：人数 ${metrics.value.student_count || selectedClass.value?.member_count || 0} 人，平均路径进度 ${metrics.value.avg_progress || 0}%，活跃路径 ${metrics.value.active_paths || 0} 条，学情记忆 ${metrics.value.memory_count || 0} 条，待批改 ${pendingSubmissions.value.length} 条。`,
    `学情摘要：${memorySummary.value}`,
    `关键洞察：\n${insightLines.length ? insightLines.join('\n') : '暂无未处理洞察。'}`,
    `需关注学生：\n${studentLines.length ? studentLines.join('\n') : '暂无需关注学生。'}`,
    `近期路径：\n${pathLines.length ? pathLines.join('\n') : '暂无近期学习路径。'}`,
    `待批改提交：\n${submissionLines.length ? submissionLines.join('\n') : '暂无待批改提交。'}`
  ].join('\n\n')
}

const loadPendingSubmissions = async (tasks: TaskOut[]) => {
  const details = await Promise.all(
    tasks.slice(0, 20).map(async (task) => {
      try {
        const res = await taskApi.getTaskDetails(task.id)
        return res.data as TaskDetails
      } catch (error) {
        console.warn('Failed to load task detail', task.id, error)
        return null
      }
    })
  )

  pendingSubmissions.value = details
    .filter((item): item is TaskDetails => Boolean(item))
    .flatMap((detail) => {
      const submittedAssigneeIds = new Set(
        detail.assignees
          .filter((assignee) => assignee.status === 'submitted')
          .map((assignee) => assignee.id)
      )
      return detail.submissions
        .filter((submission) => !submission.reviewed_at && submittedAssigneeIds.has(submission.assignee_id))
        .map((submission) => ({
          id: submission.id,
          student_name: displayNameOf(submission),
          task_title: detail.task.title,
          submitted_at: formatSubmittedAt(submission.created_at),
          created_at: submission.created_at
        }))
    })
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
}

const loadOverview = async (classId: string) => {
  selectedClassId.value = classId
  loadingOverview.value = true
  overview.value = null
  try {
    const res = await learningPathApi.getClassOverview(classId)
    overview.value = res.data
  } catch (error) {
    console.warn('Failed to load class overview', error)
    ElMessage.error('获取班级态势失败')
  } finally {
    loadingOverview.value = false
  }
}

const loadDashboard = async () => {
  loadingDashboard.value = true
  const hasLoadedClassData = classes.value.length > 0 || Boolean(overview.value)
  try {
    const classRes = await learningPathApi.listClasses()
    classes.value = classRes.data || []
    if (!classes.value.some((item) => item.id === selectedClassId.value)) {
      selectedClassId.value = classes.value[0]?.id || ''
    }
    if (selectedClassId.value) {
      await loadOverview(selectedClassId.value)
    } else {
      overview.value = null
    }
  } catch (error) {
    console.warn('Failed to load teacher dashboard classes', error)
    if (!hasLoadedClassData) overview.value = null
    ElMessage.error('加载班级列表失败')
  }

  try {
    const tasksRes = await taskApi.listTeacherTasks()
    teacherTasks.value = tasksRes.data || []
    await loadPendingSubmissions(teacherTasks.value)
  } catch (error) {
    console.warn('Failed to load teacher dashboard tasks', error)
    ElMessage.error('加载任务待办失败')
  } finally {
    loadingDashboard.value = false
  }
}

const handleInsightStatus = async (insightId: string, status: 'acknowledged' | 'resolved' | 'dismissed') => {
  try {
    await learningPathApi.updateInsightStatus(insightId, status)
    if (selectedClassId.value) await loadOverview(selectedClassId.value)
    ElMessage.success(status === 'acknowledged' ? '已标记为已读' : '洞察状态已更新')
  } catch (error) {
    ElMessage.error('更新洞察状态失败')
  }
}

const setupAiAssistant = async () => {
  try {
    const listRes = await aiChatApi.listConversations({ type: 'teacher_assistant', page_size: 1 })
    const list = listRes.data?.items || []
    if (list.length > 0) {
      conversation.value = list[0]
      await loadMessages(list[0].id)
      return
    }
    const createRes = await aiChatApi.createConversation({
      title: '教师 Agent 工作台',
      type: 'teacher_assistant'
    })
    conversation.value = createRes.data
  } catch (error) {
    console.warn('Failed to setup teacher agent', error)
  }
}

const loadMessages = async (conversationId: string) => {
  try {
    const res = await aiChatApi.listMessages(conversationId, { page_size: 30 })
    messages.value = res.data?.items || []
    scrollToBottom()
  } catch (error) {
    console.warn('Failed to load teacher agent messages', error)
  }
}

const handleSendMessage = async (customText?: string) => {
  const textToSend = customText || inputMessage.value.trim()
  if (!textToSend || !conversation.value || isResponding.value) return

  if (!customText) inputMessage.value = ''

  const tempUserMsg: MessageOut = {
    id: `temp-u-${Date.now()}`,
    conversation_id: conversation.value.id,
    role: 'user',
    content: textToSend,
    created_at: new Date().toISOString()
  }
  const tempAssistantMsg: MessageOut = {
    id: `temp-a-${Date.now()}`,
    conversation_id: conversation.value.id,
    role: 'assistant',
    content: '',
    created_at: new Date().toISOString()
  }

  messages.value.push(tempUserMsg, tempAssistantMsg)
  isResponding.value = true
  scrollToBottom()

  await aiChatApi.sendMessageStream(
    conversation.value.id,
    textToSend,
    {
      include_memory: false,
      include_todos: false,
      include_tasks: true,
      include_calendar: false,
      include_knowledge: false
    },
    (chunk) => {
      tempAssistantMsg.content += chunk
      scrollToBottom()
    },
    () => {
      isResponding.value = false
      if (conversation.value) loadMessages(conversation.value.id)
    },
    (error) => {
      isResponding.value = false
      ElMessage.error('教师 Agent 响应失败，请检查模型配置')
      console.error(error)
    }
  )
}

const runAgentAction = (action: AgentAction) => {
  const prompt = `${action.prompt}\n\n以下是系统中的当前真实数据，请只基于这些数据做判断，不要编造学生或任务：\n\n${buildClassSnapshot()}`
  handleSendMessage(prompt)
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadDashboard()
  setupAiAssistant()
})
</script>

<template>
  <div class="-m-4 min-h-[calc(100vh-8rem)] bg-gray-50 p-4 dark:bg-zinc-950 md:-m-8 md:p-8">
    <div class="mx-auto flex max-w-[1680px] flex-col gap-6">
      <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
        <div class="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <BarChart3 class="h-5 w-5 text-blue-600" />
              <h1 class="text-lg font-bold text-gray-900 dark:text-zinc-50">班级态势驾驶舱</h1>
            </div>
            <p class="mt-2 max-w-3xl text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
              {{ currentClassName }}：{{ overview?.class_info.description || selectedClass?.description || '暂无班级说明' }}
            </p>
          </div>

          <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
            <label class="flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs dark:border-zinc-800 dark:bg-zinc-950">
              <span class="shrink-0 text-gray-400">班级</span>
              <select
                v-model="selectedClassId"
                @change="selectedClassId && loadOverview(selectedClassId)"
                class="min-w-52 bg-transparent text-xs font-semibold text-gray-800 outline-none dark:text-zinc-100"
              >
                <option value="" disabled>请选择班级</option>
                <option v-for="item in classes" :key="item.id" :value="item.id">
                  {{ item.name }}（{{ item.member_count }}人）
                </option>
              </select>
            </label>
            <button
              type="button"
              class="ui-button-secondary"
              :disabled="loadingDashboard || loadingOverview"
              @click="loadDashboard"
            >
              <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': loadingDashboard || loadingOverview }" />
              刷新
            </button>
            <router-link to="/teacher/classes" class="ui-button-dark">
              <LineChart class="h-3.5 w-3.5" />
              班级看板
            </router-link>
          </div>
        </div>
      </section>

      <section v-if="classes.length === 0 && !loadingDashboard" class="minimal-card flex min-h-[420px] flex-col items-center justify-center bg-white p-8 text-center dark:bg-zinc-900">
        <Users class="mb-4 h-10 w-10 text-gray-300 dark:text-zinc-700" />
        <h2 class="text-base font-bold text-gray-900 dark:text-zinc-50">还没有可查看的班级</h2>
        <p class="mt-2 max-w-md text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
          创建班级并加入学生后，工作台会展示真实班级态势、洞察、需关注学生和教学待办。
        </p>
        <router-link to="/teacher/classes" class="ui-button-primary mt-5">
          <Users class="h-3.5 w-3.5" />
          去创建班级
        </router-link>
      </section>

      <section v-else-if="loadingDashboard && !overview" class="minimal-card flex min-h-[420px] flex-col items-center justify-center bg-white p-8 text-center dark:bg-zinc-900">
        <RefreshCw class="mb-4 h-8 w-8 animate-spin text-blue-600" />
        <h2 class="text-base font-bold text-gray-900 dark:text-zinc-50">正在加载班级态势</h2>
        <p class="mt-2 text-xs text-gray-500 dark:text-zinc-400">正在读取班级、路径、洞察和待办数据。</p>
      </section>

      <template v-else>
        <section class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5" v-loading="loadingDashboard || loadingOverview">
          <article
            v-for="card in dashboardMetricCards"
            :key="card.label"
            class="minimal-card bg-white p-5 dark:bg-zinc-900"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="min-w-0">
                <p class="text-[10px] font-semibold text-gray-400">{{ card.label }}</p>
                <div class="mt-2 flex items-end gap-1">
                  <span class="text-3xl font-bold leading-none" :class="toneClassMap[card.tone].value">{{ card.value }}</span>
                  <span class="pb-0.5 text-xs text-gray-400">{{ card.unit }}</span>
                </div>
                <p class="mt-2 truncate text-[10px] text-gray-400">{{ card.hint }}</p>
              </div>
              <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border" :class="toneClassMap[card.tone].icon">
                <component :is="card.icon" class="h-4 w-4" />
              </div>
            </div>
          </article>
        </section>

        <section class="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1fr)_380px]">
          <div class="space-y-6">
            <div class="grid grid-cols-1 gap-6 xl:grid-cols-12">
              <article class="minimal-card bg-white p-6 dark:bg-zinc-900 xl:col-span-7">
                <div class="flex flex-col gap-3 border-b border-gray-100 pb-4 dark:border-zinc-800 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                      <LineChart class="h-4 w-4 text-blue-600" />
                      班级趋势
                    </h2>
                    <p class="mt-1 text-[10px] text-gray-400">近 7 天路径进度变化</p>
                  </div>
                  <div class="flex flex-wrap gap-2 text-[10px]">
                    <span class="rounded-md bg-blue-50 px-2 py-1 font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                      {{ recentPaths.length }} 条近期路径
                    </span>
                    <span class="rounded-md bg-amber-50 px-2 py-1 font-semibold text-amber-700 dark:bg-amber-950/30 dark:text-amber-300">
                      {{ pendingSubmissions.length }} 条待批改
                    </span>
                  </div>
                </div>

                <div v-if="trend.length" class="mt-5 flex h-72 items-end gap-3 rounded-lg border border-gray-100 bg-gray-50/50 p-4 dark:border-zinc-800 dark:bg-zinc-950/30">
                  <div
                    v-for="item in trend"
                    :key="item.date"
                    class="flex h-full flex-1 flex-col items-center justify-end gap-2"
                  >
                    <div class="flex w-full max-w-12 flex-1 items-end justify-center">
                      <div
                        class="w-full rounded-t-md bg-blue-500/80"
                        :style="{ height: `${Math.max(8, Number(item.avg_progress || 0) / maxTrendProgress * 220)}px` }"
                      ></div>
                    </div>
                    <span class="text-[9px] text-gray-400">{{ String(item.date).slice(5) }}</span>
                  </div>
                </div>
                <div v-else class="mt-5 flex h-72 items-center justify-center rounded-lg border border-dashed border-gray-200 text-xs text-gray-400 dark:border-zinc-800">
                  暂无趋势数据
                </div>
              </article>

              <article class="minimal-card bg-white p-6 dark:bg-zinc-900 xl:col-span-5">
                <div class="flex items-start justify-between gap-3 border-b border-gray-100 pb-4 dark:border-zinc-800">
                  <div>
                    <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                      <AlertTriangle class="h-4 w-4 text-red-500" />
                      需要立即关注
                    </h2>
                    <p class="mt-1 text-[10px] text-gray-400">高优先级洞察和风险学生</p>
                  </div>
                  <span class="rounded-md bg-red-50 px-2 py-1 text-[10px] font-semibold text-red-700 dark:bg-red-950/30 dark:text-red-300">
                    {{ highPriorityInsights.length }} 条高优先级
                  </span>
                </div>

                <div class="mt-4 space-y-3">
                  <article
                    v-for="insight in highPriorityInsights"
                    :key="insight.id"
                    class="rounded-lg border border-red-100 bg-red-50/60 p-3 dark:border-red-900/50 dark:bg-red-950/20"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <h3 class="min-w-0 text-xs font-semibold leading-relaxed text-gray-900 dark:text-zinc-50">{{ insight.title }}</h3>
                      <span class="shrink-0 rounded bg-white px-2 py-1 text-[10px] text-red-600 dark:bg-zinc-900">{{ insight.affected_student_ids.length }} 人</span>
                    </div>
                    <p class="mt-2 line-clamp-3 text-xs leading-relaxed text-gray-600 dark:text-zinc-300">{{ insight.summary }}</p>
                  </article>

                  <div
                    v-for="student in attentionStudents.slice(0, highPriorityInsights.length ? 2 : 5)"
                    :key="student.user_id"
                    class="rounded-lg border border-gray-100 bg-gray-50/50 p-3 dark:border-zinc-800 dark:bg-zinc-950/30"
                  >
                    <div class="flex items-center justify-between gap-3">
                      <span class="text-xs font-semibold text-gray-900 dark:text-zinc-100">{{ student.name || '未设置姓名' }}</span>
                      <span class="text-[10px] text-gray-400">{{ student.progress_percent || 0 }}%</span>
                    </div>
                    <p class="mt-1 line-clamp-2 text-[10px] leading-relaxed text-gray-500">{{ student.reason || '暂无风险说明' }}</p>
                  </div>

                  <div v-if="highPriorityInsights.length === 0 && attentionStudents.length === 0" class="py-12 text-center text-xs text-gray-400">
                    当前没有需要立即处理的学生或洞察。
                  </div>
                </div>
              </article>
            </div>

            <div class="grid grid-cols-1 gap-6 xl:grid-cols-12">
              <article class="minimal-card bg-white p-6 dark:bg-zinc-900 xl:col-span-7">
                <div class="flex items-start justify-between gap-3 border-b border-gray-100 pb-4 dark:border-zinc-800">
                  <div>
                    <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                      <Brain class="h-4 w-4 text-indigo-500" />
                      班级洞察
                    </h2>
                    <p class="mt-1 text-[10px] text-gray-400">{{ memorySummary }}</p>
                  </div>
                  <router-link to="/teacher/classes" class="ui-button-secondary shrink-0">
                    查看全部
                  </router-link>
                </div>

                <div class="mt-4 space-y-3">
                  <article
                    v-for="insight in visibleInsights"
                    :key="insight.id"
                    class="rounded-lg border border-gray-100 bg-gray-50/40 p-4 dark:border-zinc-800 dark:bg-zinc-950/30"
                  >
                    <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <span class="rounded border px-2 py-0.5 text-[10px] font-semibold" :class="insightSeverityClass(insight.severity)">
                            {{ insightSeverityText(insight.severity) }}
                          </span>
                          <span class="text-[10px] text-gray-400">{{ insight.affected_student_ids.length }} 人受影响</span>
                        </div>
                        <h3 class="mt-2 text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ insight.title }}</h3>
                        <p class="mt-2 text-xs leading-relaxed text-gray-600 dark:text-zinc-300">{{ insight.summary }}</p>
                      </div>
                      <div class="flex shrink-0 gap-2">
                        <button
                          v-if="insight.status === 'new'"
                          type="button"
                          class="ui-button-secondary"
                          @click="handleInsightStatus(insight.id, 'acknowledged')"
                        >
                          <CheckCircle2 class="h-3.5 w-3.5" />
                          已读
                        </button>
                        <button type="button" class="ui-button-dark" @click="handleInsightStatus(insight.id, 'resolved')">
                          解决
                        </button>
                      </div>
                    </div>

                    <div v-if="insight.evidence.length" class="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                      <div
                        v-for="evidence in insight.evidence.slice(0, 2)"
                        :key="`${insight.id}-${evidence.source_id || evidence.content}`"
                        class="rounded-md border border-gray-100 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900"
                      >
                        <p class="text-[10px] font-semibold text-gray-500">{{ evidence.student_name || '班级' }}</p>
                        <p class="mt-1 line-clamp-2 text-[10px] leading-relaxed text-gray-500 dark:text-zinc-400">{{ evidence.content }}</p>
                      </div>
                    </div>
                  </article>

                  <div v-if="visibleInsights.length === 0" class="rounded-lg border border-dashed border-gray-200 py-12 text-center text-xs text-gray-400 dark:border-zinc-800">
                    暂无未处理班级洞察。
                  </div>
                </div>
              </article>

              <aside class="space-y-6 xl:col-span-5">
                <article class="minimal-card bg-white p-6 dark:bg-zinc-900">
                  <div class="flex items-center justify-between border-b border-gray-100 pb-4 dark:border-zinc-800">
                    <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                      <GitBranch class="h-4 w-4 text-blue-600" />
                      近期学习路径
                    </h2>
                    <router-link to="/teacher/learning-paths" class="text-[10px] font-semibold text-blue-600 dark:text-blue-300">进入路径任务</router-link>
                  </div>

                  <div class="mt-4 space-y-3">
                    <div
                      v-for="path in recentPaths"
                      :key="path.id"
                      class="rounded-lg border border-gray-100 bg-gray-50/40 p-3 dark:border-zinc-800 dark:bg-zinc-950/30"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <p class="truncate text-xs font-semibold text-gray-900 dark:text-zinc-100">{{ path.title }}</p>
                          <p class="mt-1 line-clamp-2 text-[10px] leading-relaxed text-gray-500">{{ path.goal }}</p>
                        </div>
                        <span class="rounded bg-emerald-50 px-2 py-1 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                          {{ path.avg_progress || 0 }}%
                        </span>
                      </div>
                      <div class="mt-3 flex items-center justify-between text-[10px] text-gray-400">
                        <span>截止 {{ formatDate(path.due_date) }}</span>
                        <span>{{ path.assignee_count || 0 }} 名学生</span>
                      </div>
                    </div>
                    <div v-if="recentPaths.length === 0" class="py-10 text-center text-xs text-gray-400">暂无学习路径任务。</div>
                  </div>
                </article>

                <article class="minimal-card bg-white p-6 dark:bg-zinc-900">
                  <div class="flex items-center justify-between border-b border-gray-100 pb-4 dark:border-zinc-800">
                    <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                      <ClipboardCheck class="h-4 w-4 text-amber-600" />
                      今日待办队列
                    </h2>
                    <router-link to="/teacher/tasks" class="text-[10px] font-semibold text-blue-600 dark:text-blue-300">任务管理</router-link>
                  </div>

                  <div class="mt-4 space-y-3">
                    <div
                      v-for="submission in pendingSubmissions.slice(0, 5)"
                      :key="submission.id"
                      class="rounded-lg border border-gray-100 bg-gray-50/40 p-3 dark:border-zinc-800 dark:bg-zinc-950/30"
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <p class="truncate text-xs font-semibold text-gray-900 dark:text-zinc-100">{{ submission.task_title }}</p>
                          <p class="mt-1 text-[10px] text-gray-500">{{ submission.student_name }} 提交于 {{ submission.submitted_at }}</p>
                        </div>
                        <router-link to="/teacher/tasks" class="shrink-0 rounded-md bg-gray-900 px-2 py-1 text-[10px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-950">
                          批改
                        </router-link>
                      </div>
                    </div>

                    <div v-for="insight in visibleInsights.slice(0, 2)" :key="`todo-${insight.id}`" class="rounded-lg border border-gray-100 bg-gray-50/40 p-3 dark:border-zinc-800 dark:bg-zinc-950/30">
                      <div class="flex items-start gap-2">
                        <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
                        <div class="min-w-0">
                          <p class="line-clamp-1 text-xs font-semibold text-gray-900 dark:text-zinc-100">{{ insight.title }}</p>
                          <p class="mt-1 line-clamp-2 text-[10px] leading-relaxed text-gray-500">{{ insight.summary }}</p>
                        </div>
                      </div>
                    </div>

                    <div v-if="pendingSubmissions.length === 0 && visibleInsights.length === 0" class="py-10 text-center text-xs text-gray-400">
                      当前没有待处理事项。
                    </div>
                  </div>
                </article>
              </aside>
            </div>
          </div>

          <aside class="minimal-card flex max-h-[calc(100vh-10rem)] flex-col bg-white p-5 dark:bg-zinc-900">
            <div class="border-b border-gray-100 pb-4 dark:border-zinc-800">
              <div class="flex items-center justify-between gap-3">
                <h2 class="flex items-center gap-2 text-sm font-bold text-gray-900 dark:text-zinc-50">
                  <Brain class="h-4 w-4 text-blue-600" />
                  教师 Agent 工作台
                </h2>
                <span class="rounded bg-blue-50 px-2 py-1 text-[10px] font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                  任务型
                </span>
              </div>
              <p class="mt-2 text-[10px] leading-relaxed text-gray-400">当前班级：{{ currentClassName }}</p>
            </div>

            <div class="mt-4 grid grid-cols-1 gap-2">
              <button
                v-for="action in agentActions"
                :key="action.title"
                type="button"
                class="group rounded-lg border border-gray-100 bg-gray-50/60 p-3 text-left transition hover:border-blue-200 hover:bg-blue-50/60 dark:border-zinc-800 dark:bg-zinc-950/30 dark:hover:border-blue-900 dark:hover:bg-blue-950/20"
                :disabled="isResponding || !overview"
                @click="runAgentAction(action)"
              >
                <div class="flex items-start gap-3">
                  <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-gray-100 bg-white text-blue-600 dark:border-zinc-800 dark:bg-zinc-900">
                    <component :is="action.icon" class="h-3.5 w-3.5" />
                  </div>
                  <div class="min-w-0">
                    <p class="text-xs font-semibold text-gray-900 group-disabled:text-gray-400 dark:text-zinc-100">{{ action.title }}</p>
                    <p class="mt-1 line-clamp-2 text-[10px] leading-relaxed text-gray-500">{{ action.description }}</p>
                  </div>
                </div>
              </button>
            </div>

            <div ref="chatContainer" class="mt-4 flex-1 overflow-y-auto rounded-lg border border-gray-100 bg-gray-50/50 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-950/30">
              <div class="mb-3 rounded-lg bg-white p-3 text-gray-500 dark:bg-zinc-900 dark:text-zinc-400">
                <p class="flex items-center gap-1.5 font-semibold text-blue-600 dark:text-blue-300">
                  <Sparkles class="h-3.5 w-3.5" />
                  已接入当前班级态势
                </p>
                <p class="mt-1 leading-relaxed">可以直接执行上方动作，也可以输入具体教学问题。</p>
              </div>

              <div
                v-for="message in messages"
                :key="message.id"
                class="mb-3 flex flex-col gap-1"
                :class="message.role === 'user' ? 'items-end' : 'items-start'"
              >
                <span class="px-1 text-[9px] text-gray-400">{{ message.role === 'user' ? '教师' : 'Agent' }}</span>
                <div
                  class="max-w-[88%] rounded-lg px-3 py-2 leading-relaxed"
                  :class="message.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'border border-gray-100 bg-white text-gray-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200'"
                >
                  <p class="max-h-64 overflow-y-auto whitespace-pre-wrap">{{ message.content || '正在整理...' }}</p>
                </div>
              </div>

              <div v-if="isResponding" class="flex items-center gap-2 px-1 py-2 text-[10px] text-gray-400">
                <RefreshCw class="h-3.5 w-3.5 animate-spin" />
                Agent 正在生成
              </div>
            </div>

            <div class="mt-3 flex items-center gap-2">
              <input
                v-model="inputMessage"
                :disabled="isResponding || !conversation"
                class="ui-field"
                placeholder="向教师 Agent 提问..."
                @keyup.enter="handleSendMessage()"
              />
              <button
                type="button"
                class="ui-icon-button h-9 w-9 shrink-0 bg-blue-600 text-white hover:bg-blue-500 hover:text-white"
                :disabled="isResponding || !conversation || !inputMessage.trim()"
                title="发送"
                @click="handleSendMessage()"
              >
                <Send class="h-4 w-4" />
              </button>
            </div>
          </aside>
        </section>
      </template>
    </div>
  </div>
</template>
