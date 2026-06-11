<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  CheckCircle2,
  Clock3,
  FileText,
  GitBranch,
  GraduationCap,
  Link,
  Loader2,
  Lock,
  MessageSquareText,
  Paperclip,
  PlaySquare,
  RefreshCw,
  UploadCloud,
  UserCircle
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { learningPathApi } from '../../api/modules/learning_path'
import { knowledgeApi } from '../../api/modules/knowledge'
import type { LearningPathNode, LearningPathStudentProgressOut } from '../../api/modules/learning_path'

const route = useRoute()
const router = useRouter()

const detail = ref<LearningPathStudentProgressOut | null>(null)
const loading = ref(false)

const taskId = computed(() => String(route.params.taskId || ''))
const studentId = computed(() => String(route.params.studentId || ''))
const nodes = computed(() => detail.value?.nodes || [])
const submissions = computed(() => detail.value?.submissions || [])
const completedCount = computed(() => nodes.value.filter(node => node.progress?.status === 'completed').length)
const submittedCount = computed(() => nodes.value.filter(node => ['submitted', 'completed', 'reopened'].includes(node.progress?.status || '')).length)
const totalMinutes = computed(() => nodes.value.reduce((sum, node) => sum + (node.estimated_minutes || 0), 0))

function displayNameOf(item?: Record<string, any> | null) {
  return item?.display_name || item?.nickname?.trim() || item?.username || '未设置姓名'
}

function formatDate(iso?: string) {
  if (!iso) return '未设置'
  const date = new Date(iso)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function formatDateTime(iso?: string) {
  if (!iso) return '未记录'
  const date = new Date(iso)
  return `${formatDate(iso)} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function statusText(status?: string) {
  return ({
    not_started: '未开始',
    in_progress: '进行中',
    completed: '已完成',
    available: '可开始',
    locked: '锁定',
    submitted: '已提交',
    reopened: '需重做',
    pending: '待批改',
    approved: '已通过',
    rejected: '已退回',
    revise: '需修改'
  } as Record<string, string>)[status || ''] || status || '未开始'
}

function statusClass(status?: string) {
  if (status === 'completed' || status === 'approved') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300'
  if (status === 'submitted' || status === 'pending') return 'bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300'
  if (status === 'reopened' || status === 'revise' || status === 'rejected') return 'bg-amber-50 text-amber-700 dark:bg-amber-950/20 dark:text-amber-300'
  if (status === 'locked') return 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'
  return 'bg-gray-50 text-gray-600 dark:bg-zinc-800 dark:text-zinc-300'
}

function nodeIcon(nodeType: string) {
  if (nodeType === 'video') return PlaySquare
  if (nodeType === 'reading') return FileText
  if (nodeType === 'practice') return GraduationCap
  if (nodeType === 'submission') return UploadCloud
  if (nodeType === 'checkpoint') return CheckCircle2
  return GraduationCap
}

function nodeSubmissions(node: LearningPathNode) {
  return submissions.value.filter(item => item.node_id === node.id)
}

async function loadProgress() {
  if (!taskId.value || !studentId.value) return
  loading.value = true
  try {
    const res = await learningPathApi.getStudentProgress(taskId.value, studentId.value)
    detail.value = res.data
  } catch (error) {
    console.warn('Failed to load student path progress', error)
    ElMessage.error('获取学生路径进度失败')
  } finally {
    loading.value = false
  }
}

async function openResource(resource: Record<string, any>) {
  try {
    if (resource.file_id) {
      const res = await knowledgeApi.getFileDownloadUrl(resource.file_id)
      if (res.data?.url) window.open(res.data.url, '_blank')
      return
    }
    const url = resource.url || (resource.bv_id ? `https://www.bilibili.com/video/${resource.bv_id}` : '')
    if (url) window.open(url, '_blank')
  } catch (error) {
    console.warn('Failed to open resource', error)
    ElMessage.error('打开资源失败')
  }
}

async function downloadAttachment(fileId: string) {
  try {
    const res = await knowledgeApi.getFileDownloadUrl(fileId)
    if (res.data?.url) window.open(res.data.url, '_blank')
  } catch (error) {
    console.warn('Failed to download attachment', error)
    ElMessage.error('附件下载失败')
  }
}

function goBack() {
  router.push({ name: 'TeacherLearningPaths', query: { taskId: taskId.value } })
}

onMounted(loadProgress)
</script>

<template>
  <div class="-m-4 min-h-[calc(100vh-5rem)] bg-gray-50/70 p-5 dark:bg-zinc-950">
    <div class="mx-auto max-w-7xl space-y-5" v-loading="loading">
      <div class="flex flex-col gap-4 border-b border-gray-200/70 pb-5 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
        <div>
          <button
            type="button"
            @click="goBack"
            class="mb-3 inline-flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-blue-600"
          >
            <ArrowLeft class="h-4 w-4" />
            <span>返回路径任务</span>
          </button>
          <div class="flex items-center gap-2">
            <GitBranch class="h-5 w-5 text-blue-600" />
            <h1 class="text-xl font-bold text-gray-950 dark:text-zinc-50">{{ detail?.task.title || '学生路径进度' }}</h1>
          </div>
          <p class="mt-1 max-w-3xl text-xs leading-relaxed text-gray-500 dark:text-zinc-400">{{ detail?.task.goal }}</p>
        </div>
        <button
          type="button"
          @click="loadProgress"
          class="inline-flex items-center gap-2 rounded border border-gray-200 bg-white px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300"
        >
          <RefreshCw class="h-4 w-4" />
          <span>刷新</span>
        </button>
      </div>

      <div v-if="detail" class="grid grid-cols-1 gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside class="space-y-5">
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <div class="flex items-center gap-3">
              <div class="flex h-12 w-12 items-center justify-center rounded border border-gray-100 bg-gray-50 text-blue-600 dark:border-zinc-800 dark:bg-zinc-950">
                <UserCircle class="h-6 w-6" />
              </div>
              <div class="min-w-0">
                <h2 class="truncate text-sm font-semibold text-gray-950 dark:text-zinc-50">{{ displayNameOf(detail.student) }}</h2>
                <p class="mt-1 truncate text-[11px] text-gray-400">账号：{{ detail.student.username || '-' }}</p>
              </div>
            </div>
            <div class="mt-5 grid grid-cols-2 gap-3 text-xs">
              <div class="rounded bg-gray-50 p-3 dark:bg-zinc-950/60">
                <p class="text-[10px] text-gray-400">总体进度</p>
                <p class="mt-1 text-lg font-bold text-blue-600">{{ detail.assignee.progress_percent || 0 }}%</p>
              </div>
              <div class="rounded bg-gray-50 p-3 dark:bg-zinc-950/60">
                <p class="text-[10px] text-gray-400">节点完成</p>
                <p class="mt-1 text-lg font-bold text-gray-900 dark:text-zinc-50">{{ completedCount }}/{{ nodes.length }}</p>
              </div>
              <div class="rounded bg-gray-50 p-3 dark:bg-zinc-950/60">
                <p class="text-[10px] text-gray-400">提交节点</p>
                <p class="mt-1 text-lg font-bold text-gray-900 dark:text-zinc-50">{{ submittedCount }}</p>
              </div>
              <div class="rounded bg-gray-50 p-3 dark:bg-zinc-950/60">
                <p class="text-[10px] text-gray-400">总时长</p>
                <p class="mt-1 text-lg font-bold text-gray-900 dark:text-zinc-50">{{ totalMinutes }}</p>
              </div>
            </div>
            <div class="mt-4 space-y-2 text-[11px] text-gray-500 dark:text-zinc-400">
              <p>学号：{{ detail.student.student_profile?.student_id || '未填写' }}</p>
              <p>年级：{{ detail.student.student_profile?.grade || '未填写' }}</p>
              <p>专业：{{ detail.student.student_profile?.major || '未填写' }}</p>
              <p>截止：{{ formatDate(detail.task.due_date) }}</p>
            </div>
          </section>

          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="text-sm font-semibold text-gray-950 dark:text-zinc-50">提交概览</h3>
            <div class="mt-4 space-y-2">
              <div
                v-for="submission in submissions.slice(0, 5)"
                :key="submission.id"
                class="rounded border border-gray-100 p-3 dark:border-zinc-800"
              >
                <div class="flex items-center justify-between gap-2">
                  <span class="truncate text-xs font-medium text-gray-700 dark:text-zinc-200">{{ submission.node_title }}</span>
                  <span class="shrink-0 rounded px-2 py-0.5 text-[10px]" :class="statusClass(submission.review_status)">
                    {{ statusText(submission.review_status) }}
                  </span>
                </div>
                <p class="mt-1 text-[10px] text-gray-400">{{ formatDateTime(submission.created_at) }}</p>
              </div>
              <div v-if="submissions.length === 0" class="py-8 text-center text-xs text-gray-400">暂无提交记录。</div>
            </div>
          </section>
        </aside>

        <main class="space-y-5">
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <div class="flex items-center justify-between">
              <h3 class="text-sm font-semibold text-gray-950 dark:text-zinc-50">节点进度与提交情况</h3>
              <span class="text-xs text-gray-400">{{ nodes.length }} 个节点</span>
            </div>
            <div class="mt-5 space-y-4">
              <div
                v-for="(node, index) in nodes"
                :key="node.id"
                class="rounded-lg border border-gray-100 bg-gray-50/40 p-4 dark:border-zinc-800 dark:bg-zinc-950/30"
              >
                <div class="flex items-start gap-4">
                  <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded border bg-white text-blue-600 dark:border-zinc-800 dark:bg-zinc-900">
                    <Lock v-if="node.progress?.status === 'locked'" class="h-4 w-4 text-gray-400" />
                    <component v-else :is="nodeIcon(node.node_type)" class="h-4 w-4" />
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <h4 class="text-sm font-semibold text-gray-950 dark:text-zinc-50">{{ index + 1 }}. {{ node.title }}</h4>
                        <p class="mt-1 text-xs leading-relaxed text-gray-500 dark:text-zinc-400">{{ node.description || '暂无说明' }}</p>
                      </div>
                      <div class="flex shrink-0 items-center gap-2">
                        <span class="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px]" :class="statusClass(node.progress?.status)">
                          {{ statusText(node.progress?.status) }}
                        </span>
                        <span class="inline-flex items-center gap-1 text-[10px] text-gray-400">
                          <Clock3 class="h-3.5 w-3.5" />
                          {{ node.estimated_minutes }} 分钟
                        </span>
                      </div>
                    </div>

                    <div v-if="node.resources.length" class="mt-3 flex flex-wrap gap-2">
                      <button
                        v-for="res in node.resources"
                        :key="res.id || res.file_id || res.url || res.bv_id"
                        type="button"
                        @click="openResource(res)"
                        class="inline-flex items-center gap-1.5 rounded bg-blue-50 px-2 py-1 text-[10px] text-blue-700 dark:bg-blue-950/20 dark:text-blue-300"
                      >
                        <PlaySquare v-if="res.resource_type === 'bilibili'" class="h-3.5 w-3.5" />
                        <FileText v-else-if="res.resource_type === 'file'" class="h-3.5 w-3.5" />
                        <Link v-else class="h-3.5 w-3.5" />
                        <span>{{ res.title || res.bv_id || res.url || '附件' }}</span>
                      </button>
                    </div>

                    <div v-if="nodeSubmissions(node).length" class="mt-4 space-y-3">
                      <div
                        v-for="submission in nodeSubmissions(node)"
                        :key="submission.id"
                        class="rounded border border-gray-100 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
                      >
                        <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                          <span class="inline-flex items-center gap-1.5 text-xs font-medium text-gray-700 dark:text-zinc-200">
                            <MessageSquareText class="h-3.5 w-3.5 text-blue-600" />
                            {{ formatDateTime(submission.created_at) }}
                          </span>
                          <span class="rounded px-2 py-0.5 text-[10px]" :class="statusClass(submission.review_status)">
                            {{ statusText(submission.review_status) }}
                          </span>
                        </div>
                        <p class="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-gray-600 dark:text-zinc-300">{{ submission.content || '无文本说明' }}</p>
                        <div v-if="submission.attachment_ids?.length" class="mt-3 flex flex-wrap gap-2">
                          <button
                            v-for="fileId in submission.attachment_ids"
                            :key="fileId"
                            type="button"
                            @click="downloadAttachment(fileId)"
                            class="inline-flex items-center gap-1.5 rounded bg-gray-100 px-2 py-1 text-[10px] text-gray-600 hover:text-blue-600 dark:bg-zinc-800 dark:text-zinc-300"
                          >
                            <Paperclip class="h-3.5 w-3.5" />
                            <span>附件 {{ String(fileId).slice(0, 8) }}</span>
                          </button>
                        </div>
                        <div v-if="submission.feedback || submission.follow_up" class="mt-3 rounded bg-gray-50 p-3 text-xs text-gray-500 dark:bg-zinc-950 dark:text-zinc-400">
                          <p v-if="submission.feedback">评语：{{ submission.feedback }}</p>
                          <p v-if="submission.follow_up" class="mt-1">追评：{{ submission.follow_up }}</p>
                        </div>
                      </div>
                    </div>
                    <div v-else class="mt-4 rounded border border-dashed border-gray-200 py-5 text-center text-xs text-gray-400 dark:border-zinc-800">
                      该节点暂无提交。
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>
        </main>
      </div>

      <div v-else-if="!loading" class="minimal-card flex min-h-[520px] flex-col items-center justify-center bg-white text-center text-gray-400 dark:bg-zinc-900">
        <Loader2 class="mb-3 h-8 w-8" />
        <p class="text-sm font-semibold">暂无进度数据</p>
      </div>
    </div>
  </div>
</template>
