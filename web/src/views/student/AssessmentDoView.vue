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
const questions = ref<StudentQuestion[]>([])
const attempt = ref<StudentAttempt | null>(null)
const answers = ref<Record<string, any>>({})
const submitted = ref(false)
const result = ref<StudentAttempt | null>(null)
const elapsedSeconds = ref(0)

let sessionId = ''
let timer: number | undefined
let autosaveTimer: number | undefined

const generateSessionId = () => {
  try {
    return crypto.randomUUID()
  } catch {
    return `sess_${Date.now()}_${Math.random().toString(36).slice(2)}`
  }
}

const antiCheat = useAntiCheat({ maxFullscreenExits: 3 })

const showOverlay = computed(
  () => !submitted.value && antiCheat.fullscreenExitCount.value > 0 && !antiCheat.fullscreenActive.value
)

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

const reportEvents = (events: BehaviorEventPayload[]) => {
  assessmentApi
    .reportBehavior({
      session_id: sessionId,
      attempt_id: attempt.value?.id ?? null,
      events
    })
    .catch(() => {})
}

const submit = async (auto = false) => {
  if (submitted.value || !attempt.value) return false
  submitted.value = true
  try {
    const answerList = Object.entries(answers.value).map(([question_id, answer]) => ({
      question_id,
      answer
    }))
    const res = await assessmentApi.submitAttempt(attempt.value.id, answerList)
    result.value = res.data
    antiCheat.stopTracking()
    await antiCheat.exitFullscreen()
    ElMessage.success(auto ? '检测到多次退出全屏，已自动交卷' : '交卷成功')
    return true
  } catch (err) {
    submitted.value = false
    if (!auto) ElMessage.error('交卷失败，请重试')
    return false
  }
}

const handleAutoSubmit = () => {
  ElMessageBox.alert('你已连续多次退出全屏，本次作答将自动交卷。', '防作弊提醒', {
    confirmButtonText: '知道了'
  })
  submit(true)
}

const handleRestoreFullscreen = () => {
  antiCheat.enterFullscreen()
}

const autosave = async () => {
  if (!attempt.value || submitted.value) return
  const answerList = Object.entries(answers.value).map(([question_id, answer]) => ({
    question_id,
    answer
  }))
  if (!answerList.length) return
  try {
    await assessmentApi.saveAnswers(attempt.value.id, answerList)
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

const start = async () => {
  loading.value = true
  sessionId = generateSessionId()
  try {
    const [qRes, aRes] = await Promise.all([
      assessmentApi.getStudentQuestions(paperId),
      assessmentApi.startAttempt(paperId)
    ])
    questions.value = qRes.data || []
    attempt.value = aRes.data

    if (attempt.value && attempt.value.status === 'submitted') {
      result.value = attempt.value
      submitted.value = true
      ElMessage.info('该试卷已交卷，无法重复作答')
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

    // 已存在的草稿答案通过重新请求无法获取，这里仅初始化空答案
    answers.value = prefill(questions.value)

    antiCheat.startTracking(sessionId, attempt.value?.id ?? null, {
      reportEvents,
      onFullscreenExit: (count) => {
        ElMessage.warning(`已退出全屏 ${count} 次，请立即恢复全屏`)
      },
      onMaxViolations: handleAutoSubmit
    })
  } catch (err) {
    ElMessage.error('加载试卷失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  start()
  timer = window.setInterval(() => {
    if (!submitted.value) elapsedSeconds.value += 1
  }, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
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
          <p class="text-[11px] text-gray-400">已用时 {{ formattedElapsed }}</p>
        </div>
      </div>

      <div class="flex items-center gap-2">
        <button class="ui-button-secondary" @click="autosave">
          <Save class="h-3.5 w-3.5" />
          <span>保存草稿</span>
        </button>
        <button class="ui-button-primary" :disabled="submitted" @click="confirmSubmit">
          <Send class="h-3.5 w-3.5" />
          <span>{{ submitted ? '已交卷' : '交卷' }}</span>
        </button>
      </div>
    </div>

    <div v-if="result" class="surface-panel p-8 text-center">
      <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">本次作答已提交</p>
      <p class="mt-2 text-xs text-gray-400">得分 {{ result.score ?? 0 }} 分 · 用时 {{ result.duration_seconds ?? 0 }} 秒</p>
      <button class="ui-button-primary mt-4" @click="router.push('/student/assessment')">返回试卷列表</button>
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
            {{ typeLabel(q.question_type) }} · {{ q.score }} 分
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