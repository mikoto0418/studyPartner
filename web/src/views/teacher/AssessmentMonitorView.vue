<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ShieldAlert, Eye, Clock, FileText, PenLine } from 'lucide-vue-next'
import {
  assessmentApi,
  type AssessmentPaper,
  type AttemptMonitor,
  type AttemptAnswer,
  type BehaviorEventOut
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
const currentAttempt = ref<AttemptMonitor | null>(null)
const questionMap = ref<Record<string, number>>({})

const gradeDrawer = ref(false)
const gradeLoading = ref(false)
const gradeSubmitting = ref(false)
const gradeAnswers = ref<AttemptAnswer[]>([])
const gradeScores = ref<Record<string, number>>({})
const gradingAttempt = ref<AttemptMonitor | null>(null)

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
    pending_review: '待批改',
    expired: '已过期'
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
  try {
    const res = await assessmentApi.listAttemptBehavior(attempt.id)
    behaviorEvents.value = res.data || []
  } catch {
    behaviorEvents.value = []
  } finally {
    behaviorLoading.value = false
  }
}

const openGrading = async (attempt: AttemptMonitor) => {
  gradingAttempt.value = attempt
  gradeDrawer.value = true
  gradeLoading.value = true
  gradeAnswers.value = []
  gradeScores.value = {}
  try {
    const res = await assessmentApi.listAttemptAnswers(attempt.id)
    const items: AttemptAnswer[] = res.data || []
    gradeAnswers.value = items
    // 只预填「已批改」的分数；未批改的留空。
    // 若把未批改的一律填 0 并全量提交，教师只批一道题就会把其余主观题
    // 静默锁成「已批 0 分」，且 graded=True 后无法再回到待批状态。
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
              行为明细
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
      :title="currentAttempt ? `${currentAttempt.student_name} 的行为记录` : '行为记录'"
      size="480px"
    >
      <div v-loading="behaviorLoading" class="space-y-2 px-1">
        <div
          v-for="e in behaviorEvents"
          :key="e.id"
          class="flex items-start gap-3 rounded-lg border border-gray-100 px-3 py-2.5 dark:border-zinc-800"
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
      </div>
    </el-drawer>

    <el-drawer
      v-model="gradeDrawer"
      :title="gradingAttempt ? `批改 · ${gradingAttempt.student_name}` : '批改'"
      size="620px"
    >
      <div v-loading="gradeLoading" class="space-y-3 px-1">
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
              {{ typeLabel(a.question_type) }} · 满分 {{ a.max_score }}
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

          <div v-if="isManualType(a.question_type)" class="mt-3 flex items-center gap-2">
            <span class="text-xs text-gray-500 dark:text-zinc-400">给分</span>
            <el-input-number
              v-model="gradeScores[a.question_id]"
              :min="0"
              :max="a.max_score"
              :step="1"
              size="small"
              controls-position="right"
              class="w-28"
            />
            <span class="text-xs text-gray-400">/ {{ a.max_score }}</span>
          </div>
        </div>

        <div v-if="!gradeAnswers.length && !gradeLoading" class="py-12 text-center text-sm text-gray-400">
          暂无作答内容
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <el-button @click="gradeDrawer = false">取消</el-button>
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