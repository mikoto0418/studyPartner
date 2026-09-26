<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Timer,
  Maximize2,
  AlertTriangle,
  Send,
  Save,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  Play,
  FileText,
  CircleCheck,
  CircleX
} from 'lucide-vue-next'
import {
  assessmentApi,
  type StudentQuestion,
  type StudentAttempt,
  type BehaviorEventPayload,
  type CodeRunResult
} from '../../api/modules/assessment'
import { useAntiCheat } from '../../composables/useAntiCheat'
import RichStem from '../../components/assessment/RichStem.vue'
import MathText from '../../components/common/MathText.vue'

const route = useRoute()
const router = useRouter()

const paperId = String(route.params.id || '')
const loading = ref(false)
const starting = ref(false)
const started = ref(false)
const dueAt = ref<string | null>(null)
const answerDeadline = ref<string | null>(null)
const timeLimitMinutes = ref<number | null>(null)
const remainingSeconds = ref<number | null>(null)
// 截止后「从未开考」的试卷：startAttempt 会 400，此时没有 attempt、拿不到
// due_at，只能靠这个标志落到 isExpired 分支，否则页面停在空白卷面出不去。
const blockedByExpiry = ref(false)
const questions = ref<StudentQuestion[]>([])
const attempt = ref<StudentAttempt | null>(null)
const answers = ref<Record<string, any>>({})
const submitted = ref(false)
const pendingReview = ref(false)
const result = ref<StudentAttempt | null>(null)
const elapsedSeconds = ref(0)

// 一页一题：currentIndex 是当前展示的题目下标，答题卡按它跳转
const currentIndex = ref(0)
const sheetOpen = ref(false)
// 是否强制全屏由试卷配置决定，默认要求。load 里会按后端返回覆盖。
const requireFullscreen = ref(true)
// 编程题自测：逐题保存最近一次结果与自定义输入，切题回来还在
const runResults = ref<Record<string, CodeRunResult | null>>({})
const runInputs = ref<Record<string, string>>({})
const runningCode = ref(false)

let sessionId = ''
let timer: number | undefined
let autosaveTimer: number | undefined
let countdownTimer: number | undefined
let unmounted = false
// 自动交卷只触发一次：失败后交给学生手动交卷，避免每秒刷屏重试
let expirySubmitTriggered = false
let violationSubmitTriggered = false

const generateSessionId = () => {
  try {
    return crypto.randomUUID()
  } catch {
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`
  }
}

const antiCheat = useAntiCheat({ maxFullscreenExits: 3 })

// 作答中只要不在全屏就必须盖住 —— 但仅当试卷要求全屏时。
// 不能带上 fullscreenExitCount > 0 这个条件：若全屏压根没进去（被浏览器拒绝
// 或策略禁用），退出计数恒为 0，遮罩永不出现，学生就能全程窗口化作答。
const showOverlay = computed(
  () =>
    requireFullscreen.value &&
    started.value &&
    !submitted.value &&
    !antiCheat.fullscreenActive.value
)

// 窗口失焦 / 切后台时把卷面盖住：后台窗口仍在渲染，不遮挡的话
// 截图与录屏能完整抄走题目。恢复焦点后自动揭开。
const contentMasked = computed(
  () => started.value && !submitted.value && antiCheat.contentHidden.value
)

const isExpired = computed(
  () => blockedByExpiry.value || (remainingSeconds.value !== null && remainingSeconds.value <= 0)
)

const currentQuestion = computed<StudentQuestion | null>(
  () => questions.value[currentIndex.value] || null
)

const isFirstQuestion = computed(() => currentIndex.value <= 0)
const isLastQuestion = computed(() => currentIndex.value >= questions.value.length - 1)

// 答题卡：已作答 / 未作答 / 当前题，三态决定色块
const isAnswered = (q: StudentQuestion) => {
  const value = answers.value[q.id]
  if (Array.isArray(value)) return value.length > 0
  if (value === undefined || value === null) return false
  const text = String(value).trim()
  if (!text) return false
  // 编程题的起始代码是系统预填的，学生没动过就不算已作答 ——
  // 否则一进卷面全卷编程题都会显示成绿色，答题卡失去意义。
  if (q.question_type === 'code' && text === String(q.starter_code || '').trim()) {
    return false
  }
  return true
}

const answeredCount = computed(
  () => questions.value.filter((q) => isAnswered(q)).length
)

// 作答进度条按题数而不是分值算：学生关心的是「还剩几道没写」
const progressPercent = computed(() => {
  if (!questions.value.length) return 0
  return Math.round((answeredCount.value / questions.value.length) * 100)
})

const goTo = (index: number) => {
  if (index < 0 || index >= questions.value.length) return
  currentIndex.value = index
  sheetOpen.value = false
  // 一页一题没有滚动，逐题停留时长必须由切题动作显式告知，否则会记到错题上
  antiCheat.setCurrentQuestion(questions.value[index]?.id ?? null)
  window.scrollTo({ top: 0 })
}

const goPrev = () => goTo(currentIndex.value - 1)
const goNext = () => goTo(currentIndex.value + 1)

// 答题卡按 10 题一组分页展示，长卷（50+ 题）不会糊成一片
const SHEET_GROUP_SIZE = 10
const sheetGroups = computed(() => {
  const groups: Array<{ start: number; end: number; items: Array<{ index: number; q: StudentQuestion }> }> = []
  for (let start = 0; start < questions.value.length; start += SHEET_GROUP_SIZE) {
    const end = Math.min(start + SHEET_GROUP_SIZE, questions.value.length)
    groups.push({
      start,
      end,
      items: questions.value.slice(start, end).map((q, offset) => ({ index: start + offset, q }))
    })
  }
  return groups
})

const formattedRemaining = computed(() => {
  if (remainingSeconds.value === null) return ''
  const total = Math.max(0, remainingSeconds.value)
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const sec = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
})

const formattedElapsed = computed(() => {
  const h = Math.floor(elapsedSeconds.value / 3600)
  const m = Math.floor((elapsedSeconds.value % 3600) / 60)
  const s = elapsedSeconds.value % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${pad(h)}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
})

const typeLabel = (t: string) => {
  const map: Record<string, string> = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    fill: '填空题',
    short: '简答题',
    essay: '论述题',
    code: '编程题'
  }
  return map[t] || '题目'
}

const codeLanguageLabel = (lang?: string | null) => {
  const map: Record<string, string> = {
    python: 'Python 3',
    javascript: 'JavaScript (Node)',
    java: 'Java 17'
  }
  return map[lang || ''] || 'Python 3'
}

// 编程题预填起始代码：学生进来就有一份能改的骨架，不用从零敲。
const prefillCode = (q: StudentQuestion) => q.starter_code || ''

// 必须把 promise 交回给 useAntiCheat：上报失败时它会把这批事件放回队列重投
const reportEvents = (events: BehaviorEventPayload[]) => {
  return assessmentApi
    .reportBehavior({
      session_id: sessionId,
      attempt_id: attempt.value?.id ?? null,
      events
    })
    .then(() => undefined)
}

const submit = async (auto = false) => {
  if (submitted.value) return false
  if (!attempt.value) {
    ElMessage.warning('试卷未开始或已过期，无法交卷')
    return false
  }
  submitted.value = true
  try {
    const answerList = Object.entries(answers.value).map(([question_id, answer]) => ({
      question_id,
      answer
    }))
    const res = await assessmentApi.submitAttempt(attempt.value.id, answerList)
    result.value = res.data
    // 含主观题时后端返回 pending_review，此时分数只是客观题小计，
    // 不标记的话结果面板会把它当最终成绩展示。
    pendingReview.value = res.data?.status === 'pending_review'
    started.value = false
    antiCheat.stopTracking()
    await antiCheat.exitFullscreen()
    if (res.data?.answers_ignored) {
      ElMessage.warning('已超过截止时间，本次提交的作答未计入成绩')
    } else {
      ElMessage.success(auto ? '已自动交卷' : '交卷成功')
    }
    return true
  } catch (err) {
    // 竞态：autosave 的服务端强制交卷先落地时，再交卷会撞「不能重复提交」。
    // 此时本地已被 autosave 的分支切到已交卷态，不该报错，也不该复位状态。
    if (submitted.value && result.value) return true
    submitted.value = false
    ElMessage.error(auto ? '自动交卷失败，请手动点击交卷' : '交卷失败，请重试')
    return false
  }
}

const handleAutoSubmit = async () => {
  // onMaxViolations 在每次「已超上限的退出全屏」时都会回调，只处理一次
  if (violationSubmitTriggered || submitted.value) return
  violationSubmitTriggered = true
  ElMessageBox.alert('你已连续多次退出全屏，本次作答将自动交卷。', '防作弊提醒', {
    confirmButtonText: '知道了'
  })
  await submit(true)
}

const handleRestoreFullscreen = async () => {
  const entered = await antiCheat.enterFullscreen()
  if (!entered) {
    ElMessage.warning('未能进入全屏，请检查浏览器是否允许全屏')
  }
}

const autosave = async () => {
  if (!attempt.value || submitted.value) return
  const answerList = Object.entries(answers.value).map(([question_id, answer]) => ({
    question_id,
    answer
  }))
  if (!answerList.length) return
  try {
    const res = await assessmentApi.saveAnswers(attempt.value.id, answerList)
    const forced = res.data
    if (forced) {
      // 服务端因违规超限强制交卷：必须同步切到已交卷态，
      // 否则界面卡在作答中，而之后所有保存/交卷请求都会被拒。
      result.value = forced
      pendingReview.value = forced.status === 'pending_review'
      submitted.value = true
      started.value = false
      antiCheat.stopTracking()
      await antiCheat.exitFullscreen()
      ElMessage.warning('已超出全屏退出次数上限，本次作答已被强制交卷')
    }
  } catch (err) {
    // 草稿保存失败静默处理
  }
}

const confirmSubmit = () => {
  ElMessageBox.confirm('确认交卷？交卷后将无法修改答案。', '交卷确认', {
    confirmButtonText: '确认交卷',
    cancelButtonText: '继续检查',
    type: 'warning'
  })
    .then(() => submit(false))
    .catch(() => {})
}

const toggleOption = (questionId: string, key: string, multiple: boolean) => {
  if (submitted.value) return
  if (multiple) {
    const current = Array.isArray(answers.value[questionId]) ? [...answers.value[questionId]] : []
    const idx = current.indexOf(key)
    if (idx >= 0) current.splice(idx, 1)
    else current.push(key)
    answers.value[questionId] = current
  } else {
    answers.value[questionId] = key
  }
  scheduleAutosave()
}

const setJudge = (questionId: string, value: string) => {
  if (submitted.value) return
  answers.value[questionId] = value
  scheduleAutosave()
}

const onTextInput = (questionId: string, value: string) => {
  answers.value[questionId] = value
  scheduleAutosave()
}

const scheduleAutosave = () => {
  if (autosaveTimer) clearTimeout(autosaveTimer)
  autosaveTimer = window.setTimeout(autosave, 1500)
}

// ---------- 编程题自测 ----------
const currentRunResult = computed<CodeRunResult | null>(
  () => (currentQuestion.value ? runResults.value[currentQuestion.value.id] ?? null : null)
)

const runStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    ok: '自测通过',
    wrong_answer: '输出与期望不符',
    compile_error: '编译或语法未通过',
    runtime_error: '运行时报错',
    time_limit: '超时',
    judge_error: '判题服务异常'
  }
  return map[status] || status
}

const runCode = async () => {
  const q = currentQuestion.value
  if (!q || q.question_type !== 'code' || !attempt.value || runningCode.value) return
  const code = String(answers.value[q.id] || '')
  if (!code.trim()) {
    ElMessage.warning('先写点代码再自测')
    return
  }
  const stdin = runInputs.value[q.id]
  runningCode.value = true
  try {
    const res = await assessmentApi.runCode(attempt.value.id, q.id, {
      code,
      stdin: stdin && stdin.length ? stdin : null
    })
    runResults.value = { ...runResults.value, [q.id]: res.data }
    if (res.data?.status === 'ok') {
      ElMessage.success(stdin && stdin.length ? '自测运行完成' : '样例全部通过')
    } else if (res.data?.status === 'judge_error') {
      ElMessage.error(res.data?.message || '判题服务不可用')
    } else {
      ElMessage.warning(runStatusLabel(res.data?.status || ''))
    }
  } catch {
    // 错误已由拦截器提示
  } finally {
    runningCode.value = false
  }
}

const syncRemaining = () => {
  const raw = answerDeadline.value || dueAt.value
  if (!raw) {
    remainingSeconds.value = null
    return
  }
  const target = new Date(raw).getTime()
  if (Number.isNaN(target)) {
    remainingSeconds.value = null
    return
  }
  remainingSeconds.value = Math.max(0, Math.floor((target - Date.now()) / 1000))
}

const tickCountdown = () => {
  if (remainingSeconds.value === null || submitted.value) return
  syncRemaining()
  if (remainingSeconds.value <= 0 && !expirySubmitTriggered) {
    expirySubmitTriggered = true
    ElMessage.warning('作答时间已到，正在自动交卷')
    submit(true)
  }
}

// 必须由用户手势同步触发，否则 requestFullscreen 会被浏览器拒绝。
// requestFullscreen() 本身在这次点击里同步发起，await 的只是它的结果。
const beginAnswering = async () => {
  if (starting.value || started.value) return
  starting.value = true
  // 只有试卷要求全屏时才拦：进不去就不放行，否则学生在权限弹窗上点「拒绝」
  // 即可全程窗口化作答，而 fullscreenchange 从未触发，退出计数为 0。
  if (requireFullscreen.value) {
    const entered = await antiCheat.enterFullscreen()
    if (!entered) {
      ElMessage.warning('需要进入全屏才能开始作答，请在浏览器提示中允许全屏后重试')
      starting.value = false
      return
    }
  }
  started.value = true
  antiCheat.startTracking(sessionId, attempt.value?.id ?? null, {
    reportEvents,
    onFullscreenExit: (count) => {
      ElMessage.warning(`已退出全屏 ${count} 次，请立即恢复全屏`)
    },
    onMaxViolations: handleAutoSubmit
  })
  antiCheat.setCurrentQuestion(currentQuestion.value?.id ?? null)
  starting.value = false
}

const isExpiredError = (err: any) => {
  const msg = err?.response?.data?.message || err?.message || ''
  return String(msg).includes('截止时间')
}

const load = async () => {
  loading.value = true
  sessionId = generateSessionId()
  try {
    // 先取题目。startAttempt 在截止后会对「从未开考」的试卷返回 400，
    // 若与取题一起走 Promise.all，整页会停在「开始前请确认」：
    // 题目为空、交卷按钮点了没反应，学生出不去这个页面。
    const qRes = await assessmentApi.getStudentQuestions(paperId)
    questions.value = qRes.data || []

    let aRes
    try {
      aRes = await assessmentApi.startAttempt(paperId)
    } catch (err) {
      if (isExpiredError(err)) {
        // 走已有的 isExpired 分支，给出明确的「已超过截止时间」提示。
        // 不能只置 remainingSeconds：此时 dueAt 还是空的，syncRemaining()
        // 会把它重置回 null，isExpired 又变 false，页面退回死路。
        blockedByExpiry.value = true
        return
      }
      throw err
    }
    attempt.value = aRes.data
    answerDeadline.value = attempt.value?.answer_deadline ?? null

    // pending_review：客观题已判分、主观题待批改，同样属于已交卷，不能再作答
    if (attempt.value && (attempt.value.status === 'submitted' || attempt.value.status === 'pending_review')) {
      result.value = attempt.value
      submitted.value = true
      pendingReview.value = attempt.value.status === 'pending_review'
      ElMessage.info(pendingReview.value ? '该试卷已交卷，等待老师批改' : '该试卷已交卷，无法重复作答')
      loading.value = false
      return
    }

    const prefill = (queries: StudentQuestion[]) => {
      const map: Record<string, any> = {}
      queries.forEach((q) => {
        if (q.question_type === 'multiple') {
          map[q.id] = []
        } else if (q.question_type === 'code') {
          map[q.id] = prefillCode(q)
        } else {
          map[q.id] = ''
        }
      })
      return map
    }

    // 回填已保存的答案，否则学生刷新后会看到空白卷面，
    // 而库里那些答案仍在参与判分。
    answers.value = prefill(questions.value)
    try {
      const savedRes = await assessmentApi.getStudentAnswers(paperId)
      const saved: Array<{ question_id: string; answer?: any }> = savedRes.data?.answers || []
      saved.forEach((item) => {
        // 只回填真正写过的答案：库里把「未作答」存成空串，直接覆盖会把起始代码清掉
        if (item.question_id in answers.value && item.answer !== null && item.answer !== undefined && item.answer !== '') {
          answers.value[item.question_id] = item.answer
        }
      })
    } catch {
      // 回读失败时保留空白卷面，不阻断作答
    }

    // 截止时间仅用于前端提示，真正的拦截在后端
    try {
      const listRes = await assessmentApi.listStudentPapers()
      const meta = (listRes.data || []).find((item: any) => String(item.id) === paperId)
      dueAt.value = meta?.due_at ?? null
      timeLimitMinutes.value = meta?.time_limit_minutes ?? null
      // 未配置的老数据按「要求全屏」处理，与后端 require_fullscreen_of 一致
      requireFullscreen.value = meta?.require_fullscreen !== false
      antiCheat.setEnforceFullscreen(requireFullscreen.value)
    } catch {
      dueAt.value = null
    }
    syncRemaining()
  } catch (err) {
    ElMessage.error('加载试卷失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await load()
  // load 期间可能已经切走；此时 onUnmounted 早已跑完，再建 interval 就没人清了。
  if (unmounted) return
  if (!submitted.value) tickCountdown()
  timer = window.setInterval(() => {
    if (!submitted.value && started.value) elapsedSeconds.value += 1
  }, 1000)
  countdownTimer = window.setInterval(tickCountdown, 1000)
})

onUnmounted(() => {
  unmounted = true
  if (timer) clearInterval(timer)
  if (countdownTimer) clearInterval(countdownTimer)
  if (autosaveTimer) clearTimeout(autosaveTimer)
  antiCheat.stopTracking()})
</script>

<template>
  <div v-loading="loading" class="space-y-5">
    <div class="surface-panel sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 p-4">
      <div class="flex items-center gap-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
          <Timer class="h-4.5 w-4.5" />
        </div>
        <div>
          <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">在线作答</p>
          <p class="text-[11px] text-gray-400">
            已用时 {{ formattedElapsed }}
            <span v-if="remainingSeconds !== null" :class="isExpired ? 'text-red-500' : 'text-amber-500'">
              · 剩余 {{ formattedRemaining }}
            </span>
            <span v-if="started && questions.length">· 已答 {{ answeredCount }} / {{ questions.length }}</span>
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button
          v-if="started && questions.length"
          class="ui-button-secondary"
          @click="sheetOpen = true"
        >
          <LayoutGrid class="h-3.5 w-3.5" />
          <span>答题卡</span>
        </button>
        <button class="ui-button-secondary" :disabled="!started || submitted" @click="autosave">
          <Save class="h-3.5 w-3.5" />
          <span>保存草稿</span>
        </button>
        <button class="ui-button-primary" :disabled="!started || submitted" @click="confirmSubmit">
          <Send class="h-3.5 w-3.5" />
          <span>{{ submitted ? '已交卷' : '交卷' }}</span>
        </button>
      </div>
    </div>

    <div v-if="started && questions.length" class="surface-panel-soft h-1.5 w-full overflow-hidden rounded-full">
      <div
        class="h-full rounded-full bg-blue-600 transition-all duration-300"
        :style="{ width: progressPercent + '%' }"
      />
    </div>

    <div v-if="result" class="surface-panel overflow-hidden">
      <div class="flex flex-col items-center border-b border-gray-100 px-8 py-10 text-center dark:border-zinc-800">
        <div
          class="mb-4 flex h-14 w-14 items-center justify-center rounded-full"
          :class="pendingReview
            ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400'
            : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400'"
        >
          <CircleCheck v-if="!pendingReview" class="h-7 w-7" />
          <Timer v-else class="h-7 w-7" />
        </div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-zinc-50">本次作答已提交</h3>
        <p v-if="pendingReview" class="mt-2 max-w-md text-xs leading-relaxed text-amber-600 dark:text-amber-400">
          含主观题或编程题，待老师批改后给出最终成绩。当前已判部分 {{ result.score ?? 0 }} 分。
        </p>
      </div>

      <div class="grid grid-cols-2 divide-x divide-gray-100 dark:divide-zinc-800 sm:grid-cols-3">
        <div class="px-6 py-5 text-center">
          <p class="text-[11px] text-gray-400">
            <template v-if="pendingReview">已判得分</template>
            <template v-else>得分</template>
          </p>
          <p class="mt-1 text-2xl font-semibold text-gray-900 dark:text-zinc-50">{{ result.score ?? 0 }}</p>
        </div>
        <div class="px-6 py-5 text-center">
          <p class="text-[11px] text-gray-400">用时</p>
          <p class="mt-1 text-2xl font-semibold text-gray-900 dark:text-zinc-50">
            {{ Math.max(1, Math.round((result.duration_seconds ?? 0) / 60)) }}<span class="ml-0.5 text-xs font-normal text-gray-400">分钟</span>
          </p>
        </div>
        <div class="col-span-2 border-t border-gray-100 px-6 py-5 text-center dark:border-zinc-800 sm:col-span-1 sm:border-t-0">
          <p class="text-[11px] text-gray-400">状态</p>
          <p class="mt-1 text-sm font-semibold" :class="pendingReview ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'">
            {{ pendingReview ? '待老师批改' : '已批改完成' }}
          </p>
        </div>
      </div>

      <div class="flex flex-wrap justify-center gap-2 border-t border-gray-100 px-6 py-4 dark:border-zinc-800">
        <button class="ui-button-secondary" @click="router.push(`/student/assessment/${paperId}/review`)">
          查看逐题成绩
        </button>
        <button class="ui-button-primary" @click="router.push('/student/assessment')">返回试卷列表</button>
      </div>
    </div>

    <div v-else-if="isExpired" class="surface-panel flex flex-col items-center px-8 py-12 text-center">
      <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-50 text-red-500 dark:bg-red-950/30 dark:text-red-400">
        <AlertTriangle class="h-7 w-7" />
      </div>
      <h3 class="text-base font-semibold text-gray-900 dark:text-zinc-50">已超过截止时间</h3>
      <p class="mt-2 max-w-sm text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
        该试卷已无法继续作答。如果确实参加过作答，已提交的内容仍会参与批改，如有疑问请联系任课教师。
      </p>
      <button class="ui-button-secondary mt-6" @click="router.push('/student/assessment')">返回试卷列表</button>
    </div>

    <div v-else-if="!started" class="surface-panel p-8">
      <div class="flex flex-col items-center text-center">
        <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
          <Maximize2 v-if="requireFullscreen" class="h-7 w-7" />
          <FileText v-else class="h-7 w-7" />
        </div>
        <h3 class="text-base font-semibold text-gray-900 dark:text-zinc-50">开始前请确认</h3>
      </div>
      <ul class="mx-auto mt-5 grid max-w-2xl gap-2 text-xs text-gray-600 sm:grid-cols-2 dark:text-zinc-300">
        <li class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
          <span>
            <template v-if="requireFullscreen">进入作答后强制全屏，中途退出会被记录</template>
            <template v-else>本卷不限制作答环境，可窗口化作答</template>
          </span>
        </li>
        <li class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
          <span>一页一题，用「上一题 / 下一题」或答题卡切换</span>
        </li>
        <li class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
          <span>编程题可以随时点「运行自测」，用样例或自定义输入验证，不计入成绩</span>
        </li>
        <li class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-500" />
          <span>作答期间禁止复制、粘贴、右键与切换窗口{{ requireFullscreen ? '，连续退出全屏 3 次自动交卷' : '' }}</span>
        </li>
        <li v-if="timeLimitMinutes" class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500" />
          <span>限时 {{ timeLimitMinutes }} 分钟，从进入试卷开始计时</span>
        </li>
        <li v-if="remainingSeconds !== null" class="flex items-start gap-2 rounded-lg bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
          <span class="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-amber-500" />
          <span>剩余作答时间 {{ formattedRemaining }}，到时自动交卷</span>
        </li>
      </ul>
      <div class="mt-7 flex justify-center">
        <button
          class="ui-button-primary px-5 py-2.5 text-sm"
          :disabled="starting"
          @click="beginAnswering"
        >
          <Maximize2 v-if="requireFullscreen" class="h-4 w-4" />
          <Play v-else class="h-4 w-4" />
          {{ starting ? '正在进入…' : requireFullscreen ? '进入全屏并开始作答' : '开始作答' }}
        </button>
      </div>
    </div>

    <template v-else>
      <!-- 答题卡：一页一题，靠它和上下题按钮跳转 -->
      <el-drawer v-model="sheetOpen" title="答题卡" size="440px">
        <div class="space-y-5 px-1">
          <div class="flex items-center justify-between text-xs text-gray-500 dark:text-zinc-400">
            <span>已作答 {{ answeredCount }} / {{ questions.length }}</span>
            <span class="flex items-center gap-3">
              <span class="inline-flex items-center gap-1">
                <span class="h-2.5 w-2.5 rounded-sm bg-blue-600" />已答
              </span>
              <span class="inline-flex items-center gap-1">
                <span class="h-2.5 w-2.5 rounded-sm border border-gray-300 dark:border-zinc-600" />未答
              </span>
            </span>
          </div>

          <!-- 每组 10 题：长卷里挤在一行会让题号块又小又密 -->
          <div class="space-y-4">
            <div v-for="group in sheetGroups" :key="group.start" class="space-y-2">
              <p class="flex items-center justify-between text-[11px] text-gray-400">
                <span>第 {{ group.start + 1 }} - {{ group.end }} 题</span>
                <span>{{ group.items.filter((i) => isAnswered(i.q)).length }} / {{ group.items.length }} 已答</span>
              </p>
              <div class="grid grid-cols-5 gap-2">
                <button
                  v-for="item in group.items"
                  :key="item.q.id"
                  class="flex h-12 flex-col items-center justify-center gap-0.5 rounded-md border text-xs font-semibold transition"
                  :class="[
                    item.index === currentIndex ? 'ring-2 ring-blue-500/40' : '',
                    isAnswered(item.q)
                      ? 'border-blue-600 bg-blue-600 text-white'
                      : 'border-gray-200 bg-white text-gray-500 hover:border-blue-300 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400'
                  ]"
                  @click="goTo(item.index)"
                >
                  <span>{{ item.index + 1 }}</span>
                  <span class="text-[9px] font-normal opacity-80">{{ typeLabel(item.q.question_type) }}</span>
                </button>
              </div>
            </div>
          </div>

          <div class="flex items-center justify-between border-t border-gray-100 pt-4 text-xs text-gray-500 dark:border-zinc-800 dark:text-zinc-400">
            <span>未作答 {{ questions.length - answeredCount }} 题</span>
            <button class="ui-button-dark" @click="sheetOpen = false">继续作答</button>
          </div>
        </div>
      </el-drawer>

      <div v-if="!questions.length" class="surface-panel p-12 text-center text-sm text-gray-400">
        暂无题目
      </div>

      <div v-else-if="currentQuestion" class="space-y-4">
        <!-- 题目卡：整页只展示这一道，留足空间 -->
        <div class="surface-panel p-6" :data-ac-scroll-question="currentQuestion.id">
          <div class="mb-4 flex flex-wrap items-center gap-2">
            <span class="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
              第 {{ currentIndex + 1 }} 题 / 共 {{ questions.length }} 题
            </span>
            <span class="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
              {{ typeLabel(currentQuestion.question_type) }}
              <template v-if="currentQuestion.score === null || currentQuestion.score === undefined"> · 分值待定</template>
              <template v-else> · {{ currentQuestion.score }} 分</template>
            </span>
            <span
              v-if="isAnswered(currentQuestion)"
              class="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400"
            >
              <CircleCheck class="h-3 w-3" />已作答
            </span>
          </div>

          <RichStem
            :stem="currentQuestion.stem"
            :images="currentQuestion.stem_images"
            class="text-sm leading-relaxed text-gray-800 dark:text-zinc-100"
          />

          <div
            v-if="currentQuestion.question_type === 'single' || currentQuestion.question_type === 'multiple'"
            class="mt-5 space-y-2"
          >
            <p v-if="currentQuestion.question_type === 'multiple'" class="text-[11px] text-gray-400">多选题，可选多个选项</p>
            <button
              v-for="opt in currentQuestion.options || []"
              :key="opt.key"
              class="flex w-full items-center gap-3 rounded-lg border px-4 py-3 text-left transition"
              :class="answers[currentQuestion.id] === opt.key || (Array.isArray(answers[currentQuestion.id]) && answers[currentQuestion.id].includes(opt.key))
                ? 'border-blue-500 bg-blue-50/60 dark:bg-blue-950/20'
                : 'border-gray-200 hover:border-blue-300 dark:border-zinc-800'"
              @click="toggleOption(currentQuestion!.id, opt.key, currentQuestion!.question_type === 'multiple')"
            >
              <span
                class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold"
                :class="answers[currentQuestion.id] === opt.key || (Array.isArray(answers[currentQuestion.id]) && answers[currentQuestion.id].includes(opt.key))
                  ? 'border-blue-500 bg-blue-600 text-white'
                  : 'border-gray-300 text-gray-400 dark:border-zinc-700'"
              >
                {{ opt.key }}
              </span>
              <MathText :text="opt.text" class="text-sm text-gray-700 dark:text-zinc-200" />
            </button>
          </div>

          <div v-else-if="currentQuestion.question_type === 'judge'" class="mt-5 flex gap-3">
            <button
              class="ui-button-secondary px-8 py-3 text-sm"
              :class="answers[currentQuestion.id] === '对' ? 'ring-2 ring-blue-500' : ''"
              data-ac-target="judge"
              :data-ac-question="currentQuestion.id"
              data-ac-field="对"
              @click="setJudge(currentQuestion!.id, '对')"
            >
              对
            </button>
            <button
              class="ui-button-secondary px-8 py-3 text-sm"
              :class="answers[currentQuestion.id] === '错' ? 'ring-2 ring-blue-500' : ''"
              data-ac-target="judge"
              :data-ac-question="currentQuestion.id"
              data-ac-field="错"
              @click="setJudge(currentQuestion!.id, '错')"
            >
              错
            </button>
          </div>

          <div v-else-if="currentQuestion.question_type === 'code'" class="mt-5 space-y-4">
            <div class="flex flex-wrap items-center gap-2 text-[11px] text-gray-500 dark:text-zinc-400">
              <span class="rounded bg-gray-100 px-2 py-0.5 font-semibold dark:bg-zinc-800">
                {{ codeLanguageLabel(currentQuestion.language) }}
              </span>
              <span>从标准输入读数据，结果打印到标准输出</span>
            </div>

            <div v-if="currentQuestion.sample_cases?.length" class="space-y-2">
              <p class="text-[11px] font-semibold text-gray-400">样例</p>
              <div
                v-for="(c, ci) in currentQuestion.sample_cases"
                :key="ci"
                class="grid gap-3 rounded-lg border border-gray-100 px-4 py-3 text-xs sm:grid-cols-2 dark:border-zinc-800"
              >
                <div>
                  <p class="text-gray-400">输入</p>
                  <pre class="mt-1 whitespace-pre-wrap break-words font-mono text-gray-700 dark:text-zinc-200">{{ c.input || '（空）' }}</pre>
                </div>
                <div>
                  <p class="text-gray-400">期望输出</p>
                  <pre class="mt-1 whitespace-pre-wrap break-words font-mono text-gray-700 dark:text-zinc-200">{{ c.expected_output || '（空）' }}</pre>
                </div>
              </div>
            </div>

            <textarea
              :value="answers[currentQuestion.id] || ''"
              rows="16"
              spellcheck="false"
              placeholder="在这里写你的代码（禁止粘贴）"
              class="ui-field resize-y font-mono text-xs leading-relaxed"
              data-ac-target="answer"
              :data-ac-question="currentQuestion.id"
              data-ac-field="code"
              @input="onTextInput(currentQuestion!.id, ($event.target as HTMLTextAreaElement).value)"
            ></textarea>

            <div class="rounded-lg border border-gray-100 p-4 dark:border-zinc-800">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p class="text-xs font-semibold text-gray-800 dark:text-zinc-100">自测</p>
                  <p class="mt-0.5 text-[11px] text-gray-400">
                    自测只跑样例，不会影响成绩。留空输入则逐个跑样例，填了就按你的输入跑一次。
                  </p>
                </div>
                <button
                  class="ui-button-primary"
                  :disabled="runningCode"
                  @click="runCode"
                >
                  <Play class="h-3.5 w-3.5" />
                  <span>{{ runningCode ? '运行中…' : '运行自测' }}</span>
                </button>
              </div>

              <label class="mt-3 block space-y-1">
                <span class="text-[11px] text-gray-400">自定义输入（可选）</span>
                <textarea
                  :value="runInputs[currentQuestion.id] || ''"
                  rows="3"
                  spellcheck="false"
                  placeholder="留空表示按上面的样例逐个运行"
                  class="ui-field font-mono text-xs"
                  @input="runInputs = { ...runInputs, [currentQuestion!.id]: ($event.target as HTMLTextAreaElement).value }"
                ></textarea>
              </label>

              <div v-if="currentRunResult" class="mt-3 space-y-2">
                <p
                  class="text-[11px] font-semibold"
                  :class="currentRunResult.status === 'ok' ? 'text-emerald-600' : 'text-amber-600'"
                >
                  {{ runStatusLabel(currentRunResult.status) }}
                  <span v-if="currentRunResult.runs_left >= 0" class="ml-1 font-normal text-gray-400">
                    · 剩余自测 {{ currentRunResult.runs_left }} 次
                  </span>
                </p>
                <pre
                  v-if="currentRunResult.compile_output"
                  class="max-h-40 overflow-auto whitespace-pre-wrap break-words rounded bg-red-50/70 p-2 font-mono text-[11px] text-red-700 dark:bg-red-950/20 dark:text-red-300"
                >{{ currentRunResult.compile_output }}</pre>
                <div
                  v-for="c in currentRunResult.cases"
                  :key="c.index"
                  class="rounded bg-gray-50 px-3 py-2 text-[11px] dark:bg-zinc-900/60"
                >
                  <p
                    class="flex items-center gap-1.5 font-semibold"
                    :class="c.passed === false ? 'text-red-500' : c.passed === true ? 'text-emerald-600' : 'text-gray-500'"
                  >
                    <CircleCheck v-if="c.passed === true" class="h-3 w-3" />
                    <CircleX v-else-if="c.passed === false" class="h-3 w-3" />
                    用例 {{ c.index + 1 }}
                    <span v-if="c.passed === null" class="font-normal text-gray-400">（自定义输入，不比对期望输出）</span>
                  </p>
                  <p class="mt-1 text-gray-500 dark:text-zinc-400">
                    输入 <code class="font-mono">{{ c.input || '（空）' }}</code>
                    <template v-if="c.expected_output">
                      · 期望 <code class="font-mono">{{ c.expected_output }}</code>
                    </template>
                  </p>
                  <p class="mt-1 text-gray-700 dark:text-zinc-200">
                    实际输出 <code class="font-mono">{{ c.actual_output || '（无输出）' }}</code>
                  </p>
                  <p v-if="c.stderr" class="mt-1 whitespace-pre-wrap break-words font-mono text-red-500">{{ c.stderr }}</p>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="mt-5">
            <textarea
              :value="answers[currentQuestion.id] || ''"
              rows="8"
              placeholder="请输入你的答案（禁止粘贴）"
              class="ui-field resize-y"
              data-ac-target="answer"
              :data-ac-question="currentQuestion.id"
              data-ac-field="text"
              @input="onTextInput(currentQuestion!.id, ($event.target as HTMLTextAreaElement).value)"
            ></textarea>
          </div>
        </div>

        <!-- 上一题 / 答题卡 / 下一题 -->
        <div class="surface-panel flex flex-wrap items-center justify-between gap-3 p-4">
          <button class="ui-button-secondary" :disabled="isFirstQuestion" @click="goPrev">
            <ChevronLeft class="h-3.5 w-3.5" />
            <span>上一题</span>
          </button>
          <div class="flex items-center gap-3">
            <button class="ui-button-secondary" @click="sheetOpen = true">
              <LayoutGrid class="h-3.5 w-3.5" />
              <span>答题卡</span>
            </button>
            <span class="text-[11px] text-gray-400">{{ currentIndex + 1 }} / {{ questions.length }}</span>
          </div>
          <button
            v-if="!isLastQuestion"
            class="ui-button-primary"
            @click="goNext"
          >
            <span>下一题</span>
            <ChevronRight class="h-3.5 w-3.5" />
          </button>
          <button v-else class="ui-button-primary" @click="confirmSubmit">
            <Send class="h-3.5 w-3.5" />
            <span>交卷</span>
          </button>
        </div>
      </div>
    </template>

    <!-- 失焦/切后台时盖住卷面：后台窗口仍在渲染，不遮的话截图录屏能把题抄走。
         全屏遮罩优先级更高，两者同时成立时只显示全屏那条。 -->
    <div
      v-if="contentMasked && !showOverlay"
      class="fixed inset-0 z-40 flex flex-col items-center justify-center bg-zinc-950 px-6 text-center"
    >
      <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/20 text-amber-400">
        <AlertTriangle class="h-7 w-7" />
      </div>
      <h3 class="text-lg font-semibold text-white">页面已暂时隐藏</h3>
      <p class="mt-2 max-w-sm text-sm text-zinc-400">
        检测到窗口失去焦点。为保护试题内容，作答界面已遮挡，请点击本页面继续作答。
      </p>
    </div>

    <div
      v-if="showOverlay"
      class="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/80 px-6 text-center"
    >
      <div class="mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-red-500/20 text-red-400">
        <AlertTriangle class="h-7 w-7" />
      </div>
      <h3 class="text-lg font-semibold text-white">已退出全屏模式</h3>
      <p class="mt-2 max-w-sm text-sm text-zinc-300">
        <template v-if="antiCheat.fullscreenExitCount.value > 0">
          在线考试要求保持全屏。已退出 {{ antiCheat.fullscreenExitCount.value }} 次，连续退出将被自动交卷。
        </template>
        <template v-else>
          在线考试要求保持全屏，当前不在全屏状态，作答已暂停。请点击下方按钮回到全屏继续作答。
        </template>
      </p>
      <button class="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500" @click="handleRestoreFullscreen">
        <Maximize2 class="h-4 w-4" />
        恢复全屏作答
      </button>
    </div>
  </div>
</template>