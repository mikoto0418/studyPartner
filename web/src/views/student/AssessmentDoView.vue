<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Timer, Maximize2, AlertTriangle, Send, Save } from 'lucide-vue-next'
import {
  assessmentApi,
  type StudentQuestion,
  type StudentAttempt,
  type BehaviorEventPayload
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

const showOverlay = computed(
  () => started.value && !submitted.value && antiCheat.fullscreenExitCount.value > 0 && !antiCheat.fullscreenActive.value
)

// 窗口失焦 / 切后台时把卷面盖住：后台窗口仍在渲染，不遮挡的话
// 截图与录屏能完整抄走题目。恢复焦点后自动揭开。
const contentMasked = computed(
  () => started.value && !submitted.value && antiCheat.contentHidden.value
)

const isExpired = computed(
  () => blockedByExpiry.value || (remainingSeconds.value !== null && remainingSeconds.value <= 0)
)

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
    essay: '论述题'
  }
  return map[t] || '题目'
}

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
  // 进不去全屏就不放行：否则学生在权限弹窗上点「拒绝」即可全程窗口化作答，
  // 而 fullscreenchange 从未触发，退出计数为 0，防作弊完全失效。
  const entered = await antiCheat.enterFullscreen()
  if (!entered) {
    ElMessage.warning('需要进入全屏才能开始作答，请在浏览器提示中允许全屏后重试')
    starting.value = false
    return
  }
  started.value = true
  antiCheat.startTracking(sessionId, attempt.value?.id ?? null, {
    reportEvents,
    onFullscreenExit: (count) => {
      ElMessage.warning(`已退出全屏 ${count} 次，请立即恢复全屏`)
    },
    onMaxViolations: handleAutoSubmit
  })
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
        if (item.question_id in answers.value) {
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
  antiCheat.stopTracking()
})
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
          </p>
        </div>
      </div>

      <div class="flex items-center gap-2">
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

    <div v-if="result" class="surface-panel p-8 text-center">
      <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">本次作答已提交</p>
      <p v-if="pendingReview" class="mt-2 text-xs text-amber-500">
        含主观题，待老师批改后给出最终成绩（当前客观题得分 {{ result.score ?? 0 }} 分）
      </p>
      <p v-else class="mt-2 text-xs text-gray-400">得分 {{ result.score ?? 0 }} 分 · 用时 {{ result.duration_seconds ?? 0 }} 秒</p>
      <p v-if="pendingReview" class="mt-1 text-xs text-gray-400">用时 {{ result.duration_seconds ?? 0 }} 秒</p>
      <button class="ui-button-secondary mt-4 mr-2" @click="router.push(`/student/assessment/${paperId}/review`)">查看逐题成绩</button>
      <button class="ui-button-primary mt-4" @click="router.push('/student/assessment')">返回试卷列表</button>
    </div>

    <div v-else-if="isExpired" class="surface-panel p-8 text-center">
      <p class="text-sm font-semibold text-red-500">已超过截止时间</p>
      <p class="mt-2 text-xs text-gray-400">该试卷已无法继续作答，如有疑问请联系任课教师。</p>
      <button class="ui-button-secondary mt-4" @click="router.push('/student/assessment')">返回试卷列表</button>
    </div>

    <div v-else-if="!started" class="surface-panel p-8 text-center">
      <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
        <AlertTriangle class="h-7 w-7" />
      </div>
      <h3 class="text-base font-semibold text-gray-900 dark:text-zinc-50">开始前请确认</h3>
      <ul class="mx-auto mt-4 max-w-md space-y-1.5 text-left text-xs text-gray-500 dark:text-zinc-400">
        <li>· 点击下方按钮后将进入全屏作答，中途退出全屏会被记录</li>
        <li>· 作答期间禁止复制、粘贴、右键与切换窗口</li>
        <li>· 连续退出全屏 3 次将自动交卷</li>
        <li v-if="timeLimitMinutes">· 限时 {{ timeLimitMinutes }} 分钟，从进入试卷开始计时</li>
        <li v-if="remainingSeconds !== null">· 剩余作答时间 {{ formattedRemaining }}，到时自动交卷</li>
      </ul>
      <button
        class="ui-button-primary mt-6 inline-flex items-center gap-2"
        :disabled="starting"
        @click="beginAnswering"
      >
        <Maximize2 class="h-4 w-4" />
        进入全屏并开始作答
      </button>
    </div>

    <div v-else class="space-y-5">
      <div
        v-for="(q, index) in questions"
        :key="q.id"
        class="surface-panel p-5"
        :data-ac-scroll-question="q.id"
      >
        <div class="mb-3 flex items-center gap-2">
          <span class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
            {{ index + 1 }}
          </span>
          <span class="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
            {{ typeLabel(q.question_type) }}
            <template v-if="q.score === null || q.score === undefined"> · 分值待定</template>
            <template v-else> · {{ q.score }} 分</template>
          </span>
        </div>

        <RichStem :stem="q.stem" :images="q.stem_images" class="text-sm leading-relaxed text-gray-800 dark:text-zinc-100" />

        <div v-if="q.question_type === 'single' || q.question_type === 'multiple'" class="mt-4 space-y-2">
          <div
            v-for="opt in q.options || []"
            :key="opt.key"
            class="flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2.5 transition"
            :class="answers[q.id] === opt.key || (Array.isArray(answers[q.id]) && answers[q.id].includes(opt.key))
              ? 'border-blue-500 bg-blue-50/60 dark:bg-blue-950/20'
              : 'border-gray-200 hover:border-blue-200 dark:border-zinc-800'"
            @click="toggleOption(q.id, opt.key, q.question_type === 'multiple')"
          >
            <span
              class="flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full border text-[10px] font-semibold"
              :class="answers[q.id] === opt.key || (Array.isArray(answers[q.id]) && answers[q.id].includes(opt.key))
                ? 'border-blue-500 bg-blue-600 text-white'
                : 'border-gray-300 text-transparent dark:border-zinc-700'"
            >
              {{ opt.key }}
            </span>
            <MathText :text="opt.text" class="text-sm text-gray-700 dark:text-zinc-200" />
          </div>
        </div>

        <div v-else-if="q.question_type === 'judge'" class="mt-4 flex gap-3">
          <button
            class="ui-button-secondary"
            :class="answers[q.id] === '对' ? 'ring-2 ring-blue-500' : ''"
            data-ac-target="judge"
            :data-ac-question="q.id"
            data-ac-field="对"
            @click="setJudge(q.id, '对')"
          >
            对
          </button>
          <button
            class="ui-button-secondary"
            :class="answers[q.id] === '错' ? 'ring-2 ring-blue-500' : ''"
            data-ac-target="judge"
            :data-ac-question="q.id"
            data-ac-field="错"
            @click="setJudge(q.id, '错')"
          >
            错
          </button>
        </div>

        <div v-else class="mt-4">
          <textarea
            :value="answers[q.id] || ''"
            rows="5"
            placeholder="请输入你的答案（禁止粘贴）"
            class="ui-field resize-none"
            data-ac-target="answer"
            :data-ac-question="q.id"
            data-ac-field="text"
            @input="onTextInput(q.id, ($event.target as HTMLTextAreaElement).value)"
          ></textarea>
        </div>
      </div>

      <div v-if="questions.length === 0" class="surface-panel p-12 text-center text-sm text-gray-400">
        暂无题目
      </div>
    </div>

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
        在线考试要求保持全屏。已退出 {{ antiCheat.fullscreenExitCount.value }} 次，连续退出将被自动交卷。
      </p>
      <button class="mt-6 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-blue-500" @click="handleRestoreFullscreen">
        <Maximize2 class="h-4 w-4" />
        恢复全屏作答
      </button>
    </div>
  </div>
</template>