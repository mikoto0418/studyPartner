<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, RefreshCw, Upload } from 'lucide-vue-next'
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
const fileList = ref<any[]>([])
const paperId = ref<string | null>(null)
const parseError = ref('')
const progress = ref<{ stage?: string; total?: number; done?: number }>({})
const questions = ref<any[]>([])
const loading = ref(false)
const saving = ref(false)
const publishing = ref(false)
const published = ref(false)

const publishType = ref('class')
const targetIds = ref('')
const whitelistIds = ref('')
const blacklistIds = ref('')
const publishAt = ref<Date | null>(null)
const dueAt = ref<Date | null>(null)

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

const questionTypeLabels = {
  single: '单选题',
  multiple: '多选题',
  judge: '判断题',
  fill: '填空题',
  short: '简答题',
  essay: '论述题'
} as Record<string, string>

let pollTimer: number | null = null

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
  if (stage === 'extracting') return 'AI 拆题解析中…'
  if (stage === 'done') return '拆题完成'
  if (stage === 'failed') return '拆题失败'
  return '排队等待中…'
})

function splitIds(value: string): string[] {
  return value.split(/[,，\s]+/).map((s) => s.trim()).filter(Boolean)
}

function handleFileChange(uploadFile: any) {
  selectedFile.value = uploadFile.raw || null
}

function handleFileRemove() {
  selectedFile.value = null
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

async function loadQuestions() {
  if (!paperId.value) return
  const res = await assessmentApi.listQuestions(paperId.value)
  questions.value = (res.data || []).map((q: any) => ({
    ...q,
    options: q.options || [],
    stem_images: q.stem_images || [],
    tags: q.tags || [],
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
    score: 1,
    difficulty: null,
    tags: [],
    stem_images: []
  })
}

function removeQuestion(index: number) {
  questions.value.splice(index, 1)
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
        score: q.score,
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
      due_at: dueAt.value ? dueAt.value.toISOString() : null
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
  fileList.value = []
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

function statusType(s: string): 'success' | 'warning' | 'danger' | 'info' {
  if (s === 'published') return 'success'
  if (s === 'awaiting_review') return 'warning'
  if (s === 'failed' || s === 'publish_failed') return 'danger'
  return 'info'
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
  <div class="mx-auto max-w-5xl px-4 py-6">
    <div class="mb-6 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-xl font-semibold text-gray-900 dark:text-zinc-50">发题工作台</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-zinc-400">上传文件 → AI 拆题 → 人工校对 → 发布</p>
      </div>
      <div v-if="viewMode === 'list'" class="flex shrink-0 gap-2">
        <el-button v-if="hasDraft" @click="resumeDraft">继续编辑</el-button>
        <el-button type="primary" @click="newPaper">新建试卷</el-button>
      </div>
      <div v-else class="flex shrink-0 gap-2">
        <el-button @click="backToList">返回历史</el-button>
        <el-button @click="reset">清空重来</el-button>
      </div>
    </div>

    <div v-if="viewMode === 'list'" class="rounded-xl border border-gray-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <el-table :data="papers" v-loading="papersLoading" empty-text="还没有试卷，点击「新建试卷」开始" class="w-full">
        <el-table-column prop="title" label="标题" min-width="180" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.parse_status)" size="small">{{ statusLabel(row.parse_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="question_count" label="题目数" width="90" />
        <el-table-column prop="total_score" label="总分" width="90" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.parse_status === 'awaiting_review'" size="small" type="primary" @click="openPaper(row)">继续校对</el-button>
            <el-button v-else-if="row.parse_status === 'publish_failed'" size="small" type="primary" @click="resendPaper(row)">重新发送</el-button>
            <template v-else-if="row.parse_status === 'failed'">
              <el-button size="small" type="primary" @click="openPaper(row)">手工出题</el-button>
              <el-button size="small" :loading="reparsingId === row.id" @click="reparsePaper(row)">重新拆题</el-button>
            </template>
            <el-button v-else-if="row.question_count" size="small" @click="openPaper(row)">查看题目</el-button>
            <el-button
              v-else-if="row.parse_status === 'parsing' || row.parse_status === 'pending'"
              size="small"
              type="primary"
              :loading="reparsingId === row.id"
              @click="reparsePaper(row)"
            >重新拆题</el-button>
            <span v-else class="text-xs text-gray-400">无题</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <template v-else>
    <el-steps :active="activeStep" align-center class="mb-8">
      <el-step title="上传文件" />
      <el-step title="AI 拆题" />
      <el-step title="人工校对" />
      <el-step title="发布" />
    </el-steps>

    <!-- 第一步：上传 -->
    <div v-if="activeStep === 0" class="rounded-xl border border-gray-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".pdf,.docx,.doc,.md,.markdown,.txt"
        :file-list="fileList"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
      >
        <div class="flex flex-col items-center py-4 text-gray-500 dark:text-zinc-400">
          <Upload class="h-8 w-8 text-blue-500" />
          <p class="mt-3 text-sm">拖拽文件到此处，或<em class="text-blue-600 not-italic">点击上传</em></p>
          <p class="mt-1 text-xs">支持 PDF / DOCX / Markdown</p>
        </div>
      </el-upload>

      <div class="mt-5 grid gap-4">
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">试卷标题</label>
          <el-input v-model="title" placeholder="请输入试卷标题" />
        </div>
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">说明（可选）</label>
          <el-input v-model="description" type="textarea" :rows="2" placeholder="试卷说明" />
        </div>
        <div>
          <el-button type="primary" :loading="loading" @click="startParse">开始拆题</el-button>
        </div>
      </div>
    </div>

    <!-- 第二步：拆题进度 -->
    <div v-else-if="activeStep === 1" class="rounded-xl border border-gray-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="mb-4 text-sm font-medium text-gray-700 dark:text-zinc-200">{{ progressLabel }}</div>
      <el-progress :percentage="progressPercent" :stroke-width="12" />
      <el-alert v-if="parseError" class="mt-4" type="error" :title="parseError" :closable="false" show-icon>
        <template #default>
          <div class="mt-2">
            <el-button size="small" @click="reset">返回重新上传</el-button>
          </div>
        </template>
      </el-alert>
    </div>

    <!-- 第三步：人工校对 -->
    <div v-else-if="activeStep === 2" class="space-y-4">
      <div class="flex items-center justify-between">
        <p class="text-sm text-gray-500 dark:text-zinc-400">共 {{ questions.length }} 题，请逐题校对并调整</p>
        <el-button :icon="Plus" @click="addQuestion">新增题目</el-button>
      </div>

      <QuestionEditor
        v-for="(q, i) in questions"
        :key="i"
        :item="q"
        :index="i"
        @remove="removeQuestion"
      />

      <div class="flex justify-end gap-2">
        <el-button :icon="RefreshCw" @click="loadQuestions">重新加载</el-button>
        <el-button type="primary" :loading="saving" @click="saveAndNext">保存并进入发布</el-button>
      </div>
    </div>

    <!-- 第四步：发布 -->
    <div v-else class="rounded-xl border border-gray-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <div v-if="published" class="py-10 text-center">
        <p class="text-lg font-semibold text-gray-900 dark:text-zinc-50">试卷已发布</p>
        <el-button class="mt-4" type="primary" @click="reset">再发一份</el-button>
      </div>

      <div v-else class="max-w-xl space-y-4">
        <el-alert v-if="parseError" type="error" title="上次发送失败" :description="parseError" :closable="false" show-icon />
        <div>
          <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">发布对象类型</label>
          <el-select v-model="publishType" class="w-full">
            <el-option label="按班级" value="class" />
            <el-option label="按指导学生" value="mentor" />
            <el-option label="按学生（手填 ID）" value="student" />
          </el-select>
        </div>

        <template v-if="publishType === 'class'">
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">选择班级</label>
            <el-select v-model="selectedClassId" class="w-full" placeholder="请选择班级" @change="onClassChange">
              <el-option v-for="c in classList" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">学生范围</label>
            <el-radio-group v-model="publishScope">
              <el-radio value="all">发布给全班</el-radio>
              <el-radio value="subset">指定部分学生</el-radio>
            </el-radio-group>
          </div>
          <div v-if="publishScope === 'subset'">
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">选择学生</label>
            <el-select v-model="selectedStudentIds" multiple filterable class="w-full" :loading="classStudentsLoading" placeholder="请选择学生">
              <el-option v-for="s in classStudents" :key="s.user_id" :label="studentLabel(s)" :value="s.user_id" />
            </el-select>
            <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">当前班级 {{ classStudents.length }} 名学生</p>
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">黑名单（排除学生，可选）</label>
            <el-input v-model="blacklistIds" placeholder="从发布范围中排除的学生 ID，逗号分隔" />
          </div>
        </template>

        <template v-else-if="publishType === 'mentor'">
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">选择指导学生</label>
            <el-select v-model="selectedGuidedStudentIds" multiple filterable class="w-full" :loading="guidedStudentsLoading" placeholder="请选择指导学生">
              <el-option v-for="s in guidedStudents" :key="s.id" :label="guidedStudentLabel(s)" :value="s.id" />
            </el-select>
            <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">当前共 {{ guidedStudents.length }} 名指导学生</p>
          </div>
        </template>

        <template v-else>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">学生（学号 / 用户名 / UUID）</label>
            <el-input v-model="targetIds" placeholder="学号 / 用户名 / UUID，多个用逗号分隔" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">白名单（追加，可选）</label>
            <el-input v-model="whitelistIds" placeholder="追加的学号 / 用户名 / UUID，逗号分隔" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">黑名单（排除，可选）</label>
            <el-input v-model="blacklistIds" placeholder="排除的学号 / 用户名 / UUID，逗号分隔" />
          </div>
        </template>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">预约发布时间（可选）</label>
            <el-date-picker v-model="publishAt" type="datetime" class="w-full" placeholder="留空表示立即发布" />
          </div>
          <div>
            <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">截止时间（可选）</label>
            <el-date-picker v-model="dueAt" type="datetime" class="w-full" placeholder="交卷截止时间" />
          </div>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <el-button @click="activeStep = 2">返回校对</el-button>
          <el-button type="primary" :loading="publishing" @click="doPublish">发布</el-button>
        </div>
      </div>
    </div>
    </template>

    <el-dialog v-model="viewVisible" :title="viewTitle" width="72%">
      <div v-if="!viewQuestions.length" class="py-8 text-center text-sm text-gray-400">暂无题目</div>
      <div v-for="(q, i) in viewQuestions" :key="i" class="mb-3 rounded-lg border border-gray-200 p-3 dark:border-zinc-700">
        <div class="mb-1 text-sm font-medium">{{ i + 1 }}. {{ questionTypeLabels[q.question_type] || q.question_type }}（{{ q.score }} 分）</div>
        <div class="text-sm text-gray-700 dark:text-zinc-200"><RichStem :stem="q.stem" :images="q.stem_images" /></div>
        <div v-if="q.options && q.options.length" class="mt-2 space-y-1 pl-4 text-sm text-gray-600 dark:text-zinc-400">
          <div v-for="(o, oi) in q.options" :key="oi">{{ o.key }}. {{ o.text }}</div>
        </div>
        <div class="mt-2 text-xs text-green-600 dark:text-green-400">答案：{{ Array.isArray(q.answer) ? q.answer.join('、') : q.answer }}</div>
        <div v-if="q.analysis" class="mt-1 text-xs text-gray-500 dark:text-zinc-400">解析：{{ q.analysis }}</div>
      </div>
    </el-dialog>
  </div>
</template>