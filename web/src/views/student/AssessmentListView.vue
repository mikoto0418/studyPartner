<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Clock, FileText, ChevronRight, CheckCircle2, CircleDashed } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { assessmentApi, type StudentPaper } from '../../api/modules/assessment'

const router = useRouter()
const loading = ref(false)
const papers = ref<StudentPaper[]>([])

const loadPapers = async () => {
  loading.value = true
  try {
    const res = await assessmentApi.listStudentPapers()
    papers.value = res.data || []
  } catch (err) {
    ElMessage.error('获取试卷列表失败')
  } finally {
    loading.value = false
  }
}

// 主观题未批完时后端返回 pending_review，此时分数只是客观题小计，不能当最终成绩展示
const statusMeta = (paper: StudentPaper) => {
  if (paper.attempt_status === 'submitted') {
    return { label: `已交卷 · 得分 ${paper.attempt_score ?? 0}`, tone: 'green' }
  }
  if (paper.attempt_status === 'pending_review') {
    return { label: '已交卷 · 待老师批改', tone: 'amber' }
  }
  if (paper.attempt_status === 'in_progress') {
    return { label: '继续作答', tone: 'blue' }
  }
  return { label: '开始作答', tone: 'blue' }
}

const toneClass: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400',
  amber: 'bg-amber-50 text-amber-600 dark:bg-amber-950/30 dark:text-amber-400',
  blue: 'bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400'
}

const formatDate = (iso?: string | null) => {
  if (!iso) return '未设置'
  const d = new Date(iso)
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`
}

const startPaper = (paper: StudentPaper) => {
  if (paper.attempt_status === 'submitted' || paper.attempt_status === 'pending_review') {
    router.push(`/student/assessment/${paper.id}/review`)
    return
  }
  router.push(`/student/assessment/${paper.id}`)
}

onMounted(loadPapers)
</script>

<template>
  <div class="space-y-5">
    <div class="surface-panel p-5">
      <div class="flex items-center gap-3">
        <div class="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
          <FileText class="h-5 w-5" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">我的作业与考试</h3>
          <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">
            老师发布给你的在线作业与考试。一页一题，用「上一题 / 下一题」或答题卡切换；编程题可以随时自测。
          </p>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="paper in papers"
        :key="paper.id"
        class="dashboard-widget-card group cursor-pointer p-5 transition hover:border-blue-300"
        @click="startPaper(paper)"
      >
        <div class="mb-3 flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h4 class="truncate text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ paper.title }}</h4>
            <p v-if="paper.description" class="mt-1 line-clamp-2 text-xs text-gray-400 dark:text-zinc-500">
              {{ paper.description }}
            </p>
          </div>
          <span
            class="flex-shrink-0 rounded px-2 py-1 text-[10px] font-semibold"
            :class="paper.attempt_status
              ? toneClass[statusMeta(paper).tone]
              : 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'"
          >
            {{ statusMeta(paper).label }}
          </span>
        </div>

        <div class="flex items-center gap-4 text-[11px] text-gray-400 dark:text-zinc-500">
          <span class="inline-flex items-center gap-1">
            <CircleDashed class="h-3.5 w-3.5" /> {{ paper.question_count }} 题
          </span>
          <span class="inline-flex items-center gap-1">
            <CheckCircle2 class="h-3.5 w-3.5" />
            <template v-if="paper.total_score === null || paper.total_score === undefined">满分待定</template>
            <template v-else>满分 {{ paper.total_score }}</template>
          </span>
          <span v-if="paper.time_limit_minutes" class="inline-flex items-center gap-1">
            <Clock class="h-3.5 w-3.5" /> 限时 {{ paper.time_limit_minutes }} 分钟
          </span>
          <span
            v-if="paper.require_fullscreen === false"
            class="inline-flex items-center gap-1 rounded bg-gray-100 px-1.5 py-0.5 dark:bg-zinc-800"
          >
            可窗口作答
          </span>
          <span class="inline-flex items-center gap-1">
            <Clock class="h-3.5 w-3.5" /> 截止 {{ formatDate(paper.due_at) }}
          </span>
        </div>

        <div class="mt-4 flex items-center justify-end text-xs font-semibold text-blue-600 dark:text-blue-400">
          <span>{{ paper.attempt_status === 'submitted' || paper.attempt_status === 'pending_review' ? '查看成绩' : '进入' }}</span>
          <ChevronRight class="h-4 w-4 transition group-hover:translate-x-0.5" />
        </div>
      </div>

      <div
        v-if="!loading && papers.length === 0"
        class="col-span-full flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 py-16 text-center dark:border-zinc-800"
      >
        <FileText class="mb-3 h-8 w-8 text-gray-300 dark:text-zinc-700" />
        <p class="text-sm text-gray-400 dark:text-zinc-500">暂无已发布的作业或考试</p>
      </div>
    </div>
  </div>
</template>