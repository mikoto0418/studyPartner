<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Bot,
  CheckCircle2,
  FileArchive,
  FileText,
  Globe2,
  Link,
  Loader2,
  Paperclip,
  PlaySquare,
  Plus,
  Send,
  Trash2,
  UploadCloud,
  Users
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { learningPathApi } from '../../api/modules/learning_path'
import { knowledgeApi, type FileOut } from '../../api/modules/knowledge'
import type { ClassOut, LearningPathNode, LearningPathPlanOut } from '../../api/modules/learning_path'
import type { UserOut } from '../../api/modules/user'
import StudentPickerDialog from '../../components/common/StudentPickerDialog.vue'

const router = useRouter()

const classes = ref<ClassOut[]>([])
const loadingClasses = ref(false)
const generating = ref(false)
const saving = ref(false)
const uploadingNodeKey = ref('')
const assigneePickerVisible = ref(false)
const selectedAssigneeUsers = ref<UserOut[]>([])

const pathForm = ref({
  title: '',
  goal: '',
  planning_text: '',
  class_id: '',
  assignee_ids: [] as string[],
  due_date: '',
  enable_web_research: true,
  publish: true
})

const generatedPlan = ref<LearningPathPlanOut | null>(null)

const selectedClass = computed(() => classes.value.find(item => item.id === pathForm.value.class_id))
const totalMinutes = computed(() => generatedPlan.value?.nodes.reduce((sum, node) => sum + (node.estimated_minutes || 0), 0) || 0)
const selectedAssigneeNames = computed(() => selectedAssigneeUsers.value.map(displayNameOf).join('、'))

function displayNameOf(item: { display_name?: string; nickname?: string; username?: string }) {
  return item.display_name || item.nickname?.trim() || item.username || '未设置姓名'
}

function fileSizeText(size?: number) {
  if (!size) return ''
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function nodeTypeText(type: string) {
  return ({
    learning: '学习',
    video: '视频',
    reading: '阅读',
    practice: '练习',
    submission: '提交',
    checkpoint: '检查点'
  } as Record<string, string>)[type] || type
}

async function loadClasses() {
  loadingClasses.value = true
  try {
    const res = await learningPathApi.listClasses()
    classes.value = res.data || []
  } catch (error) {
    console.warn('Failed to load classes', error)
  } finally {
    loadingClasses.value = false
  }
}

function handleAssigneesConfirm(users: UserOut[]) {
  selectedAssigneeUsers.value = users
}

async function handleGeneratePlan() {
  if (!pathForm.value.goal.trim() || !pathForm.value.planning_text.trim()) {
    ElMessage.warning('请先输入学习目标和粗略规划')
    return
  }
  generating.value = true
  try {
    const res = await learningPathApi.generatePlan({
      title: pathForm.value.title || undefined,
      goal: pathForm.value.goal,
      planning_text: pathForm.value.planning_text,
      enable_web_research: pathForm.value.enable_web_research
    })
    generatedPlan.value = normalizePlan(res.data)
    if (!pathForm.value.title) pathForm.value.title = pathForm.value.goal
    ElMessage.success('学习路径草案已生成')
  } catch (error) {
    console.warn('Failed to generate learning path plan', error)
    ElMessage.error('学习路径生成失败，请检查模型配置或稍后重试')
  } finally {
    generating.value = false
  }
}

function normalizePlan(plan: LearningPathPlanOut): LearningPathPlanOut {
  return {
    ...plan,
    stages: plan.stages?.length ? plan.stages : [{ title: '学习路径', description: '教师确认后的路径结构。', order_index: 0 }],
    nodes: (plan.nodes || []).map((node, index) => ({
      ...node,
      key: node.key || `node_${index + 1}`,
      order_index: index,
      estimated_minutes: node.estimated_minutes || 45,
      required: node.required !== false,
      resources: node.resources || [],
      config: node.config || { stage_order: 0 }
    })),
    edges: plan.edges || [],
    resources: plan.resources || [],
    summary: plan.summary || '已生成可执行学习路径。'
  }
}

function ensurePlan() {
  if (generatedPlan.value) return
  generatedPlan.value = {
    stages: [{ title: '学习路径', description: '教师手动创建的路径。', order_index: 0 }],
    nodes: [],
    edges: [],
    resources: [],
    summary: '教师手动创建路径'
  }
}

function addNode() {
  ensurePlan()
  const plan = generatedPlan.value!
  const nextIndex = plan.nodes.length
  const key = `node_${nextIndex + 1}`
  const prevNode = plan.nodes[nextIndex - 1]
  plan.nodes.push({
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
    plan.edges.push({ source_key: prevNode.key, target_key: key })
  }
}

function removeNode(index: number) {
  if (!generatedPlan.value) return
  generatedPlan.value.nodes.splice(index, 1)
  generatedPlan.value.nodes.forEach((node, idx) => {
    node.order_index = idx
    node.key = `node_${idx + 1}`
  })
  generatedPlan.value.edges = generatedPlan.value.nodes.slice(0, -1).map((node, idx) => ({
    source_key: node.key || `node_${idx + 1}`,
    target_key: generatedPlan.value!.nodes[idx + 1].key || `node_${idx + 2}`
  }))
}

function addResource(node: LearningPathNode, type: 'bilibili' | 'link') {
  node.resources.push({
    resource_type: type,
    title: type === 'bilibili' ? 'B站视频资源' : '外部链接',
    bv_id: type === 'bilibili' ? '' : undefined,
    url: type === 'link' ? '' : undefined
  })
}

async function handleResourceUpload(node: LearningPathNode, event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  if (!files.length) return
  const nodeKey = node.key || `node_${node.order_index + 1}`
  uploadingNodeKey.value = nodeKey
  try {
    for (const file of files) {
      const res = await knowledgeApi.uploadFile(file, 'learning_path_resource')
      const uploaded = res.data as FileOut
      node.resources.push({
        resource_type: 'file',
        title: uploaded.original_name,
        file_id: uploaded.id,
        metadata: {
          mime_type: uploaded.mime_type,
          file_size: uploaded.file_size,
          source: uploaded.source
        }
      })
    }
    ElMessage.success('辅佐文件已上传')
  } catch (error) {
    console.warn('Failed to upload learning path resource', error)
    ElMessage.error('辅佐文件上传失败')
  } finally {
    uploadingNodeKey.value = ''
    input.value = ''
  }
}

async function handleCreatePath() {
  if (!pathForm.value.title.trim() || !pathForm.value.goal.trim()) {
    ElMessage.warning('请填写标题和学习目标')
    return
  }
  if (!generatedPlan.value || generatedPlan.value.nodes.length === 0) {
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
      due_date: pathForm.value.due_date ? new Date(`${pathForm.value.due_date}T23:59:00`).toISOString() : undefined,
      publish: pathForm.value.publish,
      stages: generatedPlan.value.stages,
      nodes: generatedPlan.value.nodes,
      edges: generatedPlan.value.edges
    })
    ElMessage.success('学习路径任务已发布')
    router.push({ name: 'TeacherLearningPaths', query: { taskId: res.data.id } })
  } catch (error) {
    console.warn('Failed to create learning path', error)
    ElMessage.error('保存学习路径失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadClasses)
</script>

<template>
  <div class="-m-4 min-h-[calc(100vh-5rem)] bg-gray-50/70 p-5 dark:bg-zinc-950">
    <div class="mx-auto flex max-w-7xl flex-col gap-5">
      <div class="flex flex-col gap-4 border-b border-gray-200/70 pb-5 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
        <div>
          <button
            type="button"
            @click="router.push({ name: 'TeacherLearningPaths' })"
            class="mb-3 inline-flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-blue-600"
          >
            <ArrowLeft class="h-4 w-4" />
            <span>返回学习路径任务</span>
          </button>
          <h1 class="text-xl font-bold text-gray-950 dark:text-zinc-50">布置学习路径任务</h1>
          <p class="mt-1 text-xs text-gray-500 dark:text-zinc-400">把目标、资料和提交要求拆成学生可逐步完成的路径。</p>
        </div>
        <div class="flex items-center gap-3">
          <label class="inline-flex items-center gap-2 rounded border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
            <input v-model="pathForm.publish" type="checkbox" class="h-3.5 w-3.5 accent-blue-600" />
            <CheckCircle2 class="h-4 w-4 text-blue-600" />
            <span>{{ pathForm.publish ? '发布给学生' : '保存为草稿' }}</span>
          </label>
          <button
            type="button"
            @click="handleCreatePath"
            :disabled="saving"
            class="inline-flex items-center gap-2 rounded bg-gray-950 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-950"
          >
            <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
            <Send v-else class="h-4 w-4" />
            <span>{{ saving ? '保存中' : '发布任务' }}</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-1 gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside class="minimal-card bg-white p-5 dark:bg-zinc-900">
          <h2 class="text-sm font-semibold text-gray-950 dark:text-zinc-50">任务信息</h2>
          <div class="mt-5 space-y-4">
            <label class="block space-y-1.5">
              <span class="text-xs text-gray-500">任务标题</span>
              <input v-model="pathForm.title" class="w-full rounded border border-gray-200 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="例如：Vibe Coding 入门" />
            </label>
            <label class="block space-y-1.5">
              <span class="text-xs text-gray-500">截止日期</span>
              <input v-model="pathForm.due_date" type="date" class="w-full rounded border border-gray-200 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800" />
            </label>
            <label class="block space-y-1.5">
              <span class="text-xs text-gray-500">学习目标</span>
              <textarea v-model="pathForm.goal" rows="3" class="w-full resize-none rounded border border-gray-200 bg-transparent px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="学生最终要能完成什么？"></textarea>
            </label>
            <label class="block space-y-1.5">
              <span class="text-xs text-gray-500">粗略规划</span>
              <textarea v-model="pathForm.planning_text" rows="7" class="w-full resize-none rounded border border-gray-200 bg-transparent px-3 py-2 text-sm leading-relaxed outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="输入已有资料、目标层级、希望学生提交的产物。"></textarea>
            </label>

            <div class="grid grid-cols-1 gap-3">
              <label class="space-y-1.5">
                <span class="text-xs text-gray-500">发布班级</span>
                <select v-model="pathForm.class_id" :disabled="loadingClasses" class="w-full rounded border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900">
                  <option value="">不选择班级</option>
                  <option v-for="item in classes" :key="item.id" :value="item.id">{{ item.name }}（{{ item.member_count }}人）</option>
                </select>
              </label>
              <label class="space-y-1.5">
                <span class="text-xs text-gray-500">单独指派学生</span>
                <button
                  type="button"
                  @click="assigneePickerVisible = true"
                  class="flex min-h-10 w-full items-center justify-between gap-3 rounded border border-gray-200 px-3 py-2 text-left text-sm dark:border-zinc-800"
                >
                  <span class="min-w-0 truncate text-gray-700 dark:text-zinc-300">
                    {{ pathForm.assignee_ids.length ? selectedAssigneeNames : '选择学生' }}
                  </span>
                  <span class="shrink-0 rounded bg-blue-50 px-2 py-1 text-[10px] text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                    {{ pathForm.assignee_ids.length }} 人
                  </span>
                </button>
              </label>
            </div>

            <div v-if="selectedClass" class="flex items-center gap-2 rounded border border-blue-100 bg-blue-50/70 px-3 py-2 text-xs text-blue-700 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-300">
              <Users class="h-4 w-4" />
              <span>将自动分配给 {{ selectedClass.member_count }} 名班级学生。</span>
            </div>

            <button
              type="button"
              @click="handleGeneratePlan"
              :disabled="generating"
              class="flex w-full items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              <Loader2 v-if="generating" class="h-4 w-4 animate-spin" />
              <Bot v-else class="h-4 w-4" />
              <span>{{ generating ? 'AI 正在生成路径' : 'AI 生成路径' }}</span>
            </button>

            <label class="flex items-center justify-between rounded border border-gray-200 px-3 py-2 text-xs dark:border-zinc-800">
              <span class="inline-flex items-center gap-2 text-gray-600 dark:text-zinc-300">
                <Globe2 class="h-4 w-4 text-blue-600" />
                联网增强
              </span>
              <input v-model="pathForm.enable_web_research" type="checkbox" class="h-4 w-4 accent-blue-600" />
            </label>
          </div>
        </aside>

        <main class="minimal-card min-h-[720px] bg-white p-5 dark:bg-zinc-900">
          <div class="flex flex-col gap-3 border-b border-gray-100 pb-4 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 class="text-sm font-semibold text-gray-950 dark:text-zinc-50">路径草案微调</h2>
              <p class="mt-1 text-xs text-gray-400">
                {{ generatedPlan ? `${generatedPlan.nodes.length} 步，约 ${totalMinutes} 分钟` : '先生成路径，或手动添加步骤。' }}
              </p>
            </div>
            <button
              type="button"
              @click="addNode"
              class="inline-flex items-center gap-2 rounded border border-gray-200 px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800"
            >
              <Plus class="h-4 w-4" />
              <span>添加步骤</span>
            </button>
          </div>

          <div v-if="generatedPlan" class="mt-5 space-y-4">
            <div class="rounded border border-blue-100 bg-blue-50/50 px-4 py-3 text-xs leading-relaxed text-blue-800 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-200">
              {{ generatedPlan.summary }}
            </div>

            <div
              v-for="(node, index) in generatedPlan.nodes"
              :key="node.key || index"
              class="rounded-lg border border-gray-100 bg-gray-50/40 p-4 dark:border-zinc-800 dark:bg-zinc-950/30"
            >
              <div class="flex items-start gap-4">
                <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded bg-blue-50 text-sm font-bold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                  {{ index + 1 }}
                </div>
                <div class="min-w-0 flex-1 space-y-3">
                  <div class="grid grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_160px_120px]">
                    <input v-model="node.title" class="rounded border border-gray-200 bg-white px-3 py-2 text-sm font-medium outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900" />
                    <select v-model="node.node_type" class="rounded border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900">
                      <option value="learning">学习</option>
                      <option value="video">视频</option>
                      <option value="reading">阅读</option>
                      <option value="practice">练习</option>
                      <option value="submission">提交</option>
                      <option value="checkpoint">检查点</option>
                    </select>
                    <input v-model.number="node.estimated_minutes" type="number" min="5" class="rounded border border-gray-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900" />
                  </div>
                  <textarea v-model="node.description" rows="3" class="w-full resize-none rounded border border-gray-200 bg-white px-3 py-2 text-sm leading-relaxed outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900" placeholder="这一步要做什么、产出什么、通过标准是什么。"></textarea>

                  <div class="flex flex-wrap items-center gap-2">
                    <button type="button" @click="addResource(node, 'bilibili')" class="inline-flex items-center gap-1.5 rounded bg-blue-50 px-2.5 py-1.5 text-[11px] font-medium text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                      <PlaySquare class="h-3.5 w-3.5" />
                      BV
                    </button>
                    <button type="button" @click="addResource(node, 'link')" class="inline-flex items-center gap-1.5 rounded bg-gray-100 px-2.5 py-1.5 text-[11px] font-medium text-gray-600 dark:bg-zinc-800 dark:text-zinc-300">
                      <Link class="h-3.5 w-3.5" />
                      链接
                    </button>
                    <label class="inline-flex cursor-pointer items-center gap-1.5 rounded bg-gray-100 px-2.5 py-1.5 text-[11px] font-medium text-gray-600 dark:bg-zinc-800 dark:text-zinc-300">
                      <Loader2 v-if="uploadingNodeKey === (node.key || `node_${node.order_index + 1}`)" class="h-3.5 w-3.5 animate-spin" />
                      <Paperclip v-else class="h-3.5 w-3.5" />
                      附件
                      <input type="file" multiple class="hidden" @change="handleResourceUpload(node, $event)" />
                    </label>
                    <span class="text-[11px] text-gray-400">{{ nodeTypeText(node.node_type) }} · {{ node.estimated_minutes || 0 }} 分钟</span>
                    <button type="button" @click="removeNode(index)" class="ml-auto inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20">
                      <Trash2 class="h-3.5 w-3.5" />
                      删除
                    </button>
                  </div>

                  <div v-if="node.resources.length" class="space-y-2 rounded border border-gray-100 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
                    <div
                      v-for="(res, rIdx) in node.resources"
                      :key="`${res.resource_type}-${rIdx}`"
                      class="grid grid-cols-1 gap-2 lg:grid-cols-[180px_minmax(0,1fr)_76px]"
                    >
                      <input v-model="res.title" class="rounded border border-gray-200 bg-transparent px-2 py-1.5 text-xs outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="资源标题" />
                      <input v-if="res.resource_type === 'bilibili'" v-model="res.bv_id" class="rounded border border-gray-200 bg-transparent px-2 py-1.5 text-xs outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="BV 号" />
                      <input v-else-if="res.resource_type === 'link'" v-model="res.url" class="rounded border border-gray-200 bg-transparent px-2 py-1.5 text-xs outline-none focus:border-blue-500 dark:border-zinc-800" placeholder="https://..." />
                      <div v-else class="flex min-w-0 items-center gap-2 rounded border border-gray-200 px-2 py-1.5 text-xs text-gray-500 dark:border-zinc-800">
                        <FileArchive v-if="res.metadata?.mime_type?.includes('zip')" class="h-3.5 w-3.5 shrink-0 text-blue-600" />
                        <FileText v-else class="h-3.5 w-3.5 shrink-0 text-blue-600" />
                        <span class="truncate">{{ res.title || '已上传文件' }}</span>
                        <span class="shrink-0 text-gray-400">{{ fileSizeText(res.metadata?.file_size) }}</span>
                      </div>
                      <button type="button" @click="node.resources.splice(rIdx, 1)" class="rounded px-2 py-1 text-left text-[11px] text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20">移除</button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else class="flex min-h-[520px] flex-col items-center justify-center text-center text-gray-400">
            <UploadCloud class="mb-3 h-10 w-10 text-gray-300" />
            <p class="text-sm font-semibold text-gray-600 dark:text-zinc-300">还没有路径草案</p>
            <p class="mt-1 text-xs">点击左侧 AI 生成路径，或手动添加第一步。</p>
          </div>
        </main>
      </div>
    </div>

    <StudentPickerDialog
      v-model:visible="assigneePickerVisible"
      v-model="pathForm.assignee_ids"
      title="选择单独指派学生"
      @confirm="handleAssigneesConfirm"
    />
  </div>
</template>
