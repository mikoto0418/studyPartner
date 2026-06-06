<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Bot,
  CheckCircle2,
  FileText,
  GitBranch,
  GraduationCap,
  Link,
  Pencil,
  PlaySquare,
  Plus,
  RefreshCw,
  Save,
  Send,
  UploadCloud,
  Users
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { learningPathApi } from '../../api/modules/learning_path'
import type {
  ClassOut,
  LearningPathDetailOut,
  LearningPathNode,
  LearningPathPlanOut,
  LearningPathTaskOut
} from '../../api/modules/learning_path'
import { userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'

const paths = ref<LearningPathTaskOut[]>([])
const classes = ref<ClassOut[]>([])
const students = ref<UserOut[]>([])
const selectedPath = ref<LearningPathTaskOut | null>(null)
const detail = ref<LearningPathDetailOut | null>(null)
const loading = ref(false)
const generating = ref(false)
const saving = ref(false)

const createPanelOpen = ref(false)
const reviewDialogVisible = ref(false)

const pathForm = ref({
  title: '',
  goal: '',
  planning_text: '',
  class_id: '',
  assignee_ids: [] as string[],
  due_date: '',
  publish: true
})

const generatedPlan = ref<LearningPathPlanOut | null>(null)
const selectedSubmission = ref<Record<string, any> | null>(null)
const reviewForm = ref({
  review_status: 'approved' as 'approved' | 'rejected' | 'revise',
  score: 90,
  feedback: '',
  follow_up: ''
})

const selectedClass = computed(() => classes.value.find(item => item.id === pathForm.value.class_id))
const totalMinutes = computed(() => generatedPlan.value?.nodes.reduce((sum, node) => sum + (node.estimated_minutes || 0), 0) || 0)

const loadInitialData = async () => {
  loading.value = true
  try {
    const [pathRes, classRes, studentRes] = await Promise.all([
      learningPathApi.listTeacherPaths(),
      learningPathApi.listClasses(),
      userApi.listUsers({ role_code: 'student', page_size: 100 })
    ])
    paths.value = pathRes.data || []
    classes.value = classRes.data || []
    students.value = studentRes.data?.items || []
    if (paths.value.length > 0) {
      await selectPath(paths.value[0])
    }
  } catch (error) {
    console.warn('Failed to load learning path data', error)
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  pathForm.value = {
    title: '',
    goal: '',
    planning_text: '',
    class_id: '',
    assignee_ids: [],
    due_date: '',
    publish: true
  }
  generatedPlan.value = null
}

const handleGeneratePlan = async () => {
  if (!pathForm.value.goal.trim() || !pathForm.value.planning_text.trim()) {
    ElMessage.warning('请先输入学习目标和粗略规划')
    return
  }
  generating.value = true
  try {
    const res = await learningPathApi.generatePlan({
      goal: pathForm.value.goal,
      planning_text: pathForm.value.planning_text
    })
    generatedPlan.value = res.data
    if (!pathForm.value.title) pathForm.value.title = pathForm.value.goal
    ElMessage.success('学习路径草案已生成')
  } catch (error) {
    ElMessage.error('生成学习路径失败')
  } finally {
    generating.value = false
  }
}

const addNode = () => {
  if (!generatedPlan.value) {
    generatedPlan.value = {
      stages: [{ title: '学习路径', description: '教师手动创建的路径。', order_index: 0 }],
      nodes: [],
      edges: [],
      resources: [],
      summary: '教师手动创建路径'
    }
  }
  const nextIndex = generatedPlan.value.nodes.length
  const key = `node_${nextIndex + 1}`
  const prevNode = generatedPlan.value.nodes[nextIndex - 1]
  generatedPlan.value.nodes.push({
    key,
    title: '新的学习步骤',
    description: '',
    node_type: 'learning',
    order_index: nextIndex,
    estimated_minutes: 45,
    required: true,
    resources: [],
    config: { stage_order: 0 }
  })
  if (prevNode?.key) {
    generatedPlan.value.edges.push({ source_key: prevNode.key, target_key: key })
  }
}

const removeNode = (index: number) => {
  if (!generatedPlan.value) return
  generatedPlan.value.nodes.splice(index, 1)
  generatedPlan.value.nodes.forEach((node, idx) => {
    node.order_index = idx
    node.key = node.key || `node_${idx + 1}`
  })
  generatedPlan.value.edges = generatedPlan.value.nodes.slice(0, -1).map((node, idx) => ({
    source_key: node.key || `node_${idx + 1}`,
    target_key: generatedPlan.value!.nodes[idx + 1].key || `node_${idx + 2}`
  }))
}

const addResource = (node: LearningPathNode, type: 'bilibili' | 'file' | 'link') => {
  node.resources.push({
    resource_type: type,
    title: type === 'bilibili' ? 'B站视频资源' : type === 'file' ? '文档附件' : '外部链接',
    bv_id: type === 'bilibili' ? '' : undefined,
    url: type === 'link' ? '' : undefined
  })
}

const handleCreatePath = async () => {
  if (!pathForm.value.title.trim() || !pathForm.value.goal.trim()) {
    ElMessage.warning('请填写标题和学习目标')
    return
  }
  if (!generatedPlan.value) {
    ElMessage.warning('请先生成或手动添加路径节点')
    return
  }

  saving.value = true
  try {
    const res = await learningPathApi.createPath({
      title: pathForm.value.title,
      goal: pathForm.value.goal,
      planning_text: pathForm.value.planning_text,
      class_id: pathForm.value.class_id || undefined,
      assignee_ids: pathForm.value.assignee_ids,
      due_date: pathForm.value.due_date ? new Date(pathForm.value.due_date).toISOString() : undefined,
      publish: pathForm.value.publish,
      stages: generatedPlan.value.stages,
      nodes: generatedPlan.value.nodes,
      edges: generatedPlan.value.edges
    })
    paths.value.unshift(res.data)
    createPanelOpen.value = false
    resetForm()
    await selectPath(res.data)
    ElMessage.success('学习路径任务已发布')
  } catch (error) {
    ElMessage.error('保存学习路径失败')
  } finally {
    saving.value = false
  }
}

const selectPath = async (path: LearningPathTaskOut) => {
  selectedPath.value = path
  detail.value = null
  try {
    const res = await learningPathApi.getPathDetail(path.id)
    detail.value = res.data
  } catch (error) {
    console.warn('Failed to load learning path detail', error)
  }
}

const startReview = (submission: Record<string, any>) => {
  selectedSubmission.value = submission
  reviewForm.value = {
    review_status: 'approved',
    score: submission.score || 90,
    feedback: submission.feedback || '',
    follow_up: submission.follow_up || ''
  }
  reviewDialogVisible.value = true
}

const saveReview = async () => {
  if (!selectedSubmission.value || !detail.value) return
  try {
    await learningPathApi.reviewSubmission(selectedSubmission.value.id, reviewForm.value)
    reviewDialogVisible.value = false
    if (selectedPath.value) await selectPath(selectedPath.value)
    ElMessage.success('批改反馈已保存')
  } catch (error) {
    ElMessage.error('批改保存失败')
  }
}

const formatDate = (iso?: string) => {
  if (!iso) return '未设置'
  const date = new Date(iso)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const statusText = (status: string) => ({
  draft: '草稿',
  published: '已发布',
  not_started: '未开始',
  in_progress: '进行中',
  completed: '已完成',
  available: '可开始',
  locked: '锁定',
  submitted: '已提交',
  reopened: '已重开'
}[status] || status)

const nodeIcon = (nodeType: string) => {
  if (nodeType === 'video') return PlaySquare
  if (nodeType === 'reading') return FileText
  if (nodeType === 'practice') return Pencil
  if (nodeType === 'submission') return UploadCloud
  if (nodeType === 'checkpoint') return CheckCircle2
  return GraduationCap
}

const graphPoints = (nodes: LearningPathNode[]) => {
  const width = 920
  const gap = nodes.length > 1 ? width / (nodes.length - 1) : width
  return nodes.map((node, idx) => ({
    key: node.key || `node_${idx + 1}`,
    x: 40 + idx * gap,
    y: idx % 2 === 0 ? 74 : 146
  }))
}

onMounted(loadInitialData)
</script>

<template>
  <div class="h-[calc(100vh-8rem)] flex gap-6 -m-4 p-4 overflow-hidden">
    <aside class="w-80 minimal-card bg-white dark:bg-zinc-900 p-5 flex flex-col">
      <div class="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">学习路径任务</h3>
          <p class="mt-1 text-[10px] text-gray-400">教师规划、AI 拆解、学生逐步完成</p>
        </div>
        <button
          @click="createPanelOpen = true"
          class="p-2 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
          title="新建学习路径"
        >
          <Plus class="w-4 h-4" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto mt-4 space-y-2" v-loading="loading">
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
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-zinc-800 text-gray-500">
              {{ statusText(path.status) }}
            </span>
          </div>
          <p class="mt-1 text-[10px] text-gray-400 line-clamp-2">{{ path.goal }}</p>
          <div class="mt-3 flex items-center justify-between text-[10px] text-gray-400">
            <span>{{ path.assignee_count }} 人</span>
            <span>{{ path.avg_progress }}%</span>
          </div>
          <div class="mt-1 h-1.5 bg-gray-100 dark:bg-zinc-800 rounded overflow-hidden">
            <div class="h-full bg-blue-600 rounded" :style="{ width: `${Math.min(100, path.avg_progress || 0)}%` }"></div>
          </div>
        </button>

        <div v-if="paths.length === 0 && !loading" class="py-12 text-center text-xs text-gray-400">
          暂无学习路径任务。
        </div>
      </div>
    </aside>

    <section class="flex-1 overflow-y-auto pr-2">
      <div v-if="detail" class="space-y-6">
        <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
          <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
            <div>
              <div class="flex items-center gap-2">
                <GitBranch class="w-4 h-4 text-blue-600" />
                <h2 class="text-lg font-bold text-gray-900 dark:text-zinc-50">{{ detail.task.title }}</h2>
              </div>
              <p class="mt-2 text-xs text-gray-500 dark:text-zinc-400 leading-relaxed max-w-3xl">{{ detail.task.goal }}</p>
              <div class="mt-4 flex flex-wrap items-center gap-2 text-[10px]">
                <span class="px-2 py-1 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">截止 {{ formatDate(detail.task.due_date) }}</span>
                <span class="px-2 py-1 rounded bg-gray-100 text-gray-500 dark:bg-zinc-800">{{ detail.task.assignee_count }} 名学生</span>
                <span class="px-2 py-1 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">平均进度 {{ detail.task.avg_progress }}%</span>
              </div>
            </div>
            <button
              @click="selectedPath && selectPath(selectedPath)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs text-gray-500 hover:bg-gray-50 dark:hover:bg-zinc-800"
            >
              <RefreshCw class="w-3.5 h-3.5" />
              <span>刷新</span>
            </button>
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
                  stroke-dasharray="5 6"
                />
              </template>
              <g v-for="(point, idx) in graphPoints(detail.nodes)" :key="point.key">
                <circle :cx="point.x" :cy="point.y" r="24" fill="#ffffff" stroke="#2563eb" stroke-width="2" />
                <text :x="point.x" :y="point.y + 4" text-anchor="middle" class="fill-blue-700 text-xs font-bold">{{ idx + 1 }}</text>
                <text :x="point.x" :y="point.y + 46" text-anchor="middle" class="fill-gray-600 text-[10px]">{{ detail.nodes[idx].title.slice(0, 9) }}</text>
              </g>
            </svg>
          </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div class="xl:col-span-7 minimal-card bg-white dark:bg-zinc-900 p-6">
            <h3 class="text-sm font-semibold mb-4 text-gray-900 dark:text-zinc-50">路径节点</h3>
            <div class="space-y-3">
              <div
                v-for="node in detail.nodes"
                :key="node.id"
                class="p-4 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/40 dark:bg-zinc-950/30"
              >
                <div class="flex items-start gap-3">
                  <div class="w-9 h-9 rounded bg-white dark:bg-zinc-900 border border-gray-100 dark:border-zinc-800 flex items-center justify-center text-blue-600">
                    <component :is="nodeIcon(node.node_type)" class="w-4 h-4" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-3">
                      <h4 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">{{ node.title }}</h4>
                      <span class="text-[10px] text-gray-400">{{ node.estimated_minutes }} 分钟</span>
                    </div>
                    <p class="mt-1 text-[11px] leading-relaxed text-gray-500 dark:text-zinc-400">{{ node.description || '暂无说明' }}</p>
                    <div v-if="node.resources.length" class="mt-3 flex flex-wrap gap-2">
                      <a
                        v-for="res in node.resources"
                        :key="res.id || res.bv_id || res.url"
                        :href="res.url"
                        target="_blank"
                        class="inline-flex items-center gap-1 text-[10px] px-2 py-1 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300"
                      >
                        <PlaySquare v-if="res.resource_type === 'bilibili'" class="w-3 h-3" />
                        <Link v-else class="w-3 h-3" />
                        <span>{{ res.title || res.bv_id || res.url }}</span>
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="xl:col-span-5 space-y-6">
            <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
              <h3 class="text-sm font-semibold mb-4 text-gray-900 dark:text-zinc-50">学生进度</h3>
              <div class="space-y-3 max-h-72 overflow-y-auto">
                <div
                  v-for="item in detail.assignees"
                  :key="item.id"
                  class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800"
                >
                  <div class="flex items-center justify-between">
                    <span class="text-xs font-semibold text-gray-800 dark:text-zinc-200">{{ item.nickname || item.username }}</span>
                    <span class="text-[10px] text-gray-400">{{ statusText(item.status) }}</span>
                  </div>
                  <div class="mt-2 h-1.5 bg-gray-100 dark:bg-zinc-800 rounded">
                    <div class="h-full bg-emerald-500 rounded" :style="{ width: `${Math.min(100, item.progress_percent || 0)}%` }"></div>
                  </div>
                </div>
                <div v-if="detail.assignees.length === 0" class="py-8 text-center text-xs text-gray-400">
                  尚未分配学生。
                </div>
              </div>
            </div>

            <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
              <h3 class="text-sm font-semibold mb-4 text-gray-900 dark:text-zinc-50">提交与批改</h3>
              <div class="space-y-3 max-h-96 overflow-y-auto">
                <div
                  v-for="submission in detail.submissions"
                  :key="submission.id"
                  class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/40 dark:bg-zinc-950/30"
                >
                  <div class="flex items-center justify-between text-[10px] text-gray-400">
                    <span>{{ submission.nickname || submission.username }} · {{ submission.node_title }}</span>
                    <span>{{ submission.review_status }}</span>
                  </div>
                  <p class="mt-2 text-xs text-gray-700 dark:text-zinc-300 whitespace-pre-wrap line-clamp-3">{{ submission.content || '无文本说明' }}</p>
                  <div class="mt-3 flex items-center justify-between">
                    <span class="text-[10px] text-gray-400">分数 {{ submission.score ?? '未评分' }}</span>
                    <button
                      @click="startReview(submission)"
                      class="px-2.5 py-1 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-[10px]"
                    >
                      {{ submission.reviewed_at ? '追评' : '批改' }}
                    </button>
                  </div>
                </div>
                <div v-if="detail.submissions.length === 0" class="py-8 text-center text-xs text-gray-400">
                  暂无学生提交。
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="h-full minimal-card bg-white dark:bg-zinc-900 flex flex-col items-center justify-center text-center text-gray-400">
        <Bot class="w-10 h-10 mb-3 text-gray-300" />
        <p class="text-sm font-semibold">选择或创建一个学习路径任务</p>
        <p class="mt-1 text-xs">把粗略目标拆成可执行步骤，再发布给学生。</p>
      </div>
    </section>

    <el-drawer v-model="createPanelOpen" title="创建学习路径任务" size="720px" destroy-on-close>
      <div class="space-y-5">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label class="space-y-1">
            <span class="text-xs text-gray-500">任务标题</span>
            <input v-model="pathForm.title" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs focus:outline-none focus:border-blue-500" placeholder="例如：Transformer 入门路径" />
          </label>
          <label class="space-y-1">
            <span class="text-xs text-gray-500">截止日期</span>
            <input v-model="pathForm.due_date" type="date" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs focus:outline-none focus:border-blue-500" />
          </label>
        </div>

        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">学习目标</span>
          <input v-model="pathForm.goal" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs focus:outline-none focus:border-blue-500" placeholder="我要让学生学会什么？" />
        </label>

        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">粗略规划</span>
          <textarea v-model="pathForm.planning_text" rows="4" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs focus:outline-none focus:border-blue-500 resize-none" placeholder="例如：先理解注意力机制，再看 BV...，然后完成小实验，最后提交总结文档。"></textarea>
        </label>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label class="space-y-1">
            <span class="text-xs text-gray-500">发布班级</span>
            <select v-model="pathForm.class_id" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs focus:outline-none focus:border-blue-500">
              <option value="">不选择班级</option>
              <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}（{{ item.member_count }}人）</option>
            </select>
          </label>
          <label class="space-y-1">
            <span class="text-xs text-gray-500">单独指派学生</span>
            <el-select v-model="pathForm.assignee_ids" multiple class="w-full" placeholder="可多选">
              <el-option v-for="student in students" :key="student.id" :label="student.nickname || student.username" :value="student.id" />
            </el-select>
          </label>
        </div>

        <div v-if="selectedClass" class="p-3 rounded border border-blue-100 bg-blue-50/60 dark:border-blue-900 dark:bg-blue-950/20 text-xs text-blue-700 dark:text-blue-300 flex items-center gap-2">
          <Users class="w-4 h-4" />
          <span>将自动分配给 {{ selectedClass.member_count }} 名班级学生，可再叠加单独指派对象。</span>
        </div>

        <div class="flex items-center justify-between">
          <button
            @click="handleGeneratePlan"
            :disabled="generating"
            class="inline-flex items-center gap-1.5 px-3 py-2 rounded bg-blue-600 text-white text-xs font-medium disabled:opacity-50"
          >
            <Bot class="w-4 h-4" />
            <span>{{ generating ? '生成中' : '生成学习路径图谱' }}</span>
          </button>
          <div class="flex items-center gap-3 text-[10px] text-gray-400">
            <span v-if="generatedPlan">{{ generatedPlan.nodes.length }} 步</span>
            <span v-if="generatedPlan">约 {{ totalMinutes }} 分钟</span>
          </div>
        </div>

        <div v-if="generatedPlan" class="space-y-4 pt-4 border-t border-gray-100 dark:border-zinc-800">
          <div class="flex items-center justify-between">
            <div>
              <h4 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">路径草案微调</h4>
              <p class="text-[10px] text-gray-400 mt-1">{{ generatedPlan.summary }}</p>
            </div>
            <button @click="addNode" class="inline-flex items-center gap-1 px-2.5 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs">
              <Plus class="w-3.5 h-3.5" />
              <span>添加步骤</span>
            </button>
          </div>

          <div class="space-y-3">
            <div v-for="(node, index) in generatedPlan.nodes" :key="node.key || index" class="p-4 rounded-lg border border-gray-100 dark:border-zinc-800">
              <div class="flex items-start gap-3">
                <div class="w-7 h-7 rounded bg-blue-50 text-blue-600 flex items-center justify-center text-xs font-bold">{{ index + 1 }}</div>
                <div class="flex-1 space-y-3">
                  <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <input v-model="node.title" class="md:col-span-2 px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" />
                    <select v-model="node.node_type" class="px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs">
                      <option value="learning">学习</option>
                      <option value="video">视频</option>
                      <option value="reading">阅读</option>
                      <option value="practice">练习</option>
                      <option value="submission">提交</option>
                      <option value="checkpoint">检查点</option>
                    </select>
                  </div>
                  <textarea v-model="node.description" rows="2" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs resize-none"></textarea>
                  <div class="flex flex-wrap gap-2">
                    <button @click="addResource(node, 'bilibili')" class="inline-flex items-center gap-1 px-2 py-1 rounded bg-blue-50 text-blue-700 text-[10px]">
                      <PlaySquare class="w-3 h-3" />
                      <span>BV</span>
                    </button>
                    <button @click="addResource(node, 'file')" class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 text-gray-600 text-[10px]">
                      <FileText class="w-3 h-3" />
                      <span>文档</span>
                    </button>
                    <button @click="addResource(node, 'link')" class="inline-flex items-center gap-1 px-2 py-1 rounded bg-gray-100 text-gray-600 text-[10px]">
                      <Link class="w-3 h-3" />
                      <span>链接</span>
                    </button>
                    <button @click="removeNode(index)" class="ml-auto px-2 py-1 rounded text-red-500 text-[10px]">删除</button>
                  </div>
                  <div v-if="node.resources.length" class="space-y-2">
                    <div v-for="(res, rIdx) in node.resources" :key="rIdx" class="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <input v-model="res.title" class="px-2 py-1.5 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-[10px]" placeholder="资源标题" />
                      <input v-if="res.resource_type === 'bilibili'" v-model="res.bv_id" class="px-2 py-1.5 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-[10px]" placeholder="BV号" />
                      <input v-else v-model="res.url" class="px-2 py-1.5 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-[10px]" placeholder="链接/文件说明" />
                      <button @click="node.resources.splice(rIdx, 1)" class="text-left text-[10px] text-red-500">移除资源</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="sticky bottom-0 bg-white dark:bg-zinc-900 pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-end gap-3">
          <button @click="createPanelOpen = false" class="px-4 py-2 rounded border border-gray-200 dark:border-zinc-800 text-xs">取消</button>
          <button
            @click="handleCreatePath"
            :disabled="saving"
            class="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs font-medium disabled:opacity-50"
          >
            <Send class="w-3.5 h-3.5" />
            <span>{{ saving ? '保存中' : '发布任务' }}</span>
          </button>
        </div>
      </div>
    </el-drawer>

    <el-dialog v-model="reviewDialogVisible" title="批改学习节点提交" width="460px">
      <div v-if="selectedSubmission" class="space-y-4">
        <div class="p-3 rounded border border-gray-100 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 text-xs text-gray-600 dark:text-zinc-300 whitespace-pre-wrap">
          {{ selectedSubmission.content || '无文本说明' }}
        </div>
        <div class="grid grid-cols-2 gap-3">
          <label class="space-y-1">
            <span class="text-xs text-gray-500">结论</span>
            <select v-model="reviewForm.review_status" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-xs">
              <option value="approved">通过</option>
              <option value="revise">二次开放</option>
              <option value="rejected">退回</option>
            </select>
          </label>
          <label class="space-y-1">
            <span class="text-xs text-gray-500">分数</span>
            <input v-model.number="reviewForm.score" type="number" min="0" max="100" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" />
          </label>
        </div>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">评语</span>
          <textarea v-model="reviewForm.feedback" rows="3" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs resize-none"></textarea>
        </label>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">追评/二次开放说明</span>
          <textarea v-model="reviewForm.follow_up" rows="2" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs resize-none"></textarea>
        </label>
      </div>
      <template #footer>
        <button @click="reviewDialogVisible = false" class="px-4 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs mr-2">取消</button>
        <button @click="saveReview" class="inline-flex items-center gap-1.5 px-4 py-1.5 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs">
          <Save class="w-3.5 h-3.5" />
          <span>保存</span>
        </button>
      </template>
    </el-dialog>
  </div>
</template>
