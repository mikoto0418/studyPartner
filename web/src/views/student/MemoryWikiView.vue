<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Brain,
  Database,
  FileText,
  GitFork,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Trash2,
  Users
} from 'lucide-vue-next'
import { authApi } from '../../api/modules/auth'
import {
  memoryWikiApi,
  type MemoryEventOut,
  type MemoryGraphOut,
  type MemoryLintIssue,
  type MemoryPageDetail,
  type MemoryPageOut,
  type MemoryReviewTaskOut,
  type MemoryWikiStats
} from '../../api/modules/memory_wiki'

const loading = ref(false)
const currentUserId = ref('')
const pages = ref<MemoryPageOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const keyword = ref('')
const pageType = ref('')
const status = ref('active')

const stats = ref<MemoryWikiStats | null>(null)
const detail = ref<MemoryPageDetail | null>(null)
const detailVisible = ref(false)
const createVisible = ref(false)
const lintIssues = ref<MemoryLintIssue[]>([])
const events = ref<MemoryEventOut[]>([])
const reviewTasks = ref<MemoryReviewTaskOut[]>([])
const graph = ref<MemoryGraphOut | null>(null)

const pageTypeLabels: Record<string, string> = {
  concept: '知识点',
  entity: '实体',
  pattern: '学习模式',
  goal: '目标',
  weakness: '薄弱点',
  event: '事件',
  relationship: '关系'
}

const createForm = ref({
  slug: '',
  page_type: 'concept',
  title: '',
  summary: '',
  body: '',
  category: 'other',
  tags: [] as string[],
  confidence: 0.6
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const ensureCurrentUser = async () => {
  if (currentUserId.value) return
  try {
    const res = await authApi.getMe()
    currentUserId.value = res.data.id
  } catch (e) {
    console.warn('Failed to load current user', e)
  }
}

const loadStats = async () => {
  try {
    const res = await memoryWikiApi.getStats()
    stats.value = res.data
  } catch (e) {
    console.warn('Failed to load stats', e)
  }
}

const loadPages = async () => {
  loading.value = true
  try {
    await ensureCurrentUser()
    const res = await memoryWikiApi.listPages({
      page: page.value,
      page_size: pageSize.value,
      keyword: keyword.value || undefined,
      page_type: pageType.value || undefined,
      status: status.value
    })
    pages.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.warn('Failed to load memory pages', e)
  } finally {
    loading.value = false
  }
}

const loadGraph = async () => {
  try {
    const res = await memoryWikiApi.getGraph()
    graph.value = res.data
  } catch (e) {
    console.warn('Failed to load graph', e)
  }
}

const loadEvents = async () => {
  try {
    const res = await memoryWikiApi.getEvents({ page: 1, page_size: 5 })
    events.value = res.data.items || []
  } catch (e) {
    console.warn('Failed to load events', e)
  }
}

const loadReviewTasks = async () => {
  try {
    const res = await memoryWikiApi.listReviewTasks({ status: 'pending', page: 1, page_size: 5 })
    reviewTasks.value = res.data.items || []
  } catch (e) {
    console.warn('Failed to load review tasks', e)
  }
}

const runLint = async () => {
  try {
    const res = await memoryWikiApi.runLint()
    lintIssues.value = res.data.issues || []
    ElMessage.success(`检查完成，共发现 ${lintIssues.value.length} 个问题`)
  } catch (e) {
    console.warn('Failed to run lint', e)
  }
}

const refresh = async () => {
  await Promise.all([loadStats(), loadPages(), loadGraph(), loadEvents(), loadReviewTasks()])
}

const resetFilters = () => {
  keyword.value = ''
  pageType.value = ''
  status.value = 'active'
  page.value = 1
  loadPages()
}

const openDetail = async (item: MemoryPageOut) => {
  detailVisible.value = true
  detail.value = null
  try {
    const res = await memoryWikiApi.getPage(item.id)
    detail.value = res.data
  } catch (e) {
    console.warn('Failed to load detail', e)
  }
}

const openCreate = () => {
  createForm.value = {
    slug: '',
    page_type: 'concept',
    title: '',
    summary: '',
    body: '',
    category: 'other',
    tags: [],
    confidence: 0.6
  }
  createVisible.value = true
}

const handleCreate = async () => {
  if (!createForm.value.title.trim()) {
    ElMessage.warning('请填写标题')
    return
  }
  try {
    await memoryWikiApi.createPage({
      slug: createForm.value.slug || createForm.value.title,
      page_type: createForm.value.page_type,
      title: createForm.value.title,
      summary: createForm.value.summary,
      body: createForm.value.body,
      category: createForm.value.category,
      tags: createForm.value.tags,
      confidence: createForm.value.confidence
    })
    ElMessage.success('记忆页已创建')
    createVisible.value = false
    loadPages()
    loadStats()
  } catch (e) {
    console.warn('Failed to create page', e)
  }
}

const handleArchive = async (item: MemoryPageOut) => {
  try {
    await ElMessageBox.confirm(`确认归档「${item.title}」？`, '归档确认', { type: 'warning' })
    await memoryWikiApi.archivePage(item.id)
    ElMessage.success('已归档')
    refresh()
  } catch (e) {
    // cancelled
  }
}

const handleDelete = async (item: MemoryPageOut) => {
  try {
    await ElMessageBox.confirm(`确认删除「${item.title}」？该操作会保留审计记录。`, '删除确认', { type: 'error' })
    await memoryWikiApi.deletePage(item.id)
    ElMessage.success('已删除')
    refresh()
  } catch (e) {
    // cancelled
  }
}

const approveTask = async (task: MemoryReviewTaskOut) => {
  await memoryWikiApi.approveReviewTask(task.id, '前端确认')
  ElMessage.success('已批准')
  loadReviewTasks()
  refresh()
}

const rejectTask = async (task: MemoryReviewTaskOut) => {
  await memoryWikiApi.rejectReviewTask(task.id, '前端拒绝')
  ElMessage.success('已拒绝')
  loadReviewTasks()
  refresh()
}

onMounted(async () => {
  await ensureCurrentUser()
  await refresh()
})
</script>

<template>
  <div class="space-y-6">
    <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
      <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <Brain class="w-5 h-5 text-blue-600" />
            <h2 class="text-lg font-bold text-gray-900 dark:text-zinc-50">记忆 Wiki</h2>
          </div>
          <p class="mt-2 text-xs leading-relaxed text-gray-500 dark:text-zinc-400 max-w-3xl">
            基于 LLM Wiki 思想维护的长期学习记忆。页面、证据、链接和审计记录共同构成你的结构化学生画像。
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button @click="runLint" class="ui-button-secondary">
            <ShieldCheck class="w-3.5 h-3.5" />
            健康检查
          </button>
          <button @click="openCreate" class="ui-button-primary">
            <Plus class="w-3.5 h-3.5" />
            新建记忆页
          </button>
          <button @click="refresh" class="ui-button-secondary">
            <RefreshCw class="w-3.5 h-3.5" />
            刷新
          </button>
        </div>
      </div>

      <div v-if="stats" class="mt-5 grid grid-cols-2 lg:grid-cols-5 gap-4">
        <div class="rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/60 dark:bg-zinc-950/50 p-3">
          <p class="text-[10px] text-gray-400">总页面</p>
          <p class="mt-1 text-xl font-bold text-gray-900 dark:text-zinc-50">{{ stats.total_pages }}</p>
        </div>
        <div class="rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/60 dark:bg-zinc-950/50 p-3">
          <p class="text-[10px] text-gray-400">活跃页面</p>
          <p class="mt-1 text-xl font-bold text-blue-600">{{ stats.active_pages }}</p>
        </div>
        <div class="rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/60 dark:bg-zinc-950/50 p-3">
          <p class="text-[10px] text-gray-400">证据条数</p>
          <p class="mt-1 text-xl font-bold text-emerald-600">{{ stats.source_count }}</p>
        </div>
        <div class="rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/60 dark:bg-zinc-950/50 p-3">
          <p class="text-[10px] text-gray-400">关联数</p>
          <p class="mt-1 text-xl font-bold text-purple-600">{{ stats.link_count }}</p>
        </div>
        <div class="rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/60 dark:bg-zinc-950/50 p-3">
          <p class="text-[10px] text-gray-400">待确认</p>
          <p class="mt-1 text-xl font-bold text-amber-600">{{ stats.review_task_count }}</p>
        </div>
      </div>

      <div v-if="lintIssues.length" class="mt-4 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-900 dark:bg-amber-950/20 p-4">
        <div class="flex items-center gap-2">
          <ShieldCheck class="w-4 h-4 text-amber-600" />
          <h3 class="text-sm font-semibold text-amber-800 dark:text-amber-200">健康检查发现 {{ lintIssues.length }} 个问题</h3>
        </div>
        <ul class="mt-2 grid gap-1.5">
          <li v-for="issue in lintIssues" :key="issue.page_id + issue.issue_type" class="text-xs text-amber-700 dark:text-amber-300">
            [{{ issue.issue_type }}] {{ issue.message }}
          </li>
        </ul>
      </div>

      <div class="mt-5 flex flex-wrap items-center gap-3">
        <div class="relative flex-1 min-w-[220px] max-w-sm">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400" />
          <input
            v-model="keyword"
            @keyup.enter="page = 1; loadPages()"
            class="ui-field pl-9"
            placeholder="搜索标题 / 摘要 / 正文"
          />
        </div>
        <select v-model="pageType" @change="page = 1; loadPages()" class="ui-field">
          <option value="">全部类型</option>
          <option v-for="(label, key) in pageTypeLabels" :key="key" :value="key">{{ label }}</option>
        </select>
        <select v-model="status" @change="page = 1; loadPages()" class="ui-field">
          <option value="active">活跃</option>
          <option value="draft">草稿</option>
          <option value="archived">已归档</option>
        </select>
        <button @click="page = 1; loadPages()" class="ui-button-secondary">查询</button>
        <button @click="resetFilters" class="ui-button-secondary">重置</button>
      </div>
    </div>

    <div class="minimal-card bg-white dark:bg-zinc-900 p-6" v-loading="loading">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">记忆页面</h3>
          <p class="mt-1 text-xs text-gray-400">共 {{ total }} 条</p>
        </div>
      </div>

      <div v-if="pages.length" class="space-y-3">
        <div
          v-for="item in pages"
          :key="item.id"
          class="flex items-start justify-between gap-4 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/40 dark:bg-zinc-950/40 p-4 hover:border-blue-200 hover:bg-blue-50/40 dark:hover:border-blue-900 dark:hover:bg-blue-950/10 transition-colors cursor-pointer"
          @click="openDetail(item)"
        >
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <span class="rounded bg-blue-50 dark:bg-blue-950/40 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-300">
                {{ pageTypeLabels[item.page_type] || item.page_type }}
              </span>
              <span class="text-xs text-gray-400">{{ item.category }}</span>
              <h4 class="truncate text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ item.title }}</h4>
            </div>
            <p v-if="item.summary" class="mt-1 ml-9 line-clamp-1 text-xs text-gray-500 dark:text-zinc-400">{{ item.summary }}</p>
            <div class="mt-2 ml-9 flex items-center gap-3 text-[10px] text-gray-400">
              <span>置信度 {{ (item.confidence * 100).toFixed(0) }}%</span>
              <span>v{{ item.version }}</span>
              <span>{{ item.updated_at?.slice(0, 10) }}</span>
            </div>
          </div>
          <div class="flex shrink-0 items-center gap-1">
            <button class="ui-icon-button" @click.stop="handleArchive(item)" title="归档">
              <Database class="w-3.5 h-3.5" />
            </button>
            <button class="ui-icon-button" @click.stop="handleDelete(item)" title="删除">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
      <div v-else class="flex flex-col items-center justify-center py-16 text-center">
        <FileText class="h-8 w-8 text-gray-300" />
        <p class="mt-3 text-sm text-gray-400">还没有记忆页面，可以先手动创建，或等待每日复盘自动生成。</p>
      </div>

      <div class="mt-4 flex items-center justify-between">
        <span class="text-xs text-gray-400">第 {{ page }} / {{ totalPages }} 页</span>
        <div class="flex gap-2">
          <button :disabled="page <= 1" class="ui-button-secondary disabled:opacity-40" @click="page--; loadPages()">上一页</button>
          <button :disabled="page >= totalPages" class="ui-button-secondary disabled:opacity-40" @click="page++; loadPages()">下一页</button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
        <div class="flex items-center gap-2">
          <GitFork class="w-4 h-4 text-blue-600" />
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">记忆图谱</h3>
        </div>
        <div class="mt-4 flex items-center gap-6 text-sm">
          <div>
            <p class="text-2xl font-bold text-gray-900 dark:text-zinc-50">{{ graph?.nodes.length || 0 }}</p>
            <p class="text-xs text-gray-400">节点</p>
          </div>
          <div>
            <p class="text-2xl font-bold text-gray-900 dark:text-zinc-50">{{ graph?.edges.length || 0 }}</p>
            <p class="text-xs text-gray-400">关联</p>
          </div>
        </div>
        <div v-if="graph?.nodes.length" class="mt-4 max-h-56 overflow-auto space-y-1.5">
          <div v-for="node in graph.nodes" :key="node.id" class="flex items-center justify-between rounded px-2 py-1.5 text-xs bg-gray-50 dark:bg-zinc-950/40">
            <span class="font-medium text-gray-700 dark:text-zinc-300">{{ node.title }}</span>
            <span class="text-gray-400">{{ pageTypeLabels[node.page_type] || node.page_type }}</span>
          </div>
        </div>
      </div>

      <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
        <div class="flex items-center gap-2">
          <Users class="w-4 h-4 text-blue-600" />
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">待确认变更</h3>
        </div>
        <div v-if="reviewTasks.length" class="mt-4 space-y-2">
          <div v-for="task in reviewTasks" :key="task.id" class="rounded-lg border border-gray-100 dark:border-zinc-800 p-3">
            <p class="text-xs font-medium text-gray-700 dark:text-zinc-300">[{{ task.task_type }}] {{ task.payload?.title || task.page_id }}</p>
            <p class="mt-1 text-[10px] text-gray-400">{{ task.created_at?.slice(0, 16) }}</p>
            <div class="mt-2 flex gap-2">
              <button @click="approveTask(task)" class="rounded bg-emerald-50 px-2 py-1 text-[10px] font-medium text-emerald-600 hover:bg-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300">批准</button>
              <button @click="rejectTask(task)" class="rounded bg-red-50 px-2 py-1 text-[10px] font-medium text-red-500 hover:bg-red-100 dark:bg-red-950/30 dark:text-red-300">拒绝</button>
            </div>
          </div>
        </div>
        <p v-else class="mt-4 text-xs text-gray-400">当前没有待确认的记忆变更。</p>
      </div>
    </div>

    <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
      <div class="flex items-center gap-2">
        <ShieldCheck class="w-4 h-4 text-blue-600" />
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">最近审计事件</h3>
      </div>
      <div v-if="events.length" class="mt-4 space-y-2">
        <div v-for="event in events" :key="event.id" class="flex items-start justify-between gap-4 rounded bg-gray-50/60 dark:bg-zinc-950/40 px-3 py-2">
          <div class="min-w-0">
            <p class="text-xs text-gray-700 dark:text-zinc-300">
              <span class="font-semibold">{{ event.action }}</span>
              <span class="mx-1 text-gray-400">·</span>{{ event.reason || '' }}
            </p>
            <p class="mt-0.5 text-[10px] text-gray-400">{{ event.created_at?.slice(0, 16) }} · {{ event.operator }}</p>
          </div>
        </div>
      </div>
      <p v-else class="mt-4 text-xs text-gray-400">暂无审计事件。</p>
    </div>

    <el-dialog v-model="createVisible" title="新建记忆页" width="640px">
      <div class="space-y-4">
        <div>
          <label class="text-xs font-medium text-gray-500">标题 *</label>
          <input v-model="createForm.title" class="ui-field mt-1" placeholder="例如：动态规划状态定义" />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-xs font-medium text-gray-500">类型</label>
            <select v-model="createForm.page_type" class="ui-field mt-1">
              <option v-for="(label, key) in pageTypeLabels" :key="key" :value="key">{{ label }}</option>
            </select>
          </div>
          <div>
            <label class="text-xs font-medium text-gray-500">分类</label>
            <input v-model="createForm.category" class="ui-field mt-1" placeholder="other" />
          </div>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500">摘要</label>
          <input v-model="createForm.summary" class="ui-field mt-1" placeholder="一句话说明这条记忆" />
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500">正文 / 详情</label>
          <textarea v-model="createForm.body" rows="4" class="ui-field mt-1" placeholder="支持 Markdown"></textarea>
        </div>
        <div>
          <label class="text-xs font-medium text-gray-500">初始置信度</label>
          <input v-model.number="createForm.confidence" type="number" min="0" max="1" step="0.05" class="ui-field mt-1" />
        </div>
      </div>
      <template #footer>
        <button class="ui-button-secondary" @click="createVisible = false">取消</button>
        <button class="ui-button-primary" @click="handleCreate">创建</button>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="detail?.title || '记忆页详情'" size="540px">
      <div v-if="detail" class="space-y-6">
        <div>
          <div class="flex items-center gap-2">
            <span class="rounded bg-blue-50 dark:bg-blue-950/40 px-1.5 py-0.5 text-[10px] font-medium text-blue-600 dark:text-blue-300">
              {{ pageTypeLabels[detail.page_type] || detail.page_type }}
            </span>
            <span class="text-xs text-gray-400">v{{ detail.version }} · 置信度 {{ (detail.confidence * 100).toFixed(0) }}%</span>
          </div>
          <div v-if="detail.summary" class="mt-3 text-sm leading-relaxed text-gray-600 dark:text-zinc-300">{{ detail.summary }}</div>
          <div v-if="detail.body" class="mt-3 whitespace-pre-wrap rounded-lg bg-gray-50 dark:bg-zinc-950/40 p-4 text-sm leading-relaxed text-gray-700 dark:text-zinc-300">{{ detail.body }}</div>
        </div>

        <div>
          <h4 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">证据来源（{{ detail.sources.length }}）</h4>
          <div class="mt-2 space-y-2">
            <div v-for="src in detail.sources" :key="src.id" class="rounded border border-gray-100 dark:border-zinc-800 p-3">
              <div class="flex items-center gap-2 text-[10px] text-gray-400">
                <span class="font-medium text-gray-500 dark:text-zinc-400">{{ src.source_type }}</span>
                <span>{{ src.occurred_at?.slice(0, 10) }}</span>
              </div>
              <p v-if="src.snippet" class="mt-1 text-xs text-gray-600 dark:text-zinc-300">{{ src.snippet }}</p>
            </div>
            <p v-if="!detail.sources.length" class="text-xs text-gray-400">暂无证据，可在每日复盘后自动补充。</p>
          </div>
        </div>

        <div>
          <h4 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">关联（{{ detail.outbound_links.length + detail.inbound_links.length }}）</h4>
          <div class="mt-2 space-y-1.5">
            <div v-for="link in detail.outbound_links" :key="link.id" class="flex items-center justify-between rounded bg-gray-50/60 dark:bg-zinc-950/40 px-3 py-2 text-xs">
              <span class="text-gray-600 dark:text-zinc-300">{{ link.target_title || link.to_page_id }}</span>
              <span class="text-gray-400">{{ link.relation }}</span>
            </div>
            <div v-for="link in detail.inbound_links" :key="link.id" class="flex items-center justify-between rounded bg-gray-50/60 dark:bg-zinc-950/40 px-3 py-2 text-xs">
              <span class="text-gray-600 dark:text-zinc-300">{{ link.source_title || link.from_page_id }} → 当前页</span>
              <span class="text-gray-400">{{ link.relation }}</span>
            </div>
            <p v-if="!detail.outbound_links.length && !detail.inbound_links.length" class="text-xs text-gray-400">暂无关联页面。</p>
          </div>
        </div>

        <div class="flex gap-2 pt-2">
          <button class="ui-button-secondary" @click="handleArchive(detail)">归档</button>
          <button class="ui-button-danger" @click="handleDelete(detail)">删除</button>
        </div>
      </div>
      <div v-else class="flex items-center justify-center py-16 text-sm text-gray-400">加载中...</div>
    </el-drawer>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>