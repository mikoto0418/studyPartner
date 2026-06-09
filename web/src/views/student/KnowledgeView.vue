<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  FileText,
  FolderPlus,
  Layers,
  MessageSquare,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  Upload,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeApi } from '../../api/modules/knowledge'
import type { KnowledgeDocumentOut, RAGAnswerOut, TeacherAssignedFileOut } from '../../api/modules/knowledge'

const documents = ref<KnowledgeDocumentOut[]>([])
const teacherFiles = ref<TeacherAssignedFileOut[]>([])
const loadingDocs = ref(false)
const uploadingFile = ref(false)
const importingTeacherFileId = ref('')
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

const selectedFolder = ref('all')
const selectedTag = ref('all')
const customFolders = ref<string[]>([])
const newFolderName = ref('')

const uploadDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingDoc = ref<KnowledgeDocumentOut | null>(null)
const selectedFile = ref<File | null>(null)

const uploadForm = ref({
  title: '',
  description: '',
  category: '课程资料',
  tagsText: '',
  visibility: 'private',
})

const editForm = ref({
  title: '',
  description: '',
  category: '',
  tagsText: '',
  visibility: 'private',
})

const assistantQuery = ref('')
const assistantAnswer = ref<RAGAnswerOut | null>(null)
const askingAssistant = ref(false)

const folderStorageKey = 'study_partner:knowledge_folders'

const folderOptions = computed(() => {
  const names = new Set<string>()
  documents.value.forEach((doc) => {
    if (doc.category) names.add(doc.category)
  })
  customFolders.value.forEach((folder) => names.add(folder))
  return ['all', ...Array.from(names).sort()]
})

const allTags = computed(() => {
  const names = new Set<string>()
  documents.value.forEach((doc) => {
    ;(doc.tags || []).forEach((tag) => {
      if (tag) names.add(tag)
    })
  })
  return ['all', ...Array.from(names).sort()]
})

const visibleDocuments = computed(() => {
  return documents.value.filter((doc) => {
    const folderMatched = selectedFolder.value === 'all' || doc.category === selectedFolder.value
    const tagMatched = selectedTag.value === 'all' || (doc.tags || []).includes(selectedTag.value)
    return folderMatched && tagMatched
  })
})

const unimportedTeacherFiles = computed(() => {
  const usedFileIds = new Set(documents.value.map((doc) => doc.file_id))
  return teacherFiles.value.filter((item) => !usedFileIds.has(item.file.id))
})

function parseTags(text: string) {
  return text
    .split(/[,，\n]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function tagsToText(tags?: string[]) {
  return (tags || []).join('，')
}

function saveCustomFolders() {
  localStorage.setItem(folderStorageKey, JSON.stringify(customFolders.value))
}

function loadCustomFolders() {
  try {
    const raw = localStorage.getItem(folderStorageKey)
    customFolders.value = raw ? JSON.parse(raw) : []
  } catch (error) {
    customFolders.value = []
  }
}

function createFolder() {
  const folder = newFolderName.value.trim()
  if (!folder) return
  if (!customFolders.value.includes(folder)) {
    customFolders.value.push(folder)
    saveCustomFolders()
  }
  selectedFolder.value = folder
  uploadForm.value.category = folder
  newFolderName.value = ''
  ElMessage.success('文件夹已创建')
}

function normalizeDocumentResponse(data: any): KnowledgeDocumentOut[] {
  if (Array.isArray(data)) return data
  return data?.items || []
}

async function loadDocuments(silent = false) {
  if (!silent) loadingDocs.value = true
  try {
    const res = await knowledgeApi.listDocuments({ page_size: 100 })
    documents.value = normalizeDocumentResponse(res.data)

    const hasUnfinished = documents.value.some((doc) =>
      ['pending', 'parsing', 'chunking', 'embedding'].includes(doc.process_status),
    )
    if (hasUnfinished && !pollTimer.value) {
      startPolling()
    } else if (!hasUnfinished) {
      stopPolling()
    }
  } catch (error) {
    documents.value = []
  } finally {
    if (!silent) loadingDocs.value = false
  }
}

async function loadTeacherFiles() {
  try {
    const res = await knowledgeApi.listTeacherFiles()
    teacherFiles.value = res.data || []
  } catch (error) {
    teacherFiles.value = []
  }
}

function startPolling() {
  pollTimer.value = setInterval(() => {
    loadDocuments(true)
  }, 5000)
}

function stopPolling() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['pdf', 'docx', 'txt', 'md', 'markdown'].includes(ext || '')) {
    ElMessage.warning('仅支持 PDF、DOCX、TXT、MD 文件')
    return
  }

  selectedFile.value = file
  if (!uploadForm.value.title) {
    uploadForm.value.title = file.name.replace(/\.[^.]+$/, '')
  }
}

function openUploadDialog() {
  uploadForm.value.category = selectedFolder.value === 'all' ? '课程资料' : selectedFolder.value
  uploadDialogVisible.value = true
}

async function handleUploadSubmit() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.value.title.trim()) {
    ElMessage.warning('请填写资料标题')
    return
  }

  uploadingFile.value = true
  try {
    const uploadRes = await knowledgeApi.uploadFile(selectedFile.value)
    await knowledgeApi.createDocument({
      file_id: uploadRes.data.id,
      title: uploadForm.value.title.trim(),
      description: uploadForm.value.description.trim() || undefined,
      category: uploadForm.value.category.trim() || '课程资料',
      tags: parseTags(uploadForm.value.tagsText),
      visibility: uploadForm.value.visibility,
    })
    ElMessage.success('文件已提交解析')
    uploadDialogVisible.value = false
    selectedFile.value = null
    uploadForm.value = {
      title: '',
      description: '',
      category: selectedFolder.value === 'all' ? '课程资料' : selectedFolder.value,
      tagsText: '',
      visibility: 'private',
    }
    loadDocuments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '上传失败')
  } finally {
    uploadingFile.value = false
  }
}

async function importTeacherFile(item: TeacherAssignedFileOut) {
  importingTeacherFileId.value = item.file.id
  try {
    await knowledgeApi.createDocument({
      file_id: item.file.id,
      title: item.file.original_name.replace(/\.[^.]+$/, ''),
      description: item.task_description || `来自导师任务：${item.task_title}`,
      category: selectedFolder.value === 'all' ? '导师下发' : selectedFolder.value,
      tags: ['导师下发', item.task_title].filter(Boolean),
      visibility: 'private',
    })
    ElMessage.success('老师下发文件已加入知识库')
    await Promise.all([loadDocuments(), loadTeacherFiles()])
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '导入老师文件失败')
  } finally {
    importingTeacherFileId.value = ''
  }
}

function openEditDialog(doc: KnowledgeDocumentOut) {
  editingDoc.value = doc
  editForm.value = {
    title: doc.title,
    description: doc.description || '',
    category: doc.category || '课程资料',
    tagsText: tagsToText(doc.tags),
    visibility: doc.visibility || 'private',
  }
  editDialogVisible.value = true
}

async function handleEditSubmit() {
  if (!editingDoc.value) return
  if (!editForm.value.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }

  try {
    const res = await knowledgeApi.updateDocument(editingDoc.value.id, {
      title: editForm.value.title.trim(),
      description: editForm.value.description.trim() || undefined,
      category: editForm.value.category.trim() || '课程资料',
      tags: parseTags(editForm.value.tagsText),
      visibility: editForm.value.visibility,
    })
    const updated = res.data as KnowledgeDocumentOut
    documents.value = documents.value.map((doc) => (doc.id === updated.id ? updated : doc))
    editDialogVisible.value = false
    editingDoc.value = null
    ElMessage.success('资料信息已更新')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '更新失败')
  }
}

async function handleDeleteDocument(doc: KnowledgeDocumentOut) {
  try {
    await ElMessageBox.confirm(`确定删除「${doc.title}」吗？`, '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await knowledgeApi.deleteDocument(doc.id)
    ElMessage.success('文档已删除')
    loadDocuments()
  } catch (error) {
    // cancelled
  }
}

async function handleAssistantAsk() {
  if (!assistantQuery.value.trim()) {
    ElMessage.warning('请输入要搜索或提问的内容')
    return
  }

  askingAssistant.value = true
  assistantAnswer.value = null
  try {
    const res = await knowledgeApi.knowledgeQA(assistantQuery.value.trim())
    assistantAnswer.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '知识库助手检索失败')
  } finally {
    askingAssistant.value = false
  }
}

function statusText(status: string) {
  const labels: Record<string, string> = {
    pending: '排队中',
    parsing: '解析中',
    chunking: '切片中',
    embedding: '索引中',
    completed: '可检索',
    failed: '失败',
  }
  return labels[status] || status
}

function statusClass(status: string) {
  if (status === 'completed') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300'
  if (['pending', 'parsing', 'chunking', 'embedding'].includes(status)) {
    return 'bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300'
  }
  return 'bg-red-50 text-red-700 dark:bg-red-950/20 dark:text-red-300'
}

onMounted(() => {
  loadCustomFolders()
  Promise.all([loadDocuments(), loadTeacherFiles()])
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="grid grid-cols-1 gap-6 xl:grid-cols-12">
    <aside class="xl:col-span-3 space-y-5">
      <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">文件夹</h3>
          <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
            {{ folderOptions.length - 1 }}
          </span>
        </div>

        <div class="space-y-2">
          <button
            v-for="folder in folderOptions"
            :key="folder"
            @click="selectedFolder = folder"
            class="flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition"
            :class="selectedFolder === folder ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300' : 'text-gray-500 hover:bg-gray-50 dark:text-zinc-400 dark:hover:bg-zinc-800'"
          >
            <span>{{ folder === 'all' ? '全部资料' : folder }}</span>
            <span class="text-[10px] opacity-70">
              {{ folder === 'all' ? documents.length : documents.filter((doc) => doc.category === folder).length }}
            </span>
          </button>
        </div>

        <div class="mt-4 flex gap-2">
          <input
            v-model="newFolderName"
            @keyup.enter="createFolder"
            type="text"
            placeholder="新文件夹"
            class="min-w-0 flex-1 rounded border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"
          />
          <button
            @click="createFolder"
            class="rounded border border-gray-200 px-2 text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800"
            title="创建文件夹"
          >
            <FolderPlus class="h-3.5 w-3.5" />
          </button>
        </div>
      </section>

      <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h3 class="mb-4 text-xs font-semibold text-gray-900 dark:text-zinc-50">标签</h3>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="tagName in allTags"
            :key="tagName"
            @click="selectedTag = tagName"
            class="inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] transition"
            :class="selectedTag === tagName ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300' : 'border-gray-200 text-gray-500 hover:bg-gray-50 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800'"
          >
            <Tag class="h-3 w-3" />
            <span>{{ tagName === 'all' ? '全部标签' : tagName }}</span>
          </button>
        </div>
      </section>
    </aside>

    <main class="xl:col-span-5 flex flex-col gap-5">
      <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div class="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">知识库资料</h2>
            <p class="mt-1 text-[11px] text-gray-400 dark:text-zinc-500">支持 PDF、DOCX、TXT、Markdown，按文件夹和标签管理。</p>
          </div>
          <button
            @click="openUploadDialog"
            class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-500"
          >
            <Upload class="h-3.5 w-3.5" />
            <span>上传资料</span>
          </button>
        </div>

        <div class="max-h-[46vh] space-y-3 overflow-y-auto pr-1" v-loading="loadingDocs">
          <article
            v-for="doc in visibleDocuments"
            :key="doc.id"
            class="group rounded-lg border border-gray-100 bg-gray-50/50 p-4 transition hover:border-blue-200 hover:bg-white dark:border-zinc-800 dark:bg-zinc-950/20 dark:hover:bg-zinc-900"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1 space-y-2">
                <div class="flex items-center gap-2">
                  <FileText class="h-4 w-4 shrink-0 text-blue-500" />
                  <button @click="openEditDialog(doc)" class="truncate text-left text-xs font-semibold text-gray-900 hover:text-blue-600 dark:text-zinc-100">
                    {{ doc.title }}
                  </button>
                </div>
                <p v-if="doc.description" class="line-clamp-2 text-[11px] leading-relaxed text-gray-400 dark:text-zinc-500">{{ doc.description }}</p>
                <div class="flex flex-wrap items-center gap-2 text-[10px]">
                  <span class="rounded bg-gray-100 px-1.5 py-0.5 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">{{ doc.category || '未分类' }}</span>
                  <span v-for="tagName in doc.tags || []" :key="tagName" class="rounded bg-blue-50 px-1.5 py-0.5 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                    #{{ tagName }}
                  </span>
                </div>
              </div>

              <div class="flex shrink-0 items-center gap-2">
                <span class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold" :class="statusClass(doc.process_status)">
                  <RefreshCw v-if="['pending', 'parsing', 'chunking', 'embedding'].includes(doc.process_status)" class="h-3 w-3 animate-spin" />
                  <CheckCircle2 v-else-if="doc.process_status === 'completed'" class="h-3 w-3" />
                  <AlertCircle v-else class="h-3 w-3" />
                  <span>{{ statusText(doc.process_status) }}</span>
                </span>
                <button
                  @click="handleDeleteDocument(doc)"
                  class="rounded p-1 text-gray-300 opacity-0 transition hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:hover:bg-red-950/20"
                  title="删除"
                >
                  <Trash2 class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </article>

          <div v-if="visibleDocuments.length === 0" class="flex h-48 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 text-center text-gray-400 dark:border-zinc-800">
            <BookOpen class="mb-3 h-9 w-9 text-gray-200 dark:text-zinc-800" />
            <p class="text-xs">当前筛选下暂无资料</p>
          </div>
        </div>
      </section>

      <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">老师下发文件</h3>
          <span class="rounded bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">
            {{ unimportedTeacherFiles.length }}
          </span>
        </div>

        <div class="space-y-2">
          <div
            v-for="item in unimportedTeacherFiles"
            :key="`${item.task_id}-${item.file.id}`"
            class="flex items-center justify-between gap-3 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3 dark:border-indigo-900/40 dark:bg-indigo-950/20"
          >
            <div class="min-w-0">
              <p class="truncate text-xs font-semibold text-gray-900 dark:text-zinc-50">{{ item.file.original_name }}</p>
              <p class="mt-1 truncate text-[10px] text-indigo-700 dark:text-indigo-300">来自任务：{{ item.task_title }}</p>
            </div>
            <button
              @click="importTeacherFile(item)"
              :disabled="importingTeacherFileId === item.file.id"
              class="shrink-0 rounded border border-indigo-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-indigo-700 transition hover:bg-indigo-50 disabled:opacity-60 dark:border-indigo-900/50 dark:bg-zinc-900 dark:text-indigo-300"
            >
              {{ importingTeacherFileId === item.file.id ? '导入中' : '加入知识库' }}
            </button>
          </div>

          <div v-if="unimportedTeacherFiles.length === 0" class="rounded-lg border border-dashed border-gray-200 py-8 text-center text-[11px] text-gray-400 dark:border-zinc-800">
            暂无未导入的老师下发文件
          </div>
        </div>
      </section>
    </main>

    <aside class="xl:col-span-4">
      <section class="sticky top-6 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div class="mb-4 flex items-center gap-2">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-300">
            <MessageSquare class="h-4 w-4" />
          </div>
          <div>
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">知识库搜索助手</h3>
            <p class="text-[10px] text-gray-400">统一检索和问答入口</p>
          </div>
        </div>

        <div class="flex gap-2">
          <input
            v-model="assistantQuery"
            @keyup.enter="handleAssistantAsk"
            type="text"
            placeholder="输入问题或关键词"
            class="min-w-0 flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"
          />
          <button
            @click="handleAssistantAsk"
            :disabled="askingAssistant"
            class="rounded-lg bg-blue-600 p-2.5 text-white transition hover:bg-blue-500 disabled:opacity-60"
          >
            <RefreshCw v-if="askingAssistant" class="h-4 w-4 animate-spin" />
            <Search v-else class="h-4 w-4" />
          </button>
        </div>

        <div class="mt-4 max-h-[58vh] overflow-y-auto pr-1">
          <div v-if="assistantAnswer" class="space-y-4 text-xs">
            <div class="whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50 p-4 leading-relaxed text-gray-700 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-300">
              {{ assistantAnswer.answer }}
            </div>

            <div v-if="assistantAnswer.citations?.length" class="rounded-lg border border-blue-100 bg-blue-50/40 p-3 dark:border-blue-900/40 dark:bg-blue-950/20">
              <div class="mb-2 flex items-center gap-1 text-[11px] font-semibold text-blue-700 dark:text-blue-300">
                <Layers class="h-3.5 w-3.5" />
                <span>参考来源</span>
              </div>
              <div class="space-y-2">
                <div v-for="(citation, idx) in assistantAnswer.citations" :key="idx" class="text-[10px] leading-relaxed text-gray-500 dark:text-zinc-400">
                  [{{ citation.source_index }}] {{ citation.document_title }} · {{ citation.score.toFixed(3) }}
                </div>
              </div>
            </div>
          </div>

          <div v-else class="flex h-56 flex-col items-center justify-center text-center text-gray-400 dark:text-zinc-500">
            <MessageSquare class="mb-3 h-9 w-9 text-gray-200 dark:text-zinc-800" />
            <p class="text-xs">上传或导入资料后，可在这里直接提问。</p>
          </div>
        </div>
      </section>
    </aside>

    <el-dialog v-model="uploadDialogVisible" title="上传资料" width="460px" class="minimalist-dialog">
      <div class="space-y-4 text-xs" v-loading="uploadingFile">
        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">文件 <span class="text-red-500">*</span></label>
          <label class="flex h-32 cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-gray-200 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-950/30">
            <Upload class="mb-2 h-6 w-6 text-gray-400" />
            <span class="text-[11px] text-gray-500">点击选择 PDF、DOCX、TXT、MD</span>
            <input type="file" class="hidden" accept=".pdf,.docx,.txt,.md,.markdown" @change="handleFileChange" />
          </label>
          <p v-if="selectedFile" class="truncate rounded bg-blue-50 px-2 py-1.5 text-[10px] text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">{{ selectedFile.name }}</p>
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">标题 <span class="text-red-500">*</span></label>
          <input v-model="uploadForm.title" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">文件夹</label>
            <input v-model="uploadForm.category" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
          </div>
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">可见性</label>
            <select v-model="uploadForm.visibility" class="w-full rounded border border-gray-200 bg-white px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950">
              <option value="private">仅自己可见</option>
              <option value="public">公共可见</option>
              <option value="teachers_only">仅导师可见</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">标签</label>
          <input v-model="uploadForm.tagsText" placeholder="用逗号分隔，例如：论文，算法，复习" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">说明</label>
          <textarea v-model="uploadForm.description" rows="3" class="w-full resize-none rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <button @click="uploadDialogVisible = false" class="rounded border border-gray-200 px-3 py-1.5 text-xs text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800">取消</button>
          <button @click="handleUploadSubmit" class="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-500">上传解析</button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="管理资料" width="460px" class="minimalist-dialog">
      <div class="space-y-4 text-xs">
        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">标题</label>
          <input v-model="editForm.title" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">文件夹</label>
            <input v-model="editForm.category" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
          </div>
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">可见性</label>
            <select v-model="editForm.visibility" class="w-full rounded border border-gray-200 bg-white px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950">
              <option value="private">仅自己可见</option>
              <option value="public">公共可见</option>
              <option value="teachers_only">仅导师可见</option>
            </select>
          </div>
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">标签</label>
          <input v-model="editForm.tagsText" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">说明</label>
          <textarea v-model="editForm.description" rows="3" class="w-full resize-none rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <button @click="editDialogVisible = false" class="rounded border border-gray-200 px-3 py-1.5 text-xs text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800">取消</button>
          <button @click="handleEditSubmit" class="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-500">保存</button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 999px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
