<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleX } from 'lucide-vue-next'
import { assessmentApi, type StudentReview } from '../../api/modules/assessment'
import RichStem from '../../components/assessment/RichStem.vue'
import MathText from '../../components/common/MathText.vue'

const route = useRoute()
const router = useRouter()
const paperId = String(route.params.id || '')

const loading = ref(true)
const review = ref<StudentReview | null>(null)

const typeLabel = (type: string) => {
  const map: Record<string, string> = {
    single: '单选题',
    multiple: '多选题',
    judge: '判断题',
    fill: '填空题',
    short: '简答题',
    essay: '论述题',
    code: '编程题'
  }
  return map[type] || '题目'
}

const formatAnswer = (value: any) => {
  if (value == null || value === '') return '未作答'
  if (Array.isArray(value)) return value.length ? value.join('、') : '未作答'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

// 回顾页只说「过了几个用例」，不列隐藏用例的输入输出，避免学生据此打表
const judgeStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    accepted: '全部通过',
    wrong_answer: '有输出不符的用例',
    compile_error: '编译或语法未通过',
    runtime_error: '运行时报错',
    time_limit: '超时',
    no_answer: '未提交代码',
    judge_error: '判题服务异常'
  }
  return map[status] || status
}

const load = async () => {
  loading.value = true
  try {
    const res = await assessmentApi.getStudentReview(paperId)
    review.value = res.data
  } catch {
    ElMessage.error('成绩还不能查看')
    review.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="space-y-4">
    <div class="surface-panel overflow-hidden">
      <div class="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div class="min-w-0">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ review?.paper.title || '成绩回顾' }}</h3>
          <p class="mt-1 text-[11px] text-gray-400">
            {{ review?.questions.length || 0 }} 题
            <template v-if="review?.paper.total_score != null"> · 满分 {{ review.paper.total_score }}</template>
          </p>
        </div>
        <button class="ui-button-secondary" @click="router.push('/student/assessment')">返回列表</button>
      </div>

      <div v-if="review" class="grid grid-cols-2 divide-x divide-gray-100 border-t border-gray-100 dark:divide-zinc-800 dark:border-zinc-800 sm:grid-cols-3">
        <div class="px-6 py-5 text-center">
          <p class="text-[11px] text-gray-400">
            {{ review.attempt.status === 'pending_review' ? '已判得分' : '得分' }}
          </p>
          <p class="mt-1 text-2xl font-semibold text-gray-900 dark:text-zinc-50">{{ review.attempt.score ?? review.attempt.objective_score ?? 0 }}</p>
        </div>
        <div class="px-6 py-5 text-center">
          <p class="text-[11px] text-gray-400">用时</p>
          <p class="mt-1 text-2xl font-semibold text-gray-900 dark:text-zinc-50">
            {{ Math.max(1, Math.round((review.attempt.duration_seconds ?? 0) / 60)) }}<span class="ml-0.5 text-xs font-normal text-gray-400">分钟</span>
          </p>
        </div>
        <div class="col-span-2 border-t border-gray-100 px-6 py-5 text-center dark:border-zinc-800 sm:col-span-1 sm:border-t-0">
          <p class="text-[11px] text-gray-400">状态</p>
          <p
            class="mt-1 text-sm font-semibold"
            :class="review.attempt.status === 'pending_review' ? 'text-amber-600 dark:text-amber-400' : 'text-emerald-600 dark:text-emerald-400'"
          >
            {{ review.attempt.status === 'pending_review' ? '待老师批改' : '已批改完成' }}
          </p>
        </div>
      </div>

      <p
        v-if="review?.attempt.status === 'pending_review'"
        class="border-t border-gray-100 px-5 py-3 text-[11px] leading-relaxed text-amber-600 dark:border-zinc-800 dark:text-amber-400"
      >
        主观题与编程题还没批完，上面只是当前已判部分的分数，不是最终成绩。
      </p>
    </div>

    <article
      v-for="question in review?.questions || []"
      :key="question.question_id"
      class="surface-panel p-5"
    >
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <span class="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
          第 {{ question.order_index + 1 }} 题
        </span>
        <span class="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
          {{ typeLabel(question.question_type) }}
          <template v-if="question.max_score == null"> · 分值待定</template>
          <template v-else> · 满分 {{ question.max_score }}</template>
        </span>
        <span
          v-if="question.graded && question.is_correct === true"
          class="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400"
        >
          <CircleCheck class="h-3 w-3" />正确 · {{ question.score }} 分
        </span>
        <span
          v-else-if="question.graded && question.is_correct === false"
          class="inline-flex items-center gap-1 rounded bg-red-50 px-2 py-0.5 text-[11px] font-semibold text-red-500 dark:bg-red-950/30 dark:text-red-400"
        >
          <CircleX class="h-3 w-3" />不正确 · {{ question.score }} 分
        </span>
        <span v-else-if="question.graded" class="rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
          {{ question.score }} 分
        </span>
        <span v-else class="rounded bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-600 dark:bg-amber-950/30 dark:text-amber-400">
          待老师批改
        </span>
      </div>

      <RichStem :stem="question.stem" :images="question.stem_images" class="text-sm leading-relaxed text-gray-800 dark:text-zinc-100" />

      <div v-if="question.options?.length" class="mt-2 space-y-1">
        <div
          v-for="(opt, index) in question.options"
          :key="`${question.question_id}-${index}`"
          class="rounded border border-gray-100 px-2 py-1 text-xs text-gray-600 dark:border-zinc-800 dark:text-zinc-300"
        >
          <span class="font-semibold">{{ opt.key }}.</span>
          <MathText :text="opt.text || ''" class="ml-1" />
        </div>
      </div>

      <div class="mt-3 rounded bg-gray-50 px-3 py-2 dark:bg-zinc-900/60">
        <p class="text-[11px] font-semibold text-gray-400">我的作答</p>
        <pre
          v-if="question.question_type === 'code'"
          class="mt-1 max-h-80 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-gray-800 dark:text-zinc-100"
        >{{ formatAnswer(question.student_answer) }}</pre>
        <p v-else class="mt-1 whitespace-pre-wrap text-sm text-gray-800 dark:text-zinc-100">{{ formatAnswer(question.student_answer) }}</p>
      </div>

      <div
        v-if="question.judge_summary"
        class="mt-2 rounded px-3 py-2 text-[11px]"
        :class="question.judge_summary.status === 'accepted'
          ? 'bg-emerald-50/70 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300'
          : 'bg-amber-50/70 text-amber-700 dark:bg-amber-950/20 dark:text-amber-300'"
      >
        测试用例通过 {{ question.judge_summary.passed }} / {{ question.judge_summary.total }}（{{ judgeStatusLabel(question.judge_summary.status) }}）
      </div>

      <div class="mt-2 rounded bg-emerald-50/70 px-3 py-2 dark:bg-emerald-950/20">
        <p class="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300">参考答案</p>
        <p class="mt-1 whitespace-pre-wrap text-sm text-emerald-900 dark:text-emerald-100">{{ formatAnswer(question.reference_answer) }}</p>
      </div>

      <div v-if="question.analysis" class="mt-2 text-xs leading-relaxed text-gray-500 dark:text-zinc-400">
        <span class="font-semibold">解析：</span>{{ question.analysis }}
      </div>
    </article>

    <div v-if="!loading && !review" class="surface-panel p-8 text-center text-sm text-gray-400">
      交卷后才能查看逐题成绩。
    </div>
  </div>
</template>
