<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus, CheckCircle, Clock, AlertCircle, Eye, User } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { taskApi } from '../../api/modules/task'
import type { TaskOut, TaskDetails } from '../../api/modules/task'
import { userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'

// Data lists
const tasks = ref<TaskOut[]>([])
const students = ref<UserOut[]>([])

// Loading states
const loading = ref(false)

// Dialog visibilities
const createDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const reviewDialogVisible = ref(false)

// Form states
const taskForm = ref({
  title: '',
  description: '',
  priority: 'medium',
  due_date: '',
  assignee_ids: [] as string[]
})

const selectedTaskDetails = ref<TaskDetails | null>(null)
const selectedSubmission = ref<{
  id: string
  user_id: string
  nickname?: string
  username: string
  content?: string
  created_at: string
} | null>(null)

const reviewForm = ref({
  status: 'completed' as 'completed' | 'rejected',
  feedback: ''
})

const displayNameOf = (item: { display_name?: string; nickname?: string; username?: string }) => item.display_name || item.nickname?.trim() || '未设置姓名'
const optionLabelOf = (item: { display_name?: string; nickname?: string; username?: string }) => {
  const displayName = displayNameOf(item)
  return item.username ? `${displayName}（账号：${item.username}）` : displayName
}

// Fetch initial data
const loadTasks = async () => {
  loading.value = true
  try {
    const res = await taskApi.listTeacherTasks()
    tasks.value = res.data || []
  } catch (error) {
    console.warn('Failed to fetch teacher tasks', error)
    tasks.value = []
  } finally {
    loading.value = false
  }
}

const loadStudents = async () => {
  try {
    const res = await userApi.listUsers({ role_code: 'student', page_size: 100 })
    students.value = res.data?.items || []
  } catch (error) {
    console.warn('Failed to fetch students', error)
    students.value = []
  }
}

// Add task
const handleCreateTask = async () => {
  if (!taskForm.value.title.trim()) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (taskForm.value.assignee_ids.length === 0) {
    ElMessage.warning('请选择至少一个指派学生')
    return
  }

  try {
    const payload = {
      title: taskForm.value.title,
      description: taskForm.value.description || undefined,
      priority: taskForm.value.priority,
      due_date: taskForm.value.due_date ? new Date(taskForm.value.due_date).toISOString() : undefined,
      assignee_ids: taskForm.value.assignee_ids
    }
    const res = await taskApi.createTask(payload)
    tasks.value.unshift(res.data)
    createDialogVisible.value = false
    ElMessage.success('任务发布成功')
    
    // Reset form
    taskForm.value = {
      title: '',
      description: '',
      priority: 'medium',
      due_date: '',
      assignee_ids: []
    }
  } catch (error) {
    console.warn('Failed to create task', error)
    ElMessage.error('任务发布失败')
  }
}

// Show task details and submissions
const handleViewTaskDetails = async (task: TaskOut) => {
  try {
    const res = await taskApi.getTaskDetails(task.id)
    selectedTaskDetails.value = res.data
  } catch (error) {
    console.warn('Failed to get task details', error)
    ElMessage.error('加载任务详情失败')
    return
  }
  detailDrawerVisible.value = true
}

// Start reviewing a submission
const handleStartReview = (sub: any) => {
  selectedSubmission.value = sub
  reviewForm.value = {
    status: 'completed',
    feedback: ''
  }
  reviewDialogVisible.value = true
}

// Submit review
const handleSaveReview = async () => {
  if (!selectedSubmission.value || !selectedTaskDetails.value) return

  try {
    await taskApi.reviewSubmission(selectedSubmission.value.id, {
      status: reviewForm.value.status,
      feedback: reviewForm.value.feedback || undefined
    })
    
    // Update local assignee list
    const assignee = selectedTaskDetails.value.assignees.find(
      a => a.user_id === selectedSubmission.value?.user_id
    )
    if (assignee) {
      assignee.status = reviewForm.value.status
      if (reviewForm.value.status === 'completed') {
        assignee.completed_at = new Date().toISOString()
      }
    }
    
    reviewDialogVisible.value = false
    ElMessage.success('审核评阅成功')
  } catch (error) {
    console.warn('Failed to save review', error)
    ElMessage.error('审核保存失败')
  }
}

// Helpers
const formatDate = (isoStr?: string) => {
  if (!isoStr) return '--'
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadTasks()
  loadStudents()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex justify-between items-center">
      <div>
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">教学任务管理</h3>
        <p class="text-xs text-gray-400 dark:text-zinc-500 mt-1">创建和监控下发学生的教学指导任务</p>
      </div>

      <button
        @click="createDialogVisible = true"
        class="flex items-center space-x-1.5 py-1.5 px-3 bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-xs rounded transition-colors"
      >
        <Plus class="w-4 h-4" />
        <span>发布教学任务</span>
      </button>
    </div>

    <!-- Tasks Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" v-loading="loading">
      <div
        v-for="task in tasks"
        :key="task.id"
        class="minimal-card p-6 flex flex-col justify-between hover:border-gray-300 dark:hover:border-zinc-700 transition-all cursor-pointer"
        @click="handleViewTaskDetails(task)"
      >
        <div class="space-y-3">
          <div class="flex justify-between items-start">
            <span
              class="text-[9px] px-1.5 py-0.5 rounded font-medium"
              :class="{
                'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400': task.priority === 'urgent',
                'bg-amber-50 text-amber-600 dark:bg-amber-950/20 dark:text-amber-400': task.priority === 'high',
                'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400': task.priority === 'medium',
                'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400': task.priority === 'low'
              }"
            >
              {{ task.priority === 'urgent' ? '紧急' : task.priority === 'high' ? '高' : task.priority === 'medium' ? '中' : '低' }}
            </span>

            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium">
              截止日: {{ formatDate(task.due_date) }}
            </span>
          </div>

          <h4 class="text-xs font-semibold text-gray-900 dark:text-zinc-50 leading-snug line-clamp-1">
            {{ task.title }}
          </h4>

          <p class="text-[11px] text-gray-400 dark:text-zinc-500 leading-relaxed line-clamp-2 h-8">
            {{ task.description || '无任务描述' }}
          </p>
        </div>

        <div class="mt-4 pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-between items-center text-[10px] text-gray-400 dark:text-zinc-500">
          <div class="flex items-center space-x-1">
            <Clock class="w-3.5 h-3.5" />
            <span>发布于: {{ formatDate(task.created_at) }}</span>
          </div>
          
          <span class="text-blue-600 dark:text-blue-500 hover:underline flex items-center space-x-0.5">
            <span>管理状态</span>
            <Eye class="w-3 h-3 ml-0.5" />
          </span>
        </div>
      </div>

      <div
        v-if="tasks.length === 0"
        class="col-span-full py-16 text-center text-xs text-gray-400 dark:text-zinc-500"
      >
        暂无发布的任务，请点击右上角发布新任务。
      </div>
    </div>

    <!-- Create Dialog -->
    <el-dialog
      v-model="createDialogVisible"
      title="发布新教学任务"
      width="500px"
      class="minimal-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">任务标题</label>
          <input
            v-model="taskForm.title"
            placeholder="例如：文献阅读汇报、大纲审核等"
            type="text"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
          />
        </div>

        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">任务详情</label>
          <textarea
            v-model="taskForm.description"
            placeholder="任务内容说明、具体研究要求..."
            rows="3"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors resize-none"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">优先级</label>
            <select
              v-model="taskForm.priority"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-white dark:bg-zinc-900 focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            >
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="urgent">紧急</option>
            </select>
          </div>

          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">截止日期</label>
            <input
              type="date"
              v-model="taskForm.due_date"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            />
          </div>
        </div>

        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">指派学生（多选）</label>
          <el-select
            v-model="taskForm.assignee_ids"
            multiple
            placeholder="选择接收此任务的学生"
            class="w-full minimal-select"
          >
            <el-option
              v-for="s in students"
              :key="s.id"
              :label="optionLabelOf(s)"
              :value="s.id"
            />
          </el-select>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3 pt-2">
          <button
            @click="createDialogVisible = false"
            class="px-4 py-1.5 text-xs border border-gray-200 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            取消
          </button>
          <button
            @click="handleCreateTask"
            class="px-4 py-1.5 text-xs bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium rounded transition-colors"
          >
            发布
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Details Drawer / Side Panel -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="教学任务跟进详情"
      size="480px"
      destroy-on-close
    >
      <div v-if="selectedTaskDetails" class="space-y-6">
        <!-- Task info header -->
        <div class="space-y-2">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">
            {{ selectedTaskDetails.task.title }}
          </h3>
          <p class="text-xs text-gray-500 whitespace-pre-wrap leading-relaxed">
            {{ selectedTaskDetails.task.description || '无任务详情描述' }}
          </p>
        </div>

        <!-- Student execution status -->
        <div class="space-y-3">
          <h4 class="text-xs font-semibold text-gray-400 dark:text-zinc-500">指派学生进度</h4>
          <div class="space-y-2 max-h-60 overflow-y-auto">
            <div
              v-for="item in selectedTaskDetails.assignees"
              :key="item.id"
              class="flex justify-between items-center p-3 border border-gray-100 dark:border-zinc-800 rounded bg-gray-50/50 dark:bg-zinc-900/50"
            >
              <div class="flex items-center space-x-2">
                <User class="w-4 h-4 text-gray-400" />
                <span class="text-xs font-medium text-gray-700 dark:text-zinc-300">{{ displayNameOf(item) }}</span>
                <span class="text-[9px] text-gray-400 font-mono">账号：{{ item.username }}</span>
              </div>
              
              <div class="flex items-center space-x-2">
                <!-- Status badges -->
                <span
                  class="text-[9px] px-1.5 py-0.5 rounded font-medium flex items-center space-x-1"
                  :class="{
                    'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400': item.status === 'in_progress' || item.status === 'not_started',
                    'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400': item.status === 'submitted',
                    'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-400': item.status === 'completed',
                    'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400': item.status === 'rejected'
                  }"
                >
                  <CheckCircle v-if="item.status === 'completed'" class="w-3 h-3 mr-0.5 text-emerald-600" />
                  <Clock v-else-if="item.status === 'in_progress'" class="w-3 h-3 mr-0.5 text-zinc-500" />
                  <AlertCircle v-else-if="item.status === 'submitted'" class="w-3 h-3 mr-0.5 text-blue-500" />
                  <span>
                    {{ item.status === 'completed' ? '已完成' : item.status === 'submitted' ? '待评阅' : item.status === 'rejected' ? '被退回' : '进行中' }}
                  </span>
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- Student Submissions -->
        <div class="space-y-3 pt-4 border-t border-gray-100 dark:border-zinc-800">
          <h4 class="text-xs font-semibold text-gray-400 dark:text-zinc-500">学生作业提交记录</h4>
          <div class="space-y-3">
            <div
              v-for="sub in selectedTaskDetails.submissions"
              :key="sub.id"
              class="p-4 border border-gray-200 dark:border-zinc-800 rounded space-y-2 bg-white dark:bg-zinc-900"
            >
              <div class="flex justify-between items-center text-[10px] text-gray-400">
                <span class="font-medium text-gray-700 dark:text-zinc-300">
                  提交人: {{ displayNameOf(sub) }} · 账号：{{ sub.username }}
                </span>
                <span>{{ formatDate(sub.created_at) }}</span>
              </div>
              <p class="text-xs text-gray-600 dark:text-zinc-300 whitespace-pre-wrap py-1">
                {{ sub.content }}
              </p>
              
              <!-- Review stats / action -->
              <div class="pt-2 flex justify-between items-center text-[10px] border-t border-gray-50 dark:border-zinc-800/50">
                <div v-if="sub.reviewed_by" class="text-gray-400">
                  <span>评阅反馈: </span>
                  <span class="text-gray-700 dark:text-zinc-300 font-medium">{{ sub.feedback || '无评语' }}</span>
                </div>
                
                <button
                  v-else
                  @click="handleStartReview(sub)"
                  class="py-1 px-2.5 bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-[9px] rounded transition-colors ml-auto"
                >
                  批改评阅
                </button>
              </div>
            </div>

            <div
              v-if="selectedTaskDetails.submissions.length === 0"
              class="py-8 text-center text-xs text-gray-400"
            >
              目前尚无任何学生提交答案。
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Review Submission Dialog -->
    <el-dialog
      v-model="reviewDialogVisible"
      title="批改学生作业"
      width="400px"
      class="minimal-dialog"
    >
      <div v-if="selectedSubmission" class="space-y-4">
        <div>
          <span class="text-[10px] text-gray-400 block mb-1">学生回答</span>
          <div class="p-3 bg-gray-50 dark:bg-zinc-900 text-xs text-gray-700 dark:text-zinc-300 border border-gray-100 dark:border-zinc-800 rounded">
            {{ selectedSubmission.content }}
          </div>
        </div>

        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">审核结论</label>
          <select
            v-model="reviewForm.status"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-white dark:bg-zinc-900 focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
          >
            <option value="completed">通过 (合格/已完成)</option>
            <option value="rejected">退回重做</option>
          </select>
        </div>

        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">教师评语 / 反馈建议</label>
          <textarea
            v-model="reviewForm.feedback"
            placeholder="写下具体的反馈或评语，学生会在通知中收到提示..."
            rows="3"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors resize-none"
          ></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3 pt-2">
          <button
            @click="reviewDialogVisible = false"
            class="px-4 py-1.5 text-xs border border-gray-200 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            取消
          </button>
          <button
            @click="handleSaveReview"
            class="px-4 py-1.5 text-xs bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium rounded transition-colors"
          >
            确认提交
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.minimal-select :deep(.el-input__wrapper) {
  background-color: transparent !important;
  border: 1px solid #e4e4e7 !important;
  box-shadow: none !important;
  border-radius: 4px;
}
.dark .minimal-select :deep(.el-input__wrapper) {
  border-color: #27272a !important;
}
.minimal-select :deep(.el-input__wrapper):hover,
.minimal-select :deep(.el-input__wrapper).is-focus {
  border-color: #18181b !important;
}
.dark .minimal-select :deep(.el-input__wrapper):hover,
.dark .minimal-select :deep(.el-input__wrapper).is-focus {
  border-color: #f4f4f5 !important;
}
</style>
