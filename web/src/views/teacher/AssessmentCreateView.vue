<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  Clock,
  Eye,
  FileText,
  FileUp,
  Loader2,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Trophy,
  Wand2,
  X
} from 'lucide-vue-next'
import QuestionEditor from '../../components/assessment/QuestionEditor.vue'
import RichStem from '../../components/assessment/RichStem.vue'
import { assessmentApi } from '../../api/modules/assessment'
import { learningPathApi } from '../../api/modules/learning_path'
import { userApi } from '../../api/modules/user'
import { useAuthStore } from '../../stores/auth'

const activeStep = ref(0)
const title = ref('')
const description = ref('')
const selectedFile = ref<File | null>(null)
const dragActive = ref(false)
const paperId = ref<string | null>(null)
const parseError = ref('')
const progress = ref<{ stage?: string; total?: number; done?: number; channel?: string }>({})
const questions = ref<any[]>([])
const loading = ref(false)
const retrying = ref(false)
const saving = ref(false)
const publishing = ref(false)
const published = ref(false)

const publishType = ref('class')
const targetIds = ref('')
const whitelistIds = ref('')
const blacklistIds = ref('')
const publishAt = ref<Date | null>(null)
const dueAt = ref<Date | null>(null)
const timeLimitMinutes = ref<number | null>(null)

// 主观题批阅倾向：随发布保存，AI 预批阅和人工批改都按它执行
const gradingMode = ref<'lenient' | 'standard' | 'strict'>('standard')
const gradingExtra = ref('')

const classList = ref<any[]>([])
const selectedClassId = ref('')
const classStudents = ref<any[]>([])
const classStudentsLoading = ref(false)
const publishScope = ref<'all' | 'subset'>('all')
const selectedStudentIds = ref<string[]>([])

const guidedStudents = ref<any[]>([])
const guidedStudentsLoading = ref(false)
const selectedGuidedStudentIds = ref<string[]>([])

const viewMode = ref<'list' | 'create'>('list')
const papers = ref<any[]>([])
const papersLoading = ref(false)
const viewVisible = ref(false)
const viewTitle = ref('')
const viewQuestions = ref<any[]>([])

const STEPS = [
  { key: 0, title: '上传文件', desc: '选择试卷文档' },
  { key: 1, title: 'AI 拆题', desc: '自动识别题目结构' },
  { key: 2, title: '人工校对', desc: '补全分值与答案' },
  { key: 3, title: '发布', desc: '指定发布对象' }
]

const questionTypeLabels = {
  single: '单选题',
  multiple: '多选题',
  judge: '判断题',
  fill: '填空题',
  short: '简答题',
  essay: '论述题'
} as Record<string, string>

const ACCEPTED_EXTS = ['.pdf', '.docx', '.doc', '.md', '.markdown', '.txt']

let pollTimer: number | null = null
let stalledPolls = 0
// 约 2 分钟没有任何状态推进就提示排查方向：任务可能没被 worker 消费
const STALLED_POLL_LIMIT = 60

// 草稿含标准答案，key 必须绑定当前账号，避免同一浏览器换账号后读到他人草稿
const authStore = useAuthStore()
const DRAFT_KEY = computed(() => `assessment_workbench_draft:${authStore.username || 'anonymous'}`)
const hasDraft = ref(false)

function hasMeaningfulDraft(): boolean {
  if (published.value) return false
  return !!(
    title.value.trim() ||
    description.value.trim() ||
    paperId.value ||
    questions.value.length ||
    activeStep.value > 0 ||
    targetIds.value.trim() ||
    whitelistIds.value.trim() ||
    blacklistIds.value.trim() ||
    gradingExtra.value.trim() ||
    selectedClassId.value ||
    selectedStudentIds.value.length ||
    selectedGuidedStudentIds.value.length
  )
  // 注意：不要把 selectedFile 计入草稿判定 —— File 对象无法 JSON 序列化，
  // 写进 localStorage 的草稿里并不含它，恢复出来会是一份空草稿。
}

function buildDraft() {
  return {
    viewMode: viewMode.value,
    activeStep: activeStep.value,
    title: title.value,
    description: description.value,
    paperId: paperId.value,
    parseError: parseError.value,
    progress: progress.value,
    questions: questions.value,
    publishType: publishType.value,
    targetIds: targetIds.value,
    whitelistIds: whitelistIds.value,
    blacklistIds: blacklistIds.value,
    publishAt: publishAt.value ? publishAt.value.toISOString() : null,
    dueAt: dueAt.value ? dueAt.value.toISOString() : null,
    timeLimitMinutes: timeLimitMinutes.value,
    gradingMode: gradingMode.value,
    gradingExtra: gradingExtra.value,
    selectedClassId: selectedClassId.value,
    publishScope: publishScope.value,
    selectedStudentIds: selectedStudentIds.value,
    selectedGuidedStudentIds: selectedGuidedStudentIds.value,
    published: published.value
  }
}

const draftJson = computed(() => (hasMeaningfulDraft() ? JSON.stringify(buildDraft()) : ''))

function persistNow() {
  try {
    if (draftJson.value) {
      localStorage.setItem(DRAFT_KEY.value, draftJson.value)
      hasDraft.value = true
    } else {
      localStorage.removeItem(DRAFT_KEY.value)
      hasDraft.value = false
    }
  } catch {
    // 忽略本地存储不可用
  }
}

watch(draftJson, () => persistNow())

function onPageHide() {
  persistNow()
}

function loadDraft(): any | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY.value)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function applyDraft(d: any) {
  viewMode.value = d.viewMode === 'list' ? 'list' : 'create'
  activeStep.value = d.activeStep ?? 0
  title.value = d.title || ''
  description.value = d.description || ''
  paperId.value = d.paperId || null
  parseError.value = d.parseError || ''
  progress.value = d.progress || {}
  questions.value = d.questions || []
  publishType.value = d.publishType || 'class'
  targetIds.value = d.targetIds || ''
  whitelistIds.value = d.whitelistIds || ''
  blacklistIds.value = d.blacklistIds || ''
  published.value = !!d.published
  selectedClassId.value = d.selectedClassId || ''
  publishScope.value = d.publishScope || 'all'
  selectedStudentIds.value = d.selectedStudentIds || []
  selectedGuidedStudentIds.value = d.selectedGuidedStudentIds || []
  publishAt.value = d.publishAt ? new Date(d.publishAt) : null
  dueAt.value = d.dueAt ? new Date(d.dueAt) : null
  timeLimitMinutes.value = d.timeLimitMinutes || null
  gradingMode.value = d.gradingMode || 'standard'
  gradingExtra.value = d.gradingExtra || ''
  hasDraft.value = true
}

function restoreDraft() {
  const d = loadDraft()
  if (!d || d.published) {
    try {
      localStorage.removeItem(DRAFT_KEY.value)
    } catch {}
    hasDraft.value = false
    viewMode.value = 'list'
    return
  }
  applyDraft(d)
  if (d.selectedClassId) {
    onClassChange(d.selectedClassId).then(() => {
      selectedStudentIds.value = d.selectedStudentIds || []
    })
  }
  if (d.activeStep === 1 && d.paperId) {
    startPolling()
  }
}

const progressPercent = computed(() => {
  const total = progress.value.total || 0
  const done = progress.value.done || 0
  if (!total) return done ? 100 : 0
  return Math.min(100, Math.round((done / total) * 100))
})

const progressLabel = computed(() => {
  const stage = progress.value.stage || ''
  if (stage === 'downloading') return '正在下载文件…'
  if (stage === 'extracting') return 'AI 正在逐段识别题目…'
  if (stage === 'done') return '拆题完成'
  if (stage === 'failed') return '拆题失败'
  return '排队等待中…'
})

const progressHint = computed(() => {
  const stage = progress.value.stage || ''
  if (stage === 'extracting') {
    const total = progress.value.total || 0
    const done = progress.value.done || 0
    if (total) return `已完成 ${done} / ${total} 个分块，请勿关闭页面`
    return '正在按分块顺序调用模型，整卷通常需要几分钟'
  }
  if (stage === 'downloading') return '正在从对象存储取回原始文档'
  if (stage === 'done') return '马上进入人工校对'
  if (stage === 'failed') return '可查看下方原因后重试，或直接手工出题'
  return '任务已提交，等待后台开始处理'
})

// 后台任务的执行通道：inline 说明本地没有 worker，任务在 API 进程里跑
const channelLabel = computed(() => {
  const ch = progress.value.channel
  if (ch === 'celery') return '后台队列'
  if (ch === 'inline') return '本地进程'
  return ''
})

const unsetScoreCount = computed(
  () => questions.value.filter((q) => q.score === null || q.score === undefined).length
)

const totalScorePreview = computed(() =>
  questions.value.reduce((sum, q) => sum + (Number(q.score) || 0), 0)
)

function splitIds(value: string): string[] {
  return value.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
}

function prettySize(bytes?: number) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function acceptFile(file: File) {
  const name = file.name.toLowerCase()
  if (!ACCEPTED_EXTS.some((ext) => name.endsWith(ext))) {
    ElMessage.warning('仅支持 PDF / DOCX / Markdown / TXT 文件')
    return
  }
  selectedFile.value = file
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  if (f) acceptFile(f)
  input.value = ''
}

function onDrop(e: DragEvent) {
  dragActive.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) acceptFile(f)
}

async function startParse() {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  if (!title.value.trim()) {
    ElMessage.warning('请输入试卷标题')
    return
  }
  loading.value = true
  try {
    const upRes = await assessmentApi.uploadFile(selectedFile.value)
    const createRes = await assessmentApi.createPaper({
      file_id: upRes.data.id,
      title: title.value.trim(),
      description: description.value || undefined
    })
    paperId.value = createRes.data.id
    parseError.value = ''
    progress.value = { stage: 'pending' }
    activeStep.value = 1
    startPolling()
  } catch {
    // 拦截器已提示错误
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  stalledPolls = 0
  pollTimer = window.setInterval(async () => {
    if (!paperId.value) return
    try {
      const res = await assessmentApi.getParseStatus(paperId.value)
      const st = res.data
      progress.value = st.parse_progress || { stage: st.parse_status }
      if (st.parse_status === 'awaiting_review') {
        stopPolling()
        await loadQuestions()
        activeStep.value = 2
      } else if (st.parse_status === 'failed') {
        parseError.value = st.parse_error || '拆题失败'
        stopPolling()
      } else {
        // pending / parsing：记录连续无进展的轮询次数，超限给一条可自查的提示
        stalledPolls += 1
        if (stalledPolls === STALLED_POLL_LIMIT && !parseError.value) {
          parseError.value =
            '拆题任务长时间没有进展。常见原因：后台任务没有被消费（本地未启动 Celery worker），或所配置的拆题模型无法连通。'
        }
      }
    } catch {
      // 单次轮询失败忽略
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function retryCurrentParse() {
  if (!paperId.value) return
  retrying.value = true
  try {
    await assessmentApi.reparsePaper(paperId.value)
    parseError.value = ''
    progress.value = { stage: 'pending' }
    startPolling()
    ElMessage.success('已重新提交拆题')
  } catch {
    // 拦截器已提示错误
  } finally {
    retrying.value = false
  }
}

async function skipToManual() {
  if (!paperId.value) return
  parseError.value = ''
  activeStep.value = 2
  await loadQuestions()
  if (!questions.value.length) addQuestion()
}

async function loadQuestions() {
  if (!paperId.value) return
  const res = await assessmentApi.listQuestions(paperId.value)
  questions.value = (res.data || []).map((q: any) => ({
    ...q,
    options: q.options || [],
    stem_images: q.stem_images || [],
    tags: q.tags || [],
    // 后端返回 null 表示「未设置分值」，保留 null 让教师看到待填状态
    score: q.score ?? null,
    answer: q.answer ?? ''
  }))
}

function addQuestion() {
  questions.value.push({
    question_type: 'single',
    stem: '',
    options: [
      { key: 'A', text: '' },
      { key: 'B', text: '' },
      { key: 'C', text: '' },
      { key: 'D', text: '' }
    ],
    answer: '',
    analysis: '',
    score: null,
    difficulty: null,
    tags: [],
    stem_images: []
  })
}

function removeQuestion(index: number) {
  questions.value.splice(index, 1)
}

// 原文没标分值时拆题会留空，逐题填太慢；这里给一个整卷统一补分的入口
async function batchFillScore() {
  if (!questions.value.length) return
  try {
    const { value } = await ElMessageBox.prompt(
      '将为所有尚未设置分值的题目填入该分值（已填写的题目不受影响）',
      '批量设置分值',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /^\d+(\.\d+)?$/,
        inputErrorMessage: '请输入不小于 0 的数字',
        inputValue: '1'
      }
    )
    const score = Number(value)
    if (!Number.isFinite(score) || score < 0) {
      ElMessage.warning('请输入不小于 0 的数字')
      return
    }
    questions.value.forEach((q) => {
      if (q.score === null || q.score === undefined) q.score = score
    })
    ElMessage.success('已批量填入分值')
  } catch {
    // 用户取消，无需处理
  }
}

async function saveAndNext() {
  if (!paperId.value) return
  saving.value = true
  try {
    await assessmentApi.saveQuestions(
      paperId.value,
      questions.value.map((q) => ({
        question_type: q.question_type,
        stem: q.stem,
        stem_images: q.stem_images,
        options: q.options,
        answer: q.answer,
        analysis: q.analysis,
        // undefined 与 null 都表示「未设置分值」，统一成 null 发给后端
        score: q.score ?? null,
        difficulty: q.difficulty,
        tags: q.tags,
        source_chunk: q.source_chunk
      }))
    )
    ElMessage.success('题目已保存')
    activeStep.value = 3
  } catch {
    // 拦截器已提示错误
  } finally {
    saving.value = false
  }
}

async function loadClasses() {
  try {
    const res = await learningPathApi.listClasses()
    classList.value = res.data || []
  } catch {
    // 拦截器已提示错误
  }
}

async function onClassChange(classId: string) {
  selectedStudentIds.value = []
  if (!classId) {
    classStudents.value = []
    return
  }
  classStudentsLoading.value = true
  try {
    const res = await learningPathApi.listClassStudents(classId)
    classStudents.value = res.data || []
  } catch {
    // 拦截器已提示错误
  } finally {
    classStudentsLoading.value = false
  }
}

function studentLabel(s: any) {
  const extra = s.student_id ? `（${s.student_id}）` : ''
  return `${s.display_name}${extra}`
}

async function loadGuidedStudents() {
  guidedStudentsLoading.value = true
  try {
    const items: any[] = []
    const pageSize = 100
    let page = 1
    let total = 0
    do {
      const res = await userApi.listUsers({ role_code: 'student', page, page_size: pageSize })
      const data = res.data || {}
      const rows = data.items || []
      items.push(...rows)
      total = data.total || rows.length
      page += 1
      if (!rows.length || items.length >= total) break
    } while (true)
    guidedStudents.value = items
  } catch {
    // 拦截器已提示错误
  } finally {
    guidedStudentsLoading.value = false
  }
}

function guidedStudentLabel(s: any) {
  const name = s.display_name || s.nickname || s.username
  const sid = s.student_profile?.student_id
  return sid ? `${name}（${sid}）` : name
}

function buildPublishTarget() {
  if (publishType.value === 'class') {
    if (!selectedClassId.value) return null
    return {
      type: 'class',
      ids: [selectedClassId.value],
      student_ids: publishScope.value === 'subset' ? selectedStudentIds.value : [],
      whitelist: splitIds(whitelistIds.value),
      blacklist: splitIds(blacklistIds.value)
    }
  }
  if (publishType.value === 'mentor') {
    return {
      type: 'student',
      ids: [...selectedGuidedStudentIds.value],
      whitelist: [],
      blacklist: []
    }
  }
  return {
    type: publishType.value,
    ids: splitIds(targetIds.value),
    whitelist: splitIds(whitelistIds.value),
    blacklist: splitIds(blacklistIds.value)
  }
}

async function doPublish() {
  if (!paperId.value) return
  const target = buildPublishTarget()
  if (!target) {
    ElMessage.warning('请选择发布对象')
    return
  }
  if (publishType.value === 'class') {
    if (publishScope.value === 'subset' && !selectedStudentIds.value.length) {
      ElMessage.warning('请选择学生')
      return
    }
  } else if (publishType.value === 'mentor') {
    if (!selectedGuidedStudentIds.value.length) {
      ElMessage.warning('请选择指导学生')
      return
    }
  } else if (!target.ids.length) {
    ElMessage.warning('请填写发布对象 ID')
    return
  }
  publishing.value = true
  try {
    await assessmentApi.publishPaper(paperId.value, {
      publish_target: target,
      publish_at: publishAt.value ? publishAt.value.toISOString() : null,
      due_at: dueAt.value ? dueAt.value.toISOString() : null,
      time_limit_minutes: timeLimitMinutes.value && timeLimitMinutes.value > 0 ? timeLimitMinutes.value : null,
      grading_preference: {
        mode: gradingMode.value,
        extra: gradingExtra.value.trim()
      }
    })
    published.value = true
    ElMessage.success('发布成功')
  } catch {
    // 拦截器已提示错误
  } finally {
    publishing.value = false
  }
}

function reset() {
  stopPolling()
  activeStep.value = 0
  title.value = ''
  description.value = ''
  paperId.value = null
  selectedFile.value = null
  dragActive.value = false
  questions.value = []
  parseError.value = ''
  progress.value = {}
  published.value = false
  publishType.value = 'class'
  targetIds.value = ''
  whitelistIds.value = ''
  blacklistIds.value = ''
  selectedClassId.value = ''
  classStudents.value = []
  publishScope.value = 'all'
  selectedStudentIds.value = []
  selectedGuidedStudentIds.value = []
  publishAt.value = null
  dueAt.value = null
  timeLimitMinutes.value = null
  gradingMode.value = 'standard'
  gradingExtra.value = ''
}

function fmtTime(s?: string) {
  if (!s) return '-'
  return new Date(s).toLocaleString()
}

function statusLabel(s: string) {
  const map: Record<string, string> = {
    pending: '待拆题',
    parsing: '拆题中',
    awaiting_review: '待校对',
    published: '已发布',
    publish_failed: '发送失败',
    failed: '失败'
  }
  return map[s] || s
}

function statusTone(s: string) {
  if (s === 'published') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300'
  if (s === 'awaiting_review') return 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
  if (s === 'failed' || s === 'publish_failed') return 'bg-red-50 text-red-600 dark:bg-red-950/30 dark:text-red-300'
  if (s === 'parsing') return 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300'
  return 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'
}

function stepClass(key: number) {
  if (activeStep.value === key) {
    return 'border-blue-200 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/20'
  }
  if (activeStep.value > key) {
    return 'border-emerald-200 bg-emerald-50/50 dark:border-emerald-900/60 dark:bg-emerald-950/20'
  }
  return 'border-gray-200 bg-gray-50/60 dark:border-zinc-800 dark:bg-zinc-950/40'
}

function stepBadgeClass(key: number) {
  if (activeStep.value === key) return 'bg-blue-600 text-white'
  if (activeStep.value > key) return 'bg-emerald-500 text-white'
  return 'bg-gray-200 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'
}

async function loadPapers() {
  papersLoading.value = true
  try {
    const res = await assessmentApi.listPapers()
    papers.value = res.data || []
  } catch {
    // 拦截器已提示错误
  } finally {
    papersLoading.value = false
  }
}

function newPaper() {
  reset()
  viewMode.value = 'create'
}

function backToList() {
  viewMode.value = 'list'
  loadPapers()
}

function resumeDraft() {
  viewMode.value = 'create'
}

async function openPaper(paper: any) {
  // awaiting_review 继续校对；failed 允许手工出题——否则解析失败后这份试卷
  // 在校对页没有任何入口，只能废弃重传。
  if (paper.parse_status === 'awaiting_review' || paper.parse_status === 'failed') {
    reset()
    viewMode.value = 'create'
    activeStep.value = 2
    paperId.value = paper.id
    title.value = paper.title
    parseError.value = paper.parse_error || ''
    await loadQuestions()
    return
  }
  viewTitle.value = paper.title
  viewQuestions.value = []
  if (paper.question_count) {
    try {
      const res = await assessmentApi.listQuestions(paper.id)
      viewQuestions.value = (res.data || []).map((q: any) => ({
        ...q,
        options: q.options || [],
        answer: q.answer ?? ''
      }))
    } catch {
      // 拦截器已提示错误
    }
  }
  viewVisible.value = true
}

const reparsingId = ref<string | null>(null)

async function reparsePaper(paper: any) {
  // worker 被 OOM 杀掉时任务不会走 except，parse_status 会永久停在 parsing，
  // 这份试卷此前只能废弃重传。
  reparsingId.value = paper.id
  try {
    await assessmentApi.reparsePaper(paper.id)
    ElMessage.success('已重新提交拆题')
    await loadPapers()
  } catch {
    // 拦截器已提示错误
  } finally {
    reparsingId.value = null
  }
}

async function resendPaper(paper: any) {
  reset()
  viewMode.value = 'create'
  activeStep.value = 3
  paperId.value = paper.id
  title.value = paper.title
  parseError.value = paper.parse_error || '上次发送失败'

  const t = paper.publish_target || {}
  publishType.value = t.type || 'class'

  if (t.blacklist && t.blacklist.length) {
    blacklistIds.value = t.blacklist.join(', ')
  }
  // class 与 student 类型都可能带白名单；只回填 else 分支会让重发时静默丢弃它
  if (t.whitelist && t.whitelist.length) {
    whitelistIds.value = t.whitelist.join(', ')
  }

  if (t.type === 'class') {
    selectedClassId.value = t.ids && t.ids.length ? t.ids[0] : ''
    publishScope.value = t.student_ids && t.student_ids.length ? 'subset' : 'all'
    if (selectedClassId.value) {
      await onClassChange(selectedClassId.value)
    }
    if (t.student_ids) {
      selectedStudentIds.value = [...t.student_ids]
    }
  } else {
    if (t.ids && t.ids.length) targetIds.value = t.ids.join(', ')
  }

  if (paper.publish_at) publishAt.value = new Date(paper.publish_at)
  if (t.due_at) dueAt.value = new Date(t.due_at)
  timeLimitMinutes.value = t.time_limit_minutes || null
  if (paper.grading_preference) {
    gradingMode.value = paper.grading_preference.mode || 'standard'
    gradingExtra.value = paper.grading_preference.extra || ''
  }

  await loadQuestions()
}

onMounted(() => {
  loadPapers()
  loadClasses()
  loadGuidedStudents()
  restoreDraft()
  window.addEventListener('pagehide', onPageHide)
})
onUnmounted(() => {
  stopPolling()
  persistNow()
  window.removeEventListener('pagehide', onPageHide)
})
</script>

<template>
  <div class="-m-4 min-h-[calc(100vh-8rem)] bg-gray-50 p-4 dark:bg-zinc-950 md:-m-8 md:p-8">
    <div class="mx-auto flex max-w-[1400px] flex-col gap-6">
      <!-- 页头 -->
      <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <FileText class="h-5 w-5 text-blue-600" />
              <h1 class="text-lg font-bold text-gray-900 dark:text-zinc-50">发题工作台</h1>
            </div>
            <p class="mt-2 max-w-3xl text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
              上传试卷文档，由 AI 拆出结构化题目，人工校对分值与答案后发布给学生。
            </p>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <template v-if="viewMode === 'list'">
              <button v-if="hasDraft" class="ui-button-secondary" @click="resumeDraft">
                <Wand2 class="h-3.5 w-3.5" />
                <span>继续编辑草稿</span>
              </button>
              <button class="ui-button-primary" @click="newPaper">
                <Plus class="h-3.5 w-3.5" />
                <span>新建试卷</span>
              </button>
            </template>
            <template v-else>
              <button class="ui-button-secondary" @click="backToList">
                <span>返回历史</span>
              </button>
              <button class="ui-button-secondary" @click="reset">
                <RefreshCw class="h-3.5 w-3.5" />
                <span>清空重来</span>
              </button>
            </template>
          </div>
        </div>
      </section>

      <!-- 试卷列表 -->
      <template v-if="viewMode === 'list'">
        <div v-if="papersLoading" class="minimal-card flex min-h-[280px] items-center justify-center bg-white p-8 dark:bg-zinc-900">
          <RefreshCw class="h-6 w-6 animate-spin text-blue-600" />
        </div>

        <section
          v-else-if="!papers.length"
          class="minimal-card flex min-h-[280px] flex-col items-center justify-center bg-white p-8 text-center dark:bg-zinc-900"
        >
          <FileText class="mb-4 h-10 w-10 text-gray-300 dark:text-zinc-700" />
          <h2 class="text-base font-bold text-gray-900 dark:text-zinc-50">还没有试卷</h2>
          <p class="mt-2 max-w-md text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
            上传一份试卷文档，AI 会把它拆成可编辑的题目，校对完成后即可发布。
          </p>
          <button class="ui-button-primary mt-5" @click="newPaper">
            <Plus class="h-3.5 w-3.5" />
            <span>新建试卷</span>
          </button>
        </section>

        <section
          v-for="paper in papers"
          v-else
          :key="paper.id"
          class="minimal-card bg-white p-5 dark:bg-zinc-900"
        >
          <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div class="min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <h3 class="truncate text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ paper.title }}</h3>
                <span class="rounded px-2 py-0.5 text-[10px] font-semibold" :class="statusTone(paper.parse_status)">
                  {{ statusLabel(paper.parse_status) }}
                </span>
              </div>
              <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-gray-400 dark:text-zinc-500">
                <span class="inline-flex items-center gap-1">
                  <CircleDashed class="h-3.5 w-3.5" /> {{ paper.question_count }} 题
                </span>
                <span class="inline-flex items-center gap-1">
                  <Trophy class="h-3.5 w-3.5" />
                  <template v-if="paper.total_score === null || paper.total_score === undefined">总分未设置</template>
                  <template v-else>总分 {{ paper.total_score }}</template>
                </span>
                <span class="inline-flex items-center gap-1">
                  <Clock class="h-3.5 w-3.5" /> {{ fmtTime(paper.created_at) }}
                </span>
              </div>
              <p
                v-if="paper.parse_error && (paper.parse_status === 'failed' || paper.parse_status === 'publish_failed')"
                class="mt-2 line-clamp-2 text-[11px] text-red-500 dark:text-red-400"
              >
                {{ paper.parse_error }}
              </p>
            </div>

            <div class="flex flex-shrink-0 flex-wrap items-center gap-2">
              <button
                v-if="paper.parse_status === 'awaiting_review'"
                class="ui-button-primary"
                @click="openPaper(paper)"
              >
                <span>继续校对</span>
                <ChevronRight class="h-3.5 w-3.5" />
              </button>
              <button
                v-else-if="paper.parse_status === 'publish_failed'"
                class="ui-button-primary"
                @click="resendPaper(paper)"
              >
                <Send class="h-3.5 w-3.5" />
                <span>重新发送</span>
              </button>
              <template v-else-if="paper.parse_status === 'failed'">
                <button class="ui-button-primary" @click="openPaper(paper)">
                  <span>手工出题</span>
                </button>
                <button
                  class="ui-button-secondary"
                  :disabled="reparsingId === paper.id"
                  @click="reparsePaper(paper)"
                >
                  <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': reparsingId === paper.id }" />
                  <span>重新拆题</span>
                </button>
              </template>
              <button v-else-if="paper.question_count" class="ui-button-secondary" @click="openPaper(paper)">
                <Eye class="h-3.5 w-3.5" />
                <span>查看题目</span>
              </button>
              <button
                v-else-if="paper.parse_status === 'parsing' || paper.parse_status === 'pending'"
                class="ui-button-secondary"
                :disabled="reparsingId === paper.id"
                @click="reparsePaper(paper)"
              >
                <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': reparsingId === paper.id }" />
                <span>重新拆题</span>
              </button>
              <span v-else class="text-xs text-gray-400">无题</span>
            </div>
          </div>
        </section>
      </template>

      <!-- 新建流程 -->
      <template v-else>
        <!-- 步骤指示 -->
        <section class="minimal-card bg-white p-4 dark:bg-zinc-900">
          <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div
              v-for="s in STEPS"
              :key="s.key"
              class="flex items-center gap-3 rounded-lg border px-3 py-2.5 transition"
              :class="stepClass(s.key)"
            >
              <span
                class="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold"
                :class="stepBadgeClass(s.key)"
              >
                <Check v-if="activeStep > s.key" class="h-3.5 w-3.5" />
                <template v-else>{{ s.key + 1 }}</template>
              </span>
              <div class="min-w-0">
                <p class="truncate text-xs font-semibold text-gray-900 dark:text-zinc-50">{{ s.title }}</p>
                <p class="truncate text-[10px] text-gray-400 dark:text-zinc-500">{{ s.desc }}</p>
              </div>
            </div>
          </div>
        </section>

        <!-- 第一步：上传 -->
        <section v-if="activeStep === 0" class="minimal-card bg-white p-6 dark:bg-zinc-900">
          <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <div>
              <div
                class="flex flex-col items-center justify-center rounded-lg border border-dashed px-6 py-10 text-center transition"
                :class="dragActive
                  ? 'border-blue-400 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/20'
                  : 'border-gray-200 bg-gray-50/60 dark:border-zinc-800 dark:bg-zinc-950/40'"
                @dragover.prevent="dragActive = true"
                @dragleave.prevent="dragActive = false"
                @drop.prevent="onDrop"
              >
                <div class="flex h-12 w-12 items-center justify-center rounded-md bg-white text-blue-600 shadow-sm dark:bg-zinc-900 dark:text-blue-400">
                  <FileUp class="h-6 w-6" />
                </div>
                <p class="mt-4 text-sm font-semibold text-gray-800 dark:text-zinc-100">拖拽试卷文件到此处</p>
                <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">支持 PDF / DOCX / Markdown / TXT</p>
                <label class="ui-button-secondary mt-4 cursor-pointer">
                  <input
                    type="file"
                    class="hidden"
                    accept=".pdf,.docx,.doc,.md,.markdown,.txt"
                    @change="onPick"
                  />
                  <span>选择文件</span>
                </label>
              </div>

              <div
                v-if="selectedFile"
                class="mt-3 flex items-center justify-between rounded-lg border border-gray-200 bg-white px-3 py-2.5 dark:border-zinc-800 dark:bg-zinc-900"
              >
                <div class="flex min-w-0 items-center gap-2">
                  <FileText class="h-4 w-4 flex-shrink-0 text-blue-600" />
                  <span class="truncate text-xs font-medium text-gray-800 dark:text-zinc-100">{{ selectedFile.name }}</span>
                  <span class="flex-shrink-0 text-[10px] text-gray-400">{{ prettySize(selectedFile.size) }}</span>
                </div>
                <button class="ui-icon-button h-7 w-7" title="移除文件" @click="selectedFile = null">
                  <X class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            <div class="space-y-4">
              <div>
                <label class="ui-field-label mb-1">试卷标题</label>
                <input v-model="title" class="ui-field" placeholder="例如：2026 秋季高等数学期中卷" />
              </div>
              <div>
                <label class="ui-field-label mb-1">说明（可选）</label>
                <textarea v-model="description" class="ui-field" rows="3" placeholder="这份试卷的用途或备注" />
              </div>
              <button class="ui-button-primary w-full" :disabled="loading" @click="startParse">
                <Sparkles class="h-3.5 w-3.5" />
                <span>{{ loading ? '提交中…' : '开始拆题' }}</span>
              </button>
              <p class="ui-field-help">拆题会调用管理端「模型配置」里 question_parsing 通道所指定的模型。</p>
            </div>
          </div>
        </section>

        <!-- 第二步：拆题进度 -->
        <section v-else-if="activeStep === 1" class="minimal-card bg-white p-6 dark:bg-zinc-900">
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div class="flex items-center gap-3">
              <div
                class="flex h-10 w-10 items-center justify-center rounded-md"
                :class="parseError
                  ? 'bg-red-50 text-red-500 dark:bg-red-950/30 dark:text-red-400'
                  : 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400'"
              >
                <AlertCircle v-if="parseError" class="h-5 w-5" />
                <Loader2 v-else class="h-5 w-5 animate-spin" />
              </div>
              <div>
                <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ progressLabel }}</p>
                <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">{{ progressHint }}</p>
              </div>
            </div>
            <span
              v-if="channelLabel"
              class="flex-shrink-0 rounded bg-gray-100 px-2 py-1 text-[10px] font-semibold text-gray-500 dark:bg-zinc-800 dark:text-zinc-400"
            >
              {{ channelLabel }}
            </span>
          </div>

          <div class="mt-6 h-2 w-full overflow-hidden rounded-full bg-gray-100 dark:bg-zinc-800">
            <div
              class="h-full rounded-full transition-all duration-500"
              :class="parseError ? 'bg-red-500' : 'bg-blue-600'"
              :style="{ width: (parseError ? 100 : progressPercent) + '%' }"
            />
          </div>
          <div class="mt-2 flex items-center justify-between text-[11px] text-gray-400 dark:text-zinc-500">
            <span v-if="progress.total">{{ progress.done || 0 }} / {{ progress.total }} 个分块</span>
            <span v-else>正在准备</span>
            <span v-if="!parseError">{{ progressPercent }}%</span>
          </div>

          <div
            v-if="parseError"
            class="mt-5 rounded-lg border border-red-200 bg-red-50/70 p-4 dark:border-red-900 dark:bg-red-950/20"
          >
            <div class="flex items-start gap-2">
              <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
              <div class="min-w-0">
                <p class="text-xs font-semibold text-red-700 dark:text-red-300">拆题没有完成</p>
                <p class="mt-1 whitespace-pre-wrap text-[11px] leading-relaxed text-red-600/90 dark:text-red-300/80">{{ parseError }}</p>
              </div>
            </div>
            <div class="mt-4 flex flex-wrap gap-2">
              <button class="ui-button-primary" :disabled="retrying" @click="retryCurrentParse">
                <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': retrying }" />
                <span>{{ retrying ? '提交中…' : '重新拆题' }}</span>
              </button>
              <button class="ui-button-secondary" @click="skipToManual">
                <Plus class="h-3.5 w-3.5" />
                <span>手工出题</span>
              </button>
              <button class="ui-button-secondary" @click="reset">
                <span>返回重新上传</span>
              </button>
            </div>
          </div>
        </section>

        <!-- 第三步：人工校对 -->
        <template v-else-if="activeStep === 2">
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                  <CheckCircle2 class="h-5 w-5" />
                </div>
                <div>
                  <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">共 {{ questions.length }} 题，请逐题校对并调整</p>
                  <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">
                    已设分值合计 {{ totalScorePreview }} 分<span v-if="unsetScoreCount">，另有 {{ unsetScoreCount }} 题待填</span>
                  </p>
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <button v-if="unsetScoreCount" class="ui-button-secondary" @click="batchFillScore">
                  <Wand2 class="h-3.5 w-3.5" />
                  <span>批量设置分值</span>
                </button>
                <button class="ui-button-secondary" @click="addQuestion">
                  <Plus class="h-3.5 w-3.5" />
                  <span>新增题目</span>
                </button>
                <button class="ui-button-secondary" @click="loadQuestions">
                  <RefreshCw class="h-3.5 w-3.5" />
                  <span>重新加载</span>
                </button>
                <button class="ui-button-primary" :disabled="saving" @click="saveAndNext">
                  <Send class="h-3.5 w-3.5" />
                  <span>{{ saving ? '保存中…' : '保存并进入发布' }}</span>
                </button>
              </div>
            </div>

            <div
              v-if="unsetScoreCount"
              class="mt-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2.5 dark:border-amber-900 dark:bg-amber-950/20"
            >
              <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" />
              <p class="text-[11px] leading-relaxed text-amber-700 dark:text-amber-300">
                原文没有标注分值的题目不会自动估算，请逐题填写，或用「批量设置分值」统一填入；未设置分值的试卷无法发布。
              </p>
            </div>
          </section>

          <div class="flex flex-col gap-3">
            <QuestionEditor
              v-for="(q, i) in questions"
              :key="i"
              :item="q"
              :index="i"
              @remove="removeQuestion"
            />
          </div>

          <div v-if="!questions.length" class="minimal-card bg-white p-8 text-center dark:bg-zinc-900">
            <p class="text-sm text-gray-400">还没有题目，点击「新增题目」开始手工出题。</p>
          </div>
        </template>

        <!-- 第四步：发布 -->
        <section v-else class="minimal-card bg-white p-6 dark:bg-zinc-900">
          <div v-if="published" class="flex flex-col items-center py-12 text-center">
            <div class="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
              <CheckCircle2 class="h-6 w-6" />
            </div>
            <p class="mt-4 text-base font-semibold text-gray-900 dark:text-zinc-50">试卷已发布</p>
            <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">学生已可在「我的作业」中看到这份试卷。</p>
            <button class="ui-button-primary mt-5" @click="reset">再发一份</button>
          </div>

          <div v-else class="max-w-xl space-y-5">
            <div
              v-if="parseError"
              class="flex items-start gap-2 rounded-lg border border-red-200 bg-red-50/70 px-3 py-2.5 dark:border-red-900 dark:bg-red-950/20"
            >
              <AlertCircle class="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
              <div class="min-w-0">
                <p class="text-xs font-semibold text-red-700 dark:text-red-300">上次发送失败</p>
                <p class="mt-1 text-[11px] leading-relaxed text-red-600/90 dark:text-red-300/80">{{ parseError }}</p>
              </div>
            </div>

            <div>
              <label class="ui-field-label mb-1">发布对象类型</label>
              <el-select v-model="publishType" class="w-full">
                <el-option label="按班级" value="class" />
                <el-option label="按指导学生" value="mentor" />
                <el-option label="按学生（手填 ID）" value="student" />
              </el-select>
            </div>

            <template v-if="publishType === 'class'">
              <div>
                <label class="ui-field-label mb-1">选择班级</label>
                <el-select v-model="selectedClassId" class="w-full" placeholder="请选择班级" @change="onClassChange">
                  <el-option v-for="c in classList" :key="c.id" :label="c.name" :value="c.id" />
                </el-select>
              </div>
              <div>
                <label class="ui-field-label mb-1">学生范围</label>
                <el-radio-group v-model="publishScope">
                  <el-radio value="all">发布给全班</el-radio>
                  <el-radio value="subset">指定部分学生</el-radio>
                </el-radio-group>
              </div>
              <div v-if="publishScope === 'subset'">
                <label class="ui-field-label mb-1">选择学生</label>
                <el-select
                  v-model="selectedStudentIds"
                  multiple
                  filterable
                  class="w-full"
                  :loading="classStudentsLoading"
                  placeholder="请选择学生"
                >
                  <el-option v-for="s in classStudents" :key="s.user_id" :label="studentLabel(s)" :value="s.user_id" />
                </el-select>
                <p class="ui-field-help">当前班级 {{ classStudents.length }} 名学生</p>
              </div>
              <div>
                <label class="ui-field-label mb-1">黑名单（排除学生，可选）</label>
                <input v-model="blacklistIds" class="ui-field" placeholder="从发布范围中排除的学生 ID，逗号分隔" />
              </div>
            </template>

            <template v-else-if="publishType === 'mentor'">
              <div>
                <label class="ui-field-label mb-1">选择指导学生</label>
                <el-select
                  v-model="selectedGuidedStudentIds"
                  multiple
                  filterable
                  class="w-full"
                  :loading="guidedStudentsLoading"
                  placeholder="请选择指导学生"
                >
                  <el-option v-for="s in guidedStudents" :key="s.id" :label="guidedStudentLabel(s)" :value="s.id" />
                </el-select>
                <p class="ui-field-help">当前共 {{ guidedStudents.length }} 名指导学生</p>
              </div>
            </template>

            <template v-else>
              <div>
                <label class="ui-field-label mb-1">学生（学号 / 用户名 / UUID）</label>
                <input v-model="targetIds" class="ui-field" placeholder="学号 / 用户名 / UUID，多个用逗号分隔" />
              </div>
              <div>
                <label class="ui-field-label mb-1">白名单（追加，可选）</label>
                <input v-model="whitelistIds" class="ui-field" placeholder="追加的学号 / 用户名 / UUID，逗号分隔" />
              </div>
              <div>
                <label class="ui-field-label mb-1">黑名单（排除，可选）</label>
                <input v-model="blacklistIds" class="ui-field" placeholder="排除的学号 / 用户名 / UUID，逗号分隔" />
              </div>
            </template>

            <div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div>
                <label class="ui-field-label mb-1">预约发布时间（可选）</label>
                <el-date-picker v-model="publishAt" type="datetime" class="w-full" placeholder="留空表示立即发布" />
              </div>
              <div>
                <label class="ui-field-label mb-1">截止时间（可选）</label>
                <el-date-picker v-model="dueAt" type="datetime" class="w-full" placeholder="交卷截止时间" />
              </div>
              <div>
                <label class="ui-field-label mb-1">限时（分钟，可选）</label>
                <input
                  :value="timeLimitMinutes ?? ''"
                  type="number"
                  min="1"
                  max="1440"
                  class="ui-field"
                  placeholder="不填则不限时，从进入试卷开始计时"
                  @input="timeLimitMinutes = ($event.target as HTMLInputElement).value ? Number(($event.target as HTMLInputElement).value) : null"
                />
                <p class="mt-1 text-[11px] text-gray-400">和截止时间都填时，先到的那个收卷。</p>
              </div>
            </div>

            <div class="rounded-lg border border-gray-100 p-4 dark:border-zinc-800">
              <p class="text-xs font-semibold text-gray-900 dark:text-zinc-50">主观题批阅倾向</p>
              <p class="mt-1 text-[11px] leading-relaxed text-gray-400">
                决定 AI 预批阅与人工批改的松紧尺度，随本卷保存，批改时同样会提示阅卷老师。
              </p>
              <el-radio-group v-model="gradingMode" class="mt-3 flex flex-wrap gap-2">
                <el-radio-button value="lenient">宽松</el-radio-button>
                <el-radio-button value="standard">标准</el-radio-button>
                <el-radio-button value="strict">严格</el-radio-button>
              </el-radio-group>
              <el-input
                v-model="gradingExtra"
                type="textarea"
                :rows="2"
                maxlength="500"
                show-word-limit
                class="mt-3"
                placeholder="补充要求（可选），例如：计算题必须写出关键步骤，只给最终答案不得分"
              />
            </div>

            <div class="flex justify-end gap-2 border-t border-gray-100 pt-4 dark:border-zinc-800">
              <button class="ui-button-secondary" @click="activeStep = 2">
                <span>返回校对</span>
              </button>
              <button class="ui-button-primary" :disabled="publishing" @click="doPublish">
                <Send class="h-3.5 w-3.5" />
                <span>{{ publishing ? '发布中…' : '发布' }}</span>
              </button>
            </div>
          </div>
        </section>
      </template>

      <!-- 已发布试卷预览 -->
      <el-dialog v-model="viewVisible" :title="viewTitle" width="72%">
        <div v-if="!viewQuestions.length" class="py-8 text-center text-sm text-gray-400">暂无题目</div>
        <div class="flex flex-col gap-3">
          <div
            v-for="(q, i) in viewQuestions"
            :key="i"
            class="rounded-lg border border-gray-200 p-4 dark:border-zinc-800"
          >
            <div class="mb-2 flex items-center gap-2">
              <span class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
                第 {{ i + 1 }} 题
              </span>
              <span class="rounded bg-gray-100 px-2 py-0.5 text-[10px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
                {{ questionTypeLabels[q.question_type] || q.question_type }}
              </span>
              <span
                class="rounded px-2 py-0.5 text-[10px] font-semibold"
                :class="q.score === null || q.score === undefined
                  ? 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-300'
                  : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300'"
              >
                <template v-if="q.score === null || q.score === undefined">未设置分值</template>
                <template v-else>{{ q.score }} 分</template>
              </span>
            </div>
            <RichStem :stem="q.stem" :images="q.stem_images" class="text-sm leading-relaxed text-gray-800 dark:text-zinc-100" />
            <div v-if="q.options && q.options.length" class="mt-3 space-y-1.5">
              <div
                v-for="(o, oi) in q.options"
                :key="oi"
                class="rounded border border-gray-100 px-2.5 py-1.5 text-xs text-gray-600 dark:border-zinc-800 dark:text-zinc-300"
              >
                <span class="font-semibold">{{ o.key }}.</span> {{ o.text }}
              </div>
            </div>
            <p class="mt-3 text-xs text-emerald-600 dark:text-emerald-400">
              答案：{{ Array.isArray(q.answer) ? q.answer.join('、') : q.answer }}
            </p>
            <p v-if="q.analysis" class="mt-1 text-xs text-gray-500 dark:text-zinc-400">解析：{{ q.analysis }}</p>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>
