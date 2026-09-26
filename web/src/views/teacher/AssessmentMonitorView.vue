<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ShieldAlert, Eye, Clock, FileText, PenLine, Sparkles, CheckCheck } from 'lucide-vue-next'
import {
  assessmentApi,
  type AssessmentPaper,
  type AttemptMonitor,
  type AttemptAnswer,
  type BehaviorEventOut,
  type AttemptInsights,
  type AIGradeResult
} from '../../api/modules/assessment'
import RichStem from '../../components/assessment/RichStem.vue'
import MathText from '../../components/common/MathText.vue'

const route = useRoute()

const loading = ref(false)
const papers = ref<AssessmentPaper[]>([])
const selectedPaperId = ref<string>(String(route.query.paper_id || ''))
const attempts = ref<AttemptMonitor[]>([])
const attemptsLoading = ref(false)

const behaviorDrawer = ref(false)
const behaviorLoading = ref(false)
const behaviorEvents = ref<BehaviorEventOut[]>([])
// 抽屉内两种视图：timeline=原始事件时间线，byQuestion=按题聚合画像
const behaviorView = ref<'timeline' | 'byQuestion'>('byQuestion')
const insights = ref<AttemptInsights | null>(null)
const currentAttempt = ref<AttemptMonitor | null>(null)
const questionMap = ref<Record<string, number>>({})

const gradeDrawer = ref(false)
const gradeLoading = ref(false)
const gradeSubmitting = ref(false)
const gradeAiRunning = ref(false)
const gradeAnswers = ref<AttemptAnswer[]>([])
const gradeScores = ref<Record<string, number>>({})
const aiGradeErrors = ref<Record<string, string>>({})
const gradingAttempt = ref<AttemptMonitor | null>(null)

// 本卷的批阅倾向，AI 与人工批改共用同一份尺度提示
const gradingPreferenceText = computed(() => {
  const pref = selectedPaper.value?.grading_preference
  const mode = pref?.mode || 'standard'
  const label = mode === 'lenient' ? '宽松' : mode === 'strict' ? '严格' : '标准'
  const extra = (pref?.extra || '').trim()
  return extra ? `${label} · ${extra}` : label
})

const hasAiSuggestion = (a: AttemptAnswer) =>
  a.ai_suggested_score != null || !!a.ai_comment

const EVENT_LABELS: Record<string, string> = {
  session_start: '开始作答',
  session_end: '结束作答',
  fullscreen_enter: '进入全屏',
  fullscreen_exit: '退出全屏',
  fullscreen_denied: '全屏被拒绝',
  blocked_shortcut: '拦截快捷键',
  blocked_paste: '拦截粘贴',
  blocked_copy: '拦截复制',
  blocked_cut: '拦截剪切',
  blocked_drop: '拦截拖拽',
  blocked_contextmenu: '拦截右键',
  blocked_insert: '拦截粘贴插入',
  answer_edit: '答案编辑记录',
  blocked_selection: '拦截选中复制',
  blocked_drag: '拦截拖拽',
  blocked_exec: '拦截 execCommand',
  clipboard_read: '读取剪贴板',
  devtools_open: '打开开发者工具',
  focus_gain: '回到页面',
  focus_loss: '离开页面',
  focus_dwell: '焦点停留',
  question_dwell: '题目停留',
  visibility_hidden: '页面切后台',
  visibility_visible: '回到前台'
}

const FLAG_TYPES = new Set([
  'fullscreen_exit',
  'fullscreen_denied',
  'blocked_shortcut',
  'blocked_paste',
  'blocked_copy',
  'blocked_cut',
  'blocked_drop',
  'blocked_contextmenu',
  'blocked_insert',
  'blocked_selection',
  'blocked_drag',
  'blocked_exec',
  'clipboard_read',
  'devtools_open',
  'focus_loss',
  'visibility_hidden'
])

const selectedPaper = computed(
  () => papers.value.find((p) => p.id === selectedPaperId.value) || null
)

const eventLabel = (t: string) => EVENT_LABELS[t] || t
const isFlag = (t: string) => FLAG_TYPES.has(t)

const formatTime = (v?: string | null) => {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return v
  }
}

const formatDuration = (s?: number | null) => {
  if (s == null) return '—'
  const m = Math.floor(s / 60)
  const sec = s % 60
  const h = Math.floor(m / 60)
  const mm = m % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(mm)}:${pad(sec)}` : `${pad(mm)}:${pad(sec)}`
}

const statusLabel = (s: string) => {
  const map: Record<string, string> = {
    in_progress: '作答中',
    submitted: '已交卷',
    pending_review: '待批改'
  }
  return map[s] || s
}

const statusToneClass = (s: string) => {
  if (s === 'submitted') return 'bg-green-50 text-green-600 dark:bg-green-950/30 dark:text-green-400'
  if (s === 'pending_review') return 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400'
  return 'bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400'
}

const typeLabel = (t: string) => {
  const map: Record<string, string> = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    fill: '填空题',
    short: '简答题',
    essay: '论述题'
  }
  return map[t] || '题目'
}

// 只有主观题由教师给分：单选/多选/判断/填空都走 _judge 自动判分，
// 后端 grade_attempt 也只接受 short/essay，这里必须保持一致。
const isManualType = (t: string) => t === 'short' || t === 'essay'

const formatAnswer = (v: any) => {
  if (v == null || v === '') return '（未作答）'
  if (Array.isArray(v)) return v.length ? v.join('、') : '（未作答）'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

const TARGET_LABELS: Record<string, string> = {
  answer: '作答输入框',
  judge: '判断题按钮'
}

const questionNo = (qid: any) => {
  if (!qid) return ''
  const n = questionMap.value[qid]
  return n ? `第 ${n} 题` : '题目'
}

const fieldText = (target: any, field: any) => {
  if (target === 'judge' && (field === '对' || field === '错')) return `「${field}」`
  return ''
}

const formatEventPayload = (e: BehaviorEventOut) => {
  const p = e.payload || {}
  const parts: string[] = []
  const sec = (ms: any) => Math.round(Number(ms) / 1000)

  if (e.event_type === 'focus_dwell') {
    const no = questionNo(p.question_id)
    if (no) parts.push(no)
    const target = TARGET_LABELS[p.target] || ''
    if (target) parts.push(target)
    const f = fieldText(p.target, p.field)
    if (f) parts.push(f)
    if (p.duration_ms != null) parts.push(`停留 ${sec(p.duration_ms)}s`)
    return parts.join(' · ')
  }
  if (e.event_type === 'question_dwell') {
    const no = questionNo(p.question_id)
    if (no) parts.push(no)
    if (p.duration_ms != null) parts.push(`停留 ${sec(p.duration_ms)}s`)
    return parts.join(' · ')
  }
  if (e.event_type === 'answer_edit') {
    const no = questionNo(p.question_id)
    if (no) parts.push(no)
    const method: Record<string, string> = {
      typing: '键盘输入', ime: '输入法', non_key_input: '非键盘输入', delete: '删除'
    }
    const op: Record<string, string> = { insert: '新增', delete: '删除', replace: '替换' }
    parts.push(method[p.input_method] || '编辑')
    parts.push(op[p.operation] || '修改')
    if (p.deleted_chars) parts.push(`删 ${p.deleted_chars} 字`)
    if (p.inserted_chars) parts.push(`增 ${p.inserted_chars} 字`)
    return parts.join(' · ')
  }

  if (p.duration_ms != null) parts.push(`离开 ${sec(p.duration_ms)}s`)
  if (p.code) parts.push(`按键 ${p.code}`)
  if (p.key) parts.push(`键 ${p.key}`)
  if (p.count != null) parts.push(`第 ${p.count} 次`)
  if (p.input_type) parts.push(`类型 ${p.input_type}`)
  if (p.command) parts.push(`命令 ${p.command}`)
  if (p.source) parts.push(`来源 ${p.source}`)
  return parts.length ? parts.join(' · ') : ''
}

const loadPapers = async () => {
  loading.value = true
  try {
    const res = await assessmentApi.listPapers()
    papers.value = res.data || []
    if (!selectedPaperId.value && papers.value.length) {
      selectedPaperId.value = papers.value[0].id
      loadAttempts()
      loadQuestionMap(selectedPaperId.value)
    } else if (selectedPaperId.value) {
      loadAttempts()
      loadQuestionMap(selectedPaperId.value)
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    loading.value = false
  }
}

const loadAttempts = async () => {
  if (!selectedPaperId.value) return
  attemptsLoading.value = true
  try {
    const res = await assessmentApi.listPaperAttempts(selectedPaperId.value)
    attempts.value = res.data || []
  } catch {
    attempts.value = []
  } finally {
    attemptsLoading.value = false
  }
}

const exportingScore = ref(false)
const exportScoreSheet = async () => {
  if (!selectedPaperId.value || exportingScore.value) return
  exportingScore.value = true
  try {
    const res = await assessmentApi.exportScoreSheet(selectedPaperId.value)
    const blob = res.data as Blob
    if (blob.type && blob.type.includes('json')) {
      ElMessage.error('导出成绩单失败')
      return
    }
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    const encoded = /filename\*=UTF-8''([^;]+)/.exec(res.headers?.['content-disposition'] || '')
    link.href = url
    link.download = encoded ? decodeURIComponent(encoded[1]) : '成绩单.pdf'
    link.click()
    URL.revokeObjectURL(url)
  } catch {
    // 错误已由拦截器提示
  } finally {
    exportingScore.value = false
  }
}

const loadQuestionMap = async (paperId: string) => {
  questionMap.value = {}
  try {
    const res = await assessmentApi.listQuestions(paperId)
    const items: any[] = res.data || []
    const map: Record<string, number> = {}
    items.forEach((q, i) => {
      map[q.id] = i + 1
    })
    questionMap.value = map
  } catch {
    // 题目映射失败时降级为“题目”
  }
}

const onPaperChange = () => {
  loadAttempts()
  loadQuestionMap(selectedPaperId.value)
}

const openBehavior = async (attempt: AttemptMonitor) => {
  currentAttempt.value = attempt
  behaviorDrawer.value = true
  behaviorLoading.value = true
  behaviorEvents.value = []
  insights.value = null
  try {
    // 两个接口一起取：默认展示按题画像，切到时间线无需二次请求
    const [eventsRes, insightsRes] = await Promise.all([
      assessmentApi.listAttemptBehavior(attempt.id),
      assessmentApi.getAttemptInsights(attempt.id).catch(() => ({ data: null }))
    ])
    behaviorEvents.value = eventsRes.data || []
    insights.value = insightsRes.data
  } catch {
    behaviorEvents.value = []
  } finally {
    behaviorLoading.value = false
  }
}

// 逐题用时与全班均值的偏离度：显著高于全班均值（>1.5 倍且绝对差 >10s）的题
// 标记出来 —— 可能是卡壳，也可能是值得关注的地方。
const dwellDeviation = (q: AttemptInsights['questions'][number]) => {
  const avg = q.class_avg_dwell_seconds
  if (avg == null || avg <= 0 || q.dwell_seconds <= 0) return null
  if (q.dwell_seconds > avg * 1.5 && q.dwell_seconds - avg > 10) {
    return { tone: 'slow', ratio: Math.round((q.dwell_seconds / avg) * 10) / 10 }
  }
  if (q.dwell_seconds < avg * 0.5 && avg - q.dwell_seconds > 10) {
    return { tone: 'fast', ratio: Math.round((q.dwell_seconds / avg) * 10) / 10 }
  }
  return null
}

const insightRows = computed(() => {
  const qs = insights.value?.questions || []
  return qs.map((q) => ({
    ...q,
    deviation: dwellDeviation(q)
  }))
})

// 原始 BehaviorEvent 仍完整保存在后端；在按题画像里按题筛出编辑历史，
// 让教师可以展开查看精确的新增/删除内容，而不只看到字符数摘要。
const answerEditsForQuestion = (questionId: string) =>
  behaviorEvents.value.filter(
    (event) => event.event_type === 'answer_edit' && String(event.payload?.question_id || '') === questionId
  )

const editMethodLabel: Record<string, string> = {
  typing: '键盘输入',
  ime: '输入法提交',
  non_key_input: '非键盘输入',
  delete: '删除'
}
const editOperationLabel: Record<string, string> = {
  insert: '新增',
  delete: '删除',
  replace: '替换',
  none: '无变化'
}

const openGrading = async (attempt: AttemptMonitor) => {
  gradingAttempt.value = attempt
  gradeDrawer.value = true
  gradeLoading.value = true
  gradeAnswers.value = []
  gradeScores.value = {}
  aiGradeErrors.value = {}
  try {
    const res = await assessmentApi.listAttemptAnswers(attempt.id)
    const items: AttemptAnswer[] = res.data || []
    gradeAnswers.value = items
    // 只预填「已批改」的分数；未批改的留空。
    // 若把未批改的一律填 0 并全量提交，教师只批一道题就会把其余主观题
    // 静默锁成「已批 0 分」，且 graded=True 后无法再回到待批状态。
    // AI 建议分也不预填 —— 那是参考值，必须由教师点「采纳」才写入。
    const scores: Record<string, number> = {}
    items.forEach((a) => {
      if (isManualType(a.question_type) && a.graded) {
        scores[a.question_id] = Number(a.score ?? 0)
      }
    })
    gradeScores.value = scores
  } catch {
    gradeAnswers.value = []
  } finally {
    gradeLoading.value = false
  }
}

const runAiGrade = async (overwrite = false) => {
  if (!gradingAttempt.value) return
  gradeAiRunning.value = true
  try {
    const res = await assessmentApi.aiGradeAttempt(gradingAttempt.value.id, { overwrite })
    const result = res.data as AIGradeResult | undefined
    const errors: Record<string, string> = {}
    for (const item of result?.items || []) {
      if (item.error) errors[String(item.question_id)] = item.error
    }
    aiGradeErrors.value = errors
    const fresh = await assessmentApi.listAttemptAnswers(gradingAttempt.value.id)
    gradeAnswers.value = fresh.data || []
    const graded = result?.graded ?? 0
    const failed = result?.failed ?? 0
    const skipped = result?.skipped ?? 0
    if (graded > 0 && failed === 0) {
      ElMessage.success(`AI 已预批 ${graded} 题，待你确认采纳`)
    } else if (graded > 0) {
      ElMessage.warning(`AI 已预批 ${graded} 题，另有 ${failed} 题失败，原因标在题目下方`)
    } else if (failed > 0) {
      ElMessage.warning(`${failed} 题未能批阅，原因标在题目下方`)
    } else if (skipped > 0) {
      ElMessage.info('这些主观题已有建议或人工分。要重算建议分，用「重新生成」')
    } else {
      ElMessage.info('没有需要预批的主观题')
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    gradeAiRunning.value = false
  }
}

const regenerateAiGrade = async () => {
  try {
    await ElMessageBox.confirm(
      '将重新调用 AI，覆盖现有建议分。已经保存的人工分数不会被改动。',
      '重新生成建议',
      { type: 'warning', confirmButtonText: '重新生成', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  await runAiGrade(true)
}

// 采纳 AI 建议分：只是把它填进打分框，仍需教师点保存才生效
const adoptAiScore = (a: AttemptAnswer) => {
  if (a.ai_suggested_score == null) return
  gradeScores.value = { ...gradeScores.value, [a.question_id]: Number(a.ai_suggested_score) }
}

const adoptAllAiScores = () => {
  const next = { ...gradeScores.value }
  gradeAnswers.value.forEach((a) => {
    if (isManualType(a.question_type) && a.ai_suggested_score != null) {
      next[a.question_id] = Number(a.ai_suggested_score)
    }
  })
  gradeScores.value = next
}

const submitGrades = async () => {
  if (!gradingAttempt.value) return
  // 只提交教师真正给过分的题目；空值代表「还没批」，不能当成 0 分发出去。
  const grades = Object.entries(gradeScores.value)
    .filter(([, score]) => score !== undefined && score !== null && !Number.isNaN(Number(score)))
    .map(([question_id, score]) => ({
      question_id,
      score: Number(score) || 0
    }))
  if (!grades.length) {
    ElMessage.warning('请先给至少一道题打分')
    return
  }
  gradeSubmitting.value = true
  try {
    await assessmentApi.gradeAttempt(gradingAttempt.value.id, grades)
    ElMessage.success('批改已保存')
    gradeDrawer.value = false
    await loadAttempts()
  } catch {
    // 错误已由拦截器提示
  } finally {
    gradeSubmitting.value = false
  }
}

onMounted(loadPapers)
</script>

<template>
  <div class="space-y-5">
    <div class="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
      <div class="flex items-center gap-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-md bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400">
          <ShieldAlert class="h-4.5 w-4.5" />
        </div>
        <div>
          <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">监考中心</p>
          <p class="text-[11px] text-gray-400">查看学生作答情况与防作弊行为数据</p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <el-select
          v-model="selectedPaperId"
          placeholder="选择试卷"
          class="w-72"
          filterable
          @change="onPaperChange"
        >
          <el-option
            v-for="p in papers"
            :key="p.id"
            :label="p.title"
            :value="p.id"
          />
        </el-select>
        <button class="ui-button-secondary" @click="loadAttempts">
          <Clock class="h-3.5 w-3.5" />
          <span>刷新</span>
        </button>
      </div>
    </div>

    <div v-loading="attemptsLoading || loading" class="surface-panel p-5">
      <div class="mb-4 flex flex-wrap items-center gap-3 text-xs text-gray-500 dark:text-zinc-400">
        <FileText class="h-3.5 w-3.5" />
        <span>{{ selectedPaper ? selectedPaper.title : '未选择试卷' }}</span>
        <span v-if="selectedPaper" class="text-gray-300 dark:text-zinc-600">|</span>
        <span v-if="selectedPaper">共 {{ attempts.length }} 人作答</span>
        <button
          class="ml-auto rounded bg-gray-900 px-3 py-1 text-[11px] font-semibold text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
          :disabled="!selectedPaperId || exportingScore"
          @click="exportScoreSheet"
        >
          {{ exportingScore ? '正在导出…' : '导出成绩单 PDF' }}
        </button>
      </div>

      <el-table v-if="attempts.length" :data="attempts" style="width: 100%">
        <el-table-column label="学生" min-width="140">
          <template #default="{ row }">
            <div class="flex flex-col">
              <span class="text-sm font-medium text-gray-900 dark:text-zinc-100">{{ row.student_name }}</span>
              <span class="text-[11px] text-gray-400">{{ row.username }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span
              class="rounded px-2 py-0.5 text-[11px]"
              :class="statusToneClass(row.status)"
            >{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="80">
          <template #default="{ row }">
            <span class="font-semibold text-gray-900 dark:text-zinc-100">{{ row.score ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="用时" width="90">
          <template #default="{ row }">
            <span>{{ formatDuration(row.duration_seconds) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="行为/违规" width="110">
          <template #default="{ row }">
            <span class="text-gray-600 dark:text-zinc-300">{{ row.event_count }}</span>
            <span class="text-gray-300 dark:text-zinc-600"> / </span>
            <span :class="row.flagged_count ? 'text-amber-600 dark:text-amber-400' : 'text-gray-300 dark:text-zinc-600'">
              {{ row.flagged_count }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="可疑" width="70">
          <template #default="{ row }">
            <ShieldAlert v-if="row.suspicious" class="h-4 w-4 text-red-500" />
            <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="提交时间" width="160">
          <template #default="{ row }">{{ formatTime(row.submitted_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.pending_grade_count > 0"
              size="small"
              text
              type="warning"
              :icon="PenLine"
              @click="openGrading(row)"
            >
              批改 ({{ row.pending_grade_count }})
            </el-button>
            <el-button size="small" text type="primary" :icon="Eye" @click="openBehavior(row)">
              作答画像
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-else class="py-12 text-center text-sm text-gray-400">
        暂无作答记录
      </div>
    </div>

    <el-drawer
      v-model="behaviorDrawer"
      :title="currentAttempt ? `${currentAttempt.student_name} 的作答画像` : '作答画像'"
      size="560px"
    >
      <div class="mb-4 flex gap-1 rounded-lg bg-gray-100 p-1 dark:bg-zinc-800">
        <button
          class="flex-1 rounded-md px-3 py-1.5 text-xs font-semibold transition"
          :class="behaviorView === 'byQuestion' ? 'bg-white text-gray-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50' : 'text-gray-500 dark:text-zinc-400'"
          @click="behaviorView = 'byQuestion'"
        >
          按题画像
        </button>
        <button
          class="flex-1 rounded-md px-3 py-1.5 text-xs font-semibold transition"
          :class="behaviorView === 'timeline' ? 'bg-white text-gray-900 shadow-sm dark:bg-zinc-900 dark:text-zinc-50' : 'text-gray-500 dark:text-zinc-400'"
          @click="behaviorView = 'timeline'"
        >
          事件时间线
        </button>
      </div>

      <div v-loading="behaviorLoading" class="px-1">
        <!-- 按题画像 -->
        <template v-if="behaviorView === 'byQuestion'">
          <div
            v-if="insights"
            class="mb-4 rounded-lg border border-gray-100 bg-gray-50/50 px-3 py-2.5 text-xs text-gray-500 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-400"
          >
            总用时 {{ Math.round((insights.attempt.duration_seconds || 0) / 60) }} 分钟
            · 违规事件 {{ insights.attempt.flag_count }} 次
          </div>

          <div class="space-y-2">
            <div
              v-for="q in insightRows"
              :key="q.question_id"
              class="rounded-lg border border-gray-100 px-3 py-2.5 dark:border-zinc-800"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="flex items-center gap-2">
                  <span class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                    第 {{ q.order_index + 1 }} 题
                  </span>
                  <span class="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
                    {{ typeLabel(q.question_type) }}
                  </span>
                </div>
                <span v-if="q.flag_count > 0" class="text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                  {{ q.flag_count }} 次违规
                </span>
              </div>

              <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-gray-500 dark:text-zinc-400">
                <span>
                  停留
                  <span class="font-semibold text-gray-800 dark:text-zinc-100">{{ q.dwell_seconds }}s</span>
                  <span v-if="q.class_avg_dwell_seconds != null" class="text-gray-400">
                    （全班均 {{ q.class_avg_dwell_seconds }}s）
                  </span>
                </span>
                <span v-if="q.paste_events > 0" class="font-semibold text-red-500">
                  非键盘插入 {{ q.paste_events }} 次 · {{ q.paste_chars }} 字
                </span>
              </div>

              <div v-if="q.edit_count > 0" class="mt-1 text-[10px] text-gray-400 dark:text-zinc-500">
                编辑 {{ q.edit_count }} 段 · 手敲 {{ q.typed_chars }} 字
                <span v-if="q.ime_chars">· 输入法 {{ q.ime_chars }} 字</span>
                <span v-if="q.non_key_input_chars">· 非键盘 {{ q.non_key_input_chars }} 字</span>
                <span v-if="q.deleted_chars">· 删除 {{ q.deleted_chars }} 字</span>
              </div>

              <details v-if="answerEditsForQuestion(q.question_id).length" class="mt-2 rounded-md bg-gray-50 px-2.5 py-2 dark:bg-zinc-950/40">
                <summary class="cursor-pointer text-[10px] font-semibold text-blue-600 dark:text-blue-300">
                  查看新增 / 删除内容（{{ answerEditsForQuestion(q.question_id).length }} 段）
                </summary>
                <div class="mt-2 max-h-72 space-y-2 overflow-y-auto">
                  <article
                    v-for="edit in answerEditsForQuestion(q.question_id)"
                    :key="edit.id"
                    class="rounded border border-gray-100 bg-white p-2 dark:border-zinc-800 dark:bg-zinc-900"
                  >
                    <div class="mb-1 flex flex-wrap items-center gap-1.5 text-[9px] text-gray-400">
                      <span>{{ formatTime(edit.occurred_at) }}</span>
                      <span>{{ editMethodLabel[edit.payload?.input_method] || '编辑' }}</span>
                      <span>{{ editOperationLabel[edit.payload?.operation] || '修改' }}</span>
                      <span>位置 {{ edit.payload?.position ?? 0 }}</span>
                    </div>
                    <div v-if="edit.payload?.deleted_text" class="text-[10px] leading-relaxed">
                      <span class="font-semibold text-red-500">删除：</span>
                      <pre class="mt-0.5 whitespace-pre-wrap break-words rounded bg-red-50/70 p-1.5 text-red-700 dark:bg-red-950/20 dark:text-red-300">{{ edit.payload.deleted_text }}</pre>
                    </div>
                    <div v-if="edit.payload?.inserted_text" class="mt-1 text-[10px] leading-relaxed">
                      <span class="font-semibold text-emerald-600">新增：</span>
                      <pre class="mt-0.5 whitespace-pre-wrap break-words rounded bg-emerald-50/70 p-1.5 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300">{{ edit.payload.inserted_text }}</pre>
                    </div>
                  </article>
                </div>
              </details>

              <div
                v-if="q.deviation"
                class="mt-1.5 text-[10px]"
                :class="q.deviation.tone === 'slow' ? 'text-amber-600 dark:text-amber-400' : 'text-blue-600 dark:text-blue-400'"
              >
                <template v-if="q.deviation.tone === 'slow'">
                  停留约为全班均值的 {{ q.deviation.ratio }} 倍，可能卡壳
                </template>
                <template v-else>
                  停留明显短于全班（约 {{ q.deviation.ratio }} 倍），可能仓促作答
                </template>
              </div>
            </div>
          </div>

          <div v-if="!insights" class="py-12 text-center text-sm text-gray-400">
            暂无按题画像数据
          </div>
        </template>

        <!-- 事件时间线 -->
        <template v-else>
          <div
            v-for="e in behaviorEvents"
            :key="e.id"
            class="mb-2 flex items-start gap-3 rounded-lg border border-gray-100 px-3 py-2.5 dark:border-zinc-800"
          >
            <span
              class="mt-0.5 flex h-2 w-2 flex-shrink-0 rounded-full"
              :class="isFlag(e.event_type) ? 'bg-amber-500' : 'bg-gray-300 dark:bg-zinc-600'"
            />
            <div class="min-w-0 flex-1">
              <div class="flex items-center justify-between gap-2">
                <span class="text-sm font-medium text-gray-800 dark:text-zinc-100">{{ eventLabel(e.event_type) }}</span>
                <span class="text-[11px] text-gray-400">{{ formatTime(e.occurred_at) }}</span>
              </div>
              <p v-if="formatEventPayload(e)" class="mt-0.5 text-xs text-gray-500 dark:text-zinc-400">
                {{ formatEventPayload(e) }}
              </p>
            </div>
          </div>

          <div v-if="!behaviorEvents.length && !behaviorLoading" class="py-12 text-center text-sm text-gray-400">
            暂无行为记录
          </div>
        </template>
      </div>
    </el-drawer>

    <el-drawer
      v-model="gradeDrawer"
      :title="gradingAttempt ? `批改 · ${gradingAttempt.student_name}` : '批改'"
      size="620px"
    >
      <div v-loading="gradeLoading" class="space-y-3 px-1">
        <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2.5 dark:border-blue-900/40 dark:bg-blue-950/20">
          <div class="min-w-0">
            <p class="text-[11px] font-semibold text-blue-700 dark:text-blue-300">批阅尺度：{{ gradingPreferenceText }}</p>
            <p class="mt-0.5 text-[10px] leading-relaxed text-blue-600/80 dark:text-blue-300/70">
              先让 AI 预批出建议分，再逐题确认或采纳；采纳只是填入打分框，保存后才生效。
            </p>
          </div>
          <el-button
            size="small"
            type="primary"
            :loading="gradeAiRunning"
            :disabled="!gradeAnswers.length"
            @click="runAiGrade()"
          >
            <Sparkles class="mr-1 h-3.5 w-3.5" />
            AI 预批阅
          </el-button>
        </div>
        <div
          v-for="a in gradeAnswers"
          :key="a.question_id"
          class="rounded-lg border border-gray-100 px-3 py-3 dark:border-zinc-800"
        >
          <div class="mb-2 flex items-center gap-2">
            <span class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
              第 {{ a.order_index + 1 }} 题
            </span>
            <span class="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
              {{ typeLabel(a.question_type) }}
              <template v-if="a.max_score === null || a.max_score === undefined"> · 分值待定</template>
              <template v-else> · 满分 {{ a.max_score }}</template>
            </span>
            <span
              v-if="a.graded"
              class="rounded bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400"
            >
              已批 {{ a.score }} 分
            </span>
            <span
              v-else
              class="rounded bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400"
            >
              待批改
            </span>
          </div>

          <RichStem :stem="a.stem" class="text-sm leading-relaxed text-gray-800 dark:text-zinc-100" />

          <div v-if="a.options && a.options.length" class="mt-2 space-y-1">
            <div
              v-for="opt in a.options"
              :key="opt.key"
              class="rounded border border-gray-100 px-2 py-1 text-xs text-gray-600 dark:border-zinc-800 dark:text-zinc-300"
            >
              <span class="font-semibold">{{ opt.key }}.</span>
              <MathText :text="opt.text" class="ml-1" />
            </div>
          </div>

          <div class="mt-3 rounded bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
            <p class="text-[11px] font-semibold text-gray-400">学生作答</p>
            <p class="mt-1 whitespace-pre-wrap text-sm text-gray-800 dark:text-zinc-100">
              {{ formatAnswer(a.answer) }}
            </p>
          </div>

          <div
            v-if="a.reference_answer != null && a.reference_answer !== ''"
            class="mt-2 rounded bg-emerald-50/60 px-3 py-2 dark:bg-emerald-950/20"
          >
            <p class="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400">参考答案</p>
            <p class="mt-1 whitespace-pre-wrap text-sm text-emerald-800 dark:text-emerald-200">
              {{ formatAnswer(a.reference_answer) }}
            </p>
          </div>

          <div
            v-if="hasAiSuggestion(a)"
            class="mt-2 rounded border border-violet-100 bg-violet-50/60 px-3 py-2 dark:border-violet-900/40 dark:bg-violet-950/20"
          >
            <div class="flex items-center justify-between gap-2">
              <p class="flex items-center gap-1 text-[11px] font-semibold text-violet-600 dark:text-violet-300">
                <Sparkles class="h-3 w-3" />
                AI 建议
                <template v-if="a.ai_suggested_score != null">：{{ a.ai_suggested_score }} 分</template>
              </p>
              <button
                v-if="a.ai_suggested_score != null && a.max_score != null"
                class="rounded bg-violet-600 px-2 py-0.5 text-[10px] font-semibold text-white transition hover:bg-violet-500"
                @click="adoptAiScore(a)"
              >
                采纳
              </button>
            </div>
            <p v-if="a.ai_comment" class="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-violet-700/90 dark:text-violet-200/80">
              {{ a.ai_comment }}
            </p>
          </div>
          <p v-if="aiGradeErrors[a.question_id]" class="mt-2 text-[11px] leading-relaxed text-red-500">
            未能预批：{{ aiGradeErrors[a.question_id] }}
          </p>

          <div v-if="isManualType(a.question_type) || !a.graded" class="mt-3 flex items-center gap-2">
            <template v-if="a.max_score === null || a.max_score === undefined">
              <span class="text-xs text-amber-500">该题未设置分值，请先在校对页补填后再给分</span>
            </template>
            <template v-else>
              <span class="text-xs text-gray-500 dark:text-zinc-400">给分</span>
              <el-input-number
                v-model="gradeScores[a.question_id]"
                :min="0"
                :max="a.max_score"
                :step="0.5"
                :precision="1"
                size="small"
                controls-position="right"
                class="w-28"
              />
              <span class="text-xs text-gray-400">/ {{ a.max_score }}</span>
            </template>
          </div>
        </div>

        <div v-if="!gradeAnswers.length && !gradeLoading" class="py-12 text-center text-sm text-gray-400">
          暂无作答内容
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <el-button @click="gradeDrawer = false">取消</el-button>
          <el-button :disabled="gradeAiRunning || !gradeAnswers.length" @click="regenerateAiGrade">
            重新生成建议
          </el-button>
          <el-button :icon="CheckCheck" @click="adoptAllAiScores">采纳全部建议分</el-button>
          <el-button
            type="primary"
            :loading="gradeSubmitting"
            :disabled="!gradeAnswers.length"
            @click="submitGrades"
          >
            保存批改
          </el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>