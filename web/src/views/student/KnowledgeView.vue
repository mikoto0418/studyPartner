<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { BookOpen, Upload, Search, MessageSquare, Trash2, HelpCircle, FileText, CheckCircle2, AlertCircle, RefreshCw, Layers } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { knowledgeApi } from '../../api/modules/knowledge'
import type { KnowledgeDocumentOut, RAGAnswerOut } from '../../api/modules/knowledge'

// States
const documents = ref<KnowledgeDocumentOut[]>([])
const loadingDocs = ref(false)
const uploadingFile = ref(false)
const pollTimer = ref<any>(null)

// Search & QA States
const activeTab = ref('search')
const searchQuery = ref('')
const searchResults = ref<any[]>([])
const searching = ref(false)

const qaQuery = ref('')
const qaAnswer = ref<RAGAnswerOut | null>(null)
const askingQA = ref(false)

// Form configuration for Upload Dialog
const uploadDialogVisible = ref(false)
const uploadForm = ref({
  title: '',
  description: '',
  category: '学术论文',
  visibility: 'public'
})
const selectedFile = ref<File | null>(null)

// Load documents list
const loadDocuments = async (silent = false) => {
  if (!silent) loadingDocs.value = true
  try {
    const res = await knowledgeApi.listDocuments()
    documents.value = res.data || []
    
    // Auto start polling if any document is not processed yet
    const hasUnfinished = documents.value.some(d => 
      ['pending', 'parsing', 'chunking', 'embedding'].includes(d.process_status)
    )
    
    if (hasUnfinished && !pollTimer.value) {
      startPolling()
    } else if (!hasUnfinished && pollTimer.value) {
      stopPolling()
    }
  } catch (err) {
    console.error("Failed to load documents", err)
  } finally {
    if (!silent) loadingDocs.value = false
  }
}

// Polling parser helper
const startPolling = () => {
  pollTimer.value = setInterval(() => {
    loadDocuments(true)
  }, 5000)
}
const stopPolling = () => {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

// File Select trigger
const handleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files.length > 0) {
    const file = target.files[0]
    // Check type
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (!['pdf', 'docx', 'txt', 'md', 'markdown'].includes(ext || '')) {
      ElMessage.warning('仅支持 PDF, DOCX, TXT, MD 格式的学术文档')
      return
    }
    selectedFile.value = file
    // Pre-populate title
    if (!uploadForm.value.title) {
      uploadForm.value.title = file.name.substring(0, file.name.lastIndexOf('.')) || file.name
    }
  }
}

// Submit Upload Flow
const handleUploadSubmit = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择需要上传的文件')
    return
  }
  if (!uploadForm.value.title.trim()) {
    ElMessage.warning('请填写文档标题')
    return
  }

  uploadingFile.value = true
  try {
    // 1. Upload to MinIO physical server
    const uploadRes = await knowledgeApi.uploadFile(selectedFile.value)
    const fileId = uploadRes.data.id

    // 2. Create Knowledge Document DB record & trigger background parser
    await knowledgeApi.createDocument({
      file_id: fileId,
      title: uploadForm.value.title.trim(),
      description: uploadForm.value.description.trim() || undefined,
      category: uploadForm.value.category,
      visibility: uploadForm.value.visibility
    })

    ElMessage.success('文档上传并提交解析成功，请耐心等待切片索引')
    uploadDialogVisible.value = false
    selectedFile.value = null
    uploadForm.value = { title: '', description: '', category: '学术论文', visibility: 'public' }
    
    // Reload lists
    loadDocuments()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '物理文件上传或记录提交失败')
  } finally {
    uploadingFile.value = false
  }
}

// Delete document
const handleDeleteDocument = (doc: KnowledgeDocumentOut) => {
  ElMessageBox.confirm(
    `确定删除知识库文档「${doc.title}」吗？此操作会同步清理物理存储与向量数据库中的切片。`,
    '提示',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await knowledgeApi.deleteDocument(doc.id)
      ElMessage.success('删除成功')
      loadDocuments()
    } catch (e) {
      ElMessage.error('删除文档失败')
    }
  }).catch(() => {})
}

// Semantic Search action
const handleSearch = async () => {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请先输入要检索的学术课题')
    return
  }

  searching.value = true
  try {
    const res = await knowledgeApi.searchKnowledge(searchQuery.value.trim(), 4)
    searchResults.value = res.data || []
  } catch (err) {
    ElMessage.error('语义检索失败')
  } finally {
    searching.value = false
  }
}

// RAG QA Sandbox action
const handleQA = async () => {
  if (!qaQuery.value.trim()) {
    ElMessage.warning('请先提出你的科研疑问')
    return
  }

  askingQA.value = true
  qaAnswer.value = null
  try {
    const res = await knowledgeApi.knowledgeQA(qaQuery.value.trim())
    qaAnswer.value = res.data
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '知识库QA大模型检索失败')
  } finally {
    askingQA.value = false
  }
}

onMounted(() => {
  loadDocuments()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
    <!-- Left: Files Management (7 cols) -->
    <div class="lg:col-span-7 flex flex-col h-[calc(100vh-10rem)]">
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col min-h-0">
        <!-- Roster header -->
        <div class="pb-4 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between flex-shrink-0">
          <div>
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
              <BookOpen class="w-4 h-4 text-blue-600" />
              <span>共享学术文献库</span>
            </h3>
            <p class="text-[10px] text-gray-400 mt-0.5">沉淀实验室学术论文、技术笔记，后台支持滑动切片与向量索引。</p>
          </div>

          <button
            @click="uploadDialogVisible = true"
            class="flex items-center space-x-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-sm focus:outline-none"
          >
            <Upload class="w-3.5 h-3.5" />
            <span>上传文献</span>
          </button>
        </div>

        <!-- Files list -->
        <div class="flex-1 overflow-y-auto mt-4 space-y-3 pr-1" v-loading="loadingDocs">
          <div
            v-for="doc in documents"
            :key="doc.id"
            class="p-4 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/20 dark:bg-zinc-950/10 flex items-center justify-between text-xs hover:border-blue-500/50 transition-all select-none group"
          >
            <!-- Left Info -->
            <div class="space-y-1.5 flex-1 min-w-0 pr-4">
              <div class="flex items-center space-x-2">
                <FileText class="w-4 h-4 text-blue-500 flex-shrink-0" />
                <span class="font-bold text-gray-800 dark:text-zinc-200 truncate block">{{ doc.title }}</span>
              </div>
              <div class="flex items-center space-x-2 text-[10px] text-gray-400">
                <span class="bg-gray-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded text-[9px]">{{ doc.category }}</span>
                <span>&bull;</span>
                <span>切片数: {{ doc.chunk_count }}</span>
              </div>
            </div>

            <!-- Right Status and Action -->
            <div class="flex items-center space-x-3 flex-shrink-0">
              <!-- Processing status tags -->
              <span
                v-if="doc.process_status === 'completed'"
                class="inline-flex items-center space-x-0.5 px-2 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400"
              >
                <CheckCircle2 class="w-3 h-3" />
                <span>已就绪</span>
              </span>

              <span
                v-else-if="['pending', 'parsing', 'chunking', 'embedding'].includes(doc.process_status)"
                class="inline-flex items-center space-x-0.5 px-2 py-0.5 rounded text-[9px] font-bold bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-400"
              >
                <RefreshCw class="w-3 h-3 animate-spin" />
                <span>解析中</span>
              </span>

              <el-tooltip
                v-else
                :content="doc.process_error || '文档解析或向量化失败'"
                placement="top"
              >
                <span class="inline-flex items-center space-x-0.5 px-2 py-0.5 rounded text-[9px] font-bold bg-red-50 text-red-700 dark:bg-red-950/20 dark:text-red-400 cursor-help">
                  <AlertCircle class="w-3 h-3" />
                  <span>失败</span>
                </span>
              </el-tooltip>

              <!-- Delete Action -->
              <button
                @click="handleDeleteDocument(doc)"
                class="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity p-0.5"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div v-if="documents.length === 0" class="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-3 py-16">
            <BookOpen class="w-10 h-10 text-gray-200 dark:text-zinc-800" />
            <h4 class="text-xs font-semibold">库内文献为空</h4>
            <p class="text-[10px] text-gray-400 max-w-xs">点击右上角“上传文献”导入实验室 PDF 论文或 Markdown 文档。</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: QA Sandbox and Semantic Search (5 cols) -->
    <div class="lg:col-span-5 flex flex-col h-[calc(100vh-10rem)]">
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col min-h-0">
        <!-- Tabs -->
        <div class="flex border-b border-gray-100 dark:border-zinc-800 text-xs font-semibold flex-shrink-0 mb-4">
          <button
            @click="activeTab = 'search'"
            class="pb-2.5 px-4 border-b-2 transition-all focus:outline-none"
            :class="activeTab === 'search' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-400'"
          >
            多源语义检索
          </button>
          <button
            @click="activeTab = 'qa'"
            class="pb-2.5 px-4 border-b-2 transition-all focus:outline-none"
            :class="activeTab === 'qa' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-400'"
          >
            知识库 RAG 问答
          </button>
        </div>

        <!-- 1. Semantic Search Tab -->
        <div v-if="activeTab === 'search'" class="flex-1 flex flex-col min-h-0">
          <div class="flex items-center space-x-2 flex-shrink-0 mb-4">
            <input
              v-model="searchQuery"
              @keyup.enter="handleSearch"
              type="text"
              placeholder="输入关键词或自然语言，如: Transformer 自注意力"
              class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded-lg text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
            />
            <button
              @click="handleSearch"
              :disabled="searching"
              class="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg focus:outline-none disabled:opacity-50"
            >
              <Search class="w-4 h-4" />
            </button>
          </div>

          <!-- Search results -->
          <div class="flex-1 overflow-y-auto space-y-3 pr-1">
            <div
              v-for="(chunk, idx) in searchResults"
              :key="idx"
              class="p-3.5 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/20 dark:bg-zinc-950/10 text-xs space-y-2 leading-relaxed"
            >
              <!-- Info header -->
              <div class="flex justify-between items-center text-[9px] text-gray-400 pb-1.5 border-b border-gray-100/50 dark:border-zinc-800/40">
                <span class="font-bold truncate max-w-[180px]">{{ chunk.document_title || '关联文档' }}</span>
                <span class="font-mono bg-blue-50 dark:bg-blue-950/20 text-blue-600 px-1.5 py-0.5 rounded">
                  匹配分 {{ chunk.score.toFixed(3) }}
                </span>
              </div>
              <p class="text-gray-600 dark:text-zinc-300">{{ chunk.content }}</p>
            </div>

            <!-- Empty results placeholder -->
            <div v-if="searchResults.length === 0 && !searching" class="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-2 py-16">
              <Search class="w-8 h-8 text-gray-200 dark:text-zinc-800" />
              <p class="text-[10px]">在上方输入搜索内容，AI 会自动寻找最相似的知识切片。</p>
            </div>

            <div v-if="searching" class="py-12 flex items-center justify-center space-x-2 text-gray-400 text-xs">
              <RefreshCw class="w-4 h-4 animate-spin" />
              <span>向量数据库检索中...</span>
            </div>
          </div>
        </div>

        <!-- 2. RAG QA Tab -->
        <div v-else class="flex-1 flex flex-col min-h-0">
          <div class="flex items-center space-x-2 flex-shrink-0 mb-4">
            <input
              v-model="qaQuery"
              @keyup.enter="handleQA"
              type="text"
              placeholder="向大模型提问共享知识库内容..."
              class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded-lg text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
            />
            <button
              @click="handleQA"
              :disabled="askingQA"
              class="p-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg focus:outline-none disabled:opacity-50"
            >
              <MessageSquare class="w-4 h-4" />
            </button>
          </div>

          <!-- QA response sandbox -->
          <div class="flex-1 overflow-y-auto pr-1">
            <div v-if="qaAnswer" class="space-y-4 text-xs">
              <div class="p-4 bg-gray-50 dark:bg-zinc-950 rounded-lg border border-gray-100 dark:border-zinc-800/50 leading-relaxed text-gray-700 dark:text-zinc-300 whitespace-pre-wrap">
                {{ qaAnswer.answer }}
              </div>

              <!-- Citations -->
              <div v-if="qaAnswer.citations && qaAnswer.citations.length > 0" class="space-y-2 p-3 bg-blue-50/20 dark:bg-blue-950/10 rounded-lg border border-blue-100/30 dark:border-blue-900/20">
                <span class="text-[10px] text-blue-600 dark:text-blue-400 font-bold block flex items-center space-x-1">
                  <Layers class="w-3.5 h-3.5" />
                  <span>参考引文与学术来源 (Citations)</span>
                </span>
                <div class="space-y-1.5 text-[10px] text-gray-500 dark:text-zinc-400 font-mono">
                  <div v-for="(cit, idx) in qaAnswer.citations" :key="idx" class="flex items-start space-x-1.5">
                    <span class="bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-400 font-bold px-1.5 rounded flex-shrink-0">
                      [{{ cit.source_index }}]
                    </span>
                    <span class="leading-normal">{{ cit.document_title }} (相似度: {{ cit.score.toFixed(3) }})</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Empty QA Sandbox placeholder -->
            <div v-if="!qaAnswer && !askingQA" class="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-2 py-16">
              <HelpCircle class="w-8 h-8 text-gray-200 dark:text-zinc-800" />
              <p class="text-[10px]">提出问题，大模型会自动检索上传的文献库作为先验知识进行解答并罗列文献引用。</p>
            </div>

            <div v-if="askingQA" class="py-12 flex flex-col items-center justify-center space-y-3 text-gray-400 text-xs h-full">
              <RefreshCw class="w-5 h-5 animate-spin" />
              <span>知识定位中 & 大模型深度阅读中...</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Upload Document Dialog -->
    <el-dialog
      v-model="uploadDialogVisible"
      title="上传文献资料"
      width="420px"
      class="minimalist-dialog"
    >
      <div class="space-y-4 text-xs" v-loading="uploadingFile">
        <!-- File Picker -->
        <div class="space-y-1.5">
          <label class="text-gray-500 font-medium">选择本地文献文件 <span class="text-red-500">*</span></label>
          <div class="flex items-center justify-center w-full">
            <label
              class="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-200 dark:border-zinc-800 rounded-lg cursor-pointer hover:bg-gray-50/50 dark:hover:bg-zinc-950/20 transition-all"
            >
              <div class="flex flex-col items-center justify-center pt-5 pb-6">
                <Upload class="w-6 h-6 text-gray-400 mb-2" />
                <p class="text-[10px] text-gray-500 text-center px-4 leading-normal">
                  <span class="font-bold">点击选择</span> 或是拖拽文献到此区域
                </p>
                <p class="text-[9px] text-gray-400 mt-1">仅支持 PDF, DOCX, TXT, MD (最大 10MB)</p>
              </div>
              <input
                type="file"
                class="hidden"
                accept=".pdf,.docx,.txt,.md,.markdown"
                @change="handleFileChange"
              />
            </label>
          </div>
          <!-- Selected filename display -->
          <div v-if="selectedFile" class="p-2.5 rounded bg-blue-50/30 border border-blue-100/30 text-[10px] text-blue-700 flex items-center justify-between">
            <span class="truncate max-w-[280px] font-mono font-medium">{{ selectedFile.name }}</span>
            <span class="text-[9px] text-gray-400 font-mono">({{(selectedFile.size / 1024).toFixed(1)}} KB)</span>
          </div>
        </div>

        <!-- Document Title -->
        <div class="space-y-1">
          <label class="text-gray-500 font-medium">文献大纲标题 <span class="text-red-500">*</span></label>
          <input
            v-model="uploadForm.title"
            type="text"
            placeholder="文献命名"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
          />
        </div>

        <!-- Category & Visibility -->
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">资料分类</label>
            <select
              v-model="uploadForm.category"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500 bg-white"
            >
              <option value="学术论文">学术论文</option>
              <option value="技术笔记">技术笔记</option>
              <option value="开发文档">开发文档</option>
              <option value="其他">其他</option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">共享可见范围</label>
            <select
              v-model="uploadForm.visibility"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500 bg-white"
            >
              <option value="public">共享全实验室 (Public)</option>
              <option value="teachers_only">仅对导师可见 (Teachers only)</option>
              <option value="private">仅限自己可见 (Private)</option>
            </select>
          </div>
        </div>

        <!-- Description -->
        <div class="space-y-1">
          <label class="text-gray-500 font-medium">内容概要与描述（选填）</label>
          <textarea
            v-model="uploadForm.description"
            rows="3"
            placeholder="简要填写研究大纲背景..."
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
          ></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="uploadDialogVisible = false" :disabled="uploadingFile" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleUploadSubmit" :disabled="uploadingFile" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">开始解析上传</button>
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
  border-radius: 4px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
