<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CheckCircle2, Circle, Clock3, FileText, GraduationCap, Lock, PlaySquare, Send, UploadCloud } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { learningPathApi } from '../../api/modules/learning_path'
import type { LearningPathDetailOut, LearningPathNode, LearningPathTaskOut } from '../../api/modules/learning_path'

const paths = ref<LearningPathTaskOut[]>([])
const selectedPath = ref<LearningPathTaskOut | null>(null)
const detail = ref<LearningPathDetailOut | null>(null)
const loading = ref(false)
const submitDialogVisible = ref(false)
const selectedNode = ref<LearningPathNode | null>(null)
const submitForm = ref({
  content: '',
  attachment_ids: ''
})

const completedCount = computed(() => detail.value?.nodes.filter(node => node.progress?.status === 'completed').length || 0)
const totalCount = computed(() => detail.value?.nodes.length || 0)

const loadPaths = async () => {
  loading.value = true
  try {
    const res = await learningPathApi.listStudentPaths()
    paths.value = res.data || []
    if (paths.value.length > 0) {
      await selectPath(paths.value[0])
    }
  } catch (error) {
    console.warn('Failed to load student learning paths', error)
  } finally {
    loading.value = false
  }
}

const selectPath = async (path: LearningPathTaskOut) => {
  selectedPath.value = path
  detail.value = null
  try {
    const res = await learningPathApi.getPathDetail(path.id)
    detail.value = res.data
  } catch (error) {
    ElMessage.error('获取学习路径详情失败')
  }
}

const openSubmit = (node: LearningPathNode) => {
  if (node.progress?.status === 'locked') {
    ElMessage.warning('请先完成前置步骤')
    return
  }
  selectedNode.value = node
  submitForm.value = { content: '', attachment_ids: '' }
  submitDialogVisible.value = true
}

const submitNode = async () => {
  if (!selectedPath.value || !selectedNode.value?.id) return
  try {
    const attachmentIds = submitForm.value.attachment_ids
      .split(',')
      .map(item => item.trim())
      .filter(Boolean)
    await learningPathApi.submitNode(selectedPath.value.id, selectedNode.value.id, {
      content: submitForm.value.content,
      attachment_ids: attachmentIds,
      mark_complete: true
    })
    submitDialogVisible.value = false
    await selectPath(selectedPath.value)
    ElMessage.success('节点已完成，下一步已解锁')
  } catch (error) {
    ElMessage.error('提交失败')
  }
}

const statusText = (status?: string) => ({
  locked: '锁定',
  available: '可开始',
  submitted: '已提交',
  completed: '已完成',
  reopened: '需重做'
}[status || ''] || '未开始')

const nodeIcon = (nodeType: string) => {
  if (nodeType === 'video') return PlaySquare
  if (nodeType === 'reading') return FileText
  if (nodeType === 'submission') return UploadCloud
  return GraduationCap
}

const formatDate = (iso?: string) => {
  if (!iso) return '未设置'
  const date = new Date(iso)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const graphPoints = (nodes: LearningPathNode[]) => {
  const width = 900
  const gap = nodes.length > 1 ? width / (nodes.length - 1) : width
  return nodes.map((node, idx) => ({
    key: node.key || `node_${idx + 1}`,
    x: 45 + idx * gap,
    y: idx % 2 === 0 ? 76 : 144
  }))
}

onMounted(loadPaths)
</script>

<template>
  <div class="h-[calc(100vh-8rem)] flex gap-6 -m-4 p-4 overflow-hidden">
    <aside class="w-80 minimal-card bg-white dark:bg-zinc-900 p-5 flex flex-col">
      <div class="pb-4 border-b border-gray-100 dark:border-zinc-800">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">我的学习路径</h3>
        <p class="mt-1 text-[10px] text-gray-400">按老师发布的步骤逐步完成总任务</p>
      </div>

      <div class="mt-4 flex-1 overflow-y-auto space-y-2" v-loading="loading">
        <button
          v-for="path in paths"
          :key="path.id"
          @click="selectPath(path)"
          class="w-full text-left p-3 rounded-lg border transition-all"
          :class="selectedPath?.id === path.id
            ? 'border-blue-200 bg-blue-50/70 text-blue-800 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-300'
            : 'border-gray-100 bg-white hover:bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60'"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-xs font-semibold truncate">{{ path.title }}</span>
            <span class="text-[9px] text-gray-400">{{ path.avg_progress }}%</span>
          </div>
          <p class="mt-1 text-[10px] text-gray-400 line-clamp-2">{{ path.goal }}</p>
          <div class="mt-3 h-1.5 bg-gray-100 dark:bg-zinc-800 rounded">
            <div class="h-full bg-blue-600 rounded" :style="{ width: `${Math.min(100, path.avg_progress || 0)}%` }"></div>
          </div>
        </button>
        <div v-if="paths.length === 0 && !loading" class="py-12 text-center text-xs text-gray-400">
          暂无老师发布的学习路径任务。
        </div>
      </div>
    </aside>

    <section class="flex-1 overflow-y-auto pr-2">
      <div v-if="detail" class="space-y-6">
        <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
          <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
            <div>
              <h2 class="text-lg font-bold text-gray-900 dark:text-zinc-50">{{ detail.task.title }}</h2>
              <p class="mt-2 text-xs leading-relaxed text-gray-500 dark:text-zinc-400 max-w-3xl">{{ detail.task.goal }}</p>
              <div class="mt-4 flex flex-wrap gap-2 text-[10px]">
                <span class="px-2 py-1 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">截止 {{ formatDate(detail.task.due_date) }}</span>
                <span class="px-2 py-1 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">{{ completedCount }}/{{ totalCount }} 已完成</span>
              </div>
            </div>
            <div class="w-28 h-28 rounded-full border-8 border-blue-100 dark:border-blue-950/40 flex items-center justify-center">
              <span class="text-2xl font-bold text-blue-600">{{ detail.task.avg_progress }}%</span>
            </div>
          </div>

          <div class="mt-6 overflow-x-auto border border-gray-100 dark:border-zinc-800 rounded-lg bg-gray-50/50 dark:bg-zinc-950/40">
            <svg :width="1000" height="220" class="min-w-[1000px]">
              <template v-for="edge in detail.edges" :key="edge.id || `${edge.source_key}-${edge.target_key}`">
                <line
                  v-if="graphPoints(detail.nodes).find(p => p.key === edge.source_key) && graphPoints(detail.nodes).find(p => p.key === edge.target_key)"
                  :x1="graphPoints(detail.nodes).find(p => p.key === edge.source_key)!.x"
                  :y1="graphPoints(detail.nodes).find(p => p.key === edge.source_key)!.y"
                  :x2="graphPoints(detail.nodes).find(p => p.key === edge.target_key)!.x"
                  :y2="graphPoints(detail.nodes).find(p => p.key === edge.target_key)!.y"
                  stroke="#93c5fd"
                  stroke-width="2"
                />
              </template>
              <g v-for="(point, idx) in graphPoints(detail.nodes)" :key="point.key">
                <circle
                  :cx="point.x"
                  :cy="point.y"
                  r="24"
                  :fill="detail.nodes[idx].progress?.status === 'completed' ? '#10b981' : detail.nodes[idx].progress?.status === 'locked' ? '#e5e7eb' : '#ffffff'"
                  :stroke="detail.nodes[idx].progress?.status === 'locked' ? '#9ca3af' : '#2563eb'"
                  stroke-width="2"
                />
                <text :x="point.x" :y="point.y + 4" text-anchor="middle" :class="detail.nodes[idx].progress?.status === 'completed' ? 'fill-white' : 'fill-blue-700'" class="text-xs font-bold">{{ idx + 1 }}</text>
                <text :x="point.x" :y="point.y + 46" text-anchor="middle" class="fill-gray-600 text-[10px]">{{ detail.nodes[idx].title.slice(0, 9) }}</text>
              </g>
            </svg>
          </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div
            v-for="node in detail.nodes"
            :key="node.id"
            class="minimal-card bg-white dark:bg-zinc-900 p-5"
          >
            <div class="flex items-start gap-4">
              <div
                class="w-10 h-10 rounded border flex items-center justify-center"
                :class="node.progress?.status === 'completed'
                  ? 'bg-emerald-50 text-emerald-600 border-emerald-100 dark:bg-emerald-950/20 dark:border-emerald-900'
                  : node.progress?.status === 'locked'
                    ? 'bg-gray-50 text-gray-400 border-gray-100 dark:bg-zinc-950 dark:border-zinc-800'
                    : 'bg-blue-50 text-blue-600 border-blue-100 dark:bg-blue-950/20 dark:border-blue-900'"
              >
                <Lock v-if="node.progress?.status === 'locked'" class="w-4 h-4" />
                <CheckCircle2 v-else-if="node.progress?.status === 'completed'" class="w-4 h-4" />
                <component v-else :is="nodeIcon(node.node_type)" class="w-4 h-4" />
              </div>

              <div class="flex-1 min-w-0">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ node.title }}</h3>
                    <p class="mt-1 text-[10px] text-gray-400">{{ statusText(node.progress?.status) }} · 预计 {{ node.estimated_minutes }} 分钟</p>
                  </div>
                  <Clock3 class="w-4 h-4 text-gray-300" />
                </div>
                <p class="mt-3 text-xs leading-relaxed text-gray-500 dark:text-zinc-400">{{ node.description || '暂无说明' }}</p>

                <div v-if="node.resources.length" class="mt-4 flex flex-wrap gap-2">
                  <a
                    v-for="res in node.resources"
                    :key="res.id || res.bv_id || res.url"
                    :href="res.url"
                    target="_blank"
                    class="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300 text-[10px]"
                  >
                    <PlaySquare v-if="res.resource_type === 'bilibili'" class="w-3 h-3" />
                    <FileText v-else class="w-3 h-3" />
                    <span>{{ res.title || res.bv_id || res.url }}</span>
                  </a>
                </div>

                <button
                  @click="openSubmit(node)"
                  :disabled="node.progress?.status === 'locked' || node.progress?.status === 'completed'"
                  class="mt-5 inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium disabled:opacity-50"
                  :class="node.progress?.status === 'completed'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900'"
                >
                  <Send v-if="node.progress?.status !== 'completed'" class="w-3.5 h-3.5" />
                  <Circle v-else class="w-3.5 h-3.5" />
                  <span>{{ node.progress?.status === 'completed' ? '已完成' : '提交完成' }}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="h-full minimal-card bg-white dark:bg-zinc-900 flex flex-col items-center justify-center text-center text-gray-400">
        <GraduationCap class="w-10 h-10 mb-3 text-gray-300" />
        <p class="text-sm font-semibold">还没有学习路径</p>
        <p class="mt-1 text-xs">老师发布后会出现在这里。</p>
      </div>
    </section>

    <el-dialog v-model="submitDialogVisible" title="提交当前学习节点" width="520px">
      <div v-if="selectedNode" class="space-y-4">
        <div class="p-3 rounded border border-gray-100 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950">
          <p class="text-xs font-semibold text-gray-800 dark:text-zinc-200">{{ selectedNode.title }}</p>
          <p class="mt-1 text-[10px] text-gray-400">{{ selectedNode.description }}</p>
        </div>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">学习说明 / 作业内容</span>
          <textarea v-model="submitForm.content" rows="5" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs resize-none" placeholder="写下你完成的内容、遇到的问题或总结。"></textarea>
        </label>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">附件 ID（可选，多个用英文逗号分隔）</span>
          <input v-model="submitForm.attachment_ids" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" placeholder="上传文件后填入文件 ID" />
        </label>
      </div>
      <template #footer>
        <button @click="submitDialogVisible = false" class="px-4 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs mr-2">取消</button>
        <button @click="submitNode" class="px-4 py-1.5 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs">确认提交</button>
      </template>
    </el-dialog>
  </div>
</template>
