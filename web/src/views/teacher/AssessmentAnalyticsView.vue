<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { BarChart3, Clock, FileText, ShieldAlert, Target, TrendingUp, Users } from 'lucide-vue-next'
import type { EChartsOption } from 'echarts'
import BaseChart from '../../components/common/BaseChart.vue'
import { assessmentApi, type AssessmentPaper, type PaperAnalytics } from '../../api/modules/assessment'

const papers = ref<AssessmentPaper[]>([])
const selectedPaperId = ref('')
const analytics = ref<PaperAnalytics | null>(null)
const loading = ref(false)

const loadPapers = async () => {
  try {
    const res = await assessmentApi.listPapers()
    // 只列已发布/待校对的试卷：解析中的卷子没有作答数据，进分析页只会是一片空
    papers.value = (res.data || []).filter(
      (p: AssessmentPaper) => p.parse_status === 'published' || p.parse_status === 'awaiting_review'
    )
    if (!selectedPaperId.value && papers.value.length) {
      selectedPaperId.value = papers.value[0].id
      await loadAnalytics()
    }
  } catch (error) {
    ElMessage.error('获取试卷列表失败')
  }
}

const loadAnalytics = async () => {
  if (!selectedPaperId.value) return
  loading.value = true
  analytics.value = null
  try {
    const res = await assessmentApi.getPaperAnalytics(selectedPaperId.value)
    analytics.value = res.data
  } catch (error) {
    ElMessage.error('获取试卷分析失败')
  } finally {
    loading.value = false
  }
}

const overview = computed(() => analytics.value?.overview)

const fmtDuration = (seconds?: number | null) => {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m} 分 ${s} 秒` : `${s} 秒`
}

const metricCards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { label: '已作答', value: o.finished, unit: `/ ${o.assigned} 人`, icon: Users, tone: 'blue' },
    {
      label: '平均分',
      value: o.avg_score ?? '—',
      unit: o.total_score ? `/ ${o.total_score}` : '',
      icon: TrendingUp,
      tone: 'emerald'
    },
    { label: '及格率', value: o.pass_rate ?? '—', unit: '%', icon: Target, tone: 'amber' },
    { label: '平均用时', value: fmtDuration(o.avg_duration_seconds), unit: '', icon: Clock, tone: 'indigo' },
    { label: '可疑作答', value: analytics.value?.suspicious_count ?? 0, unit: '人', icon: ShieldAlert, tone: 'red' },
    { label: '待批改', value: o.pending_review, unit: '人', icon: FileText, tone: 'violet' }
  ]
})

const toneClass: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400',
  emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400',
  amber: 'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400',
  indigo: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400',
  red: 'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400',
  violet: 'bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-400'
}

// ---------- 图表配置 ----------

const scoreDistributionOption = computed<EChartsOption>(() => {
  const dist = analytics.value?.score_distribution || []
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: dist.map((d) => d.label) },
    yAxis: { type: 'value', name: '人数', minInterval: 1 },
    series: [
      {
        type: 'bar',
        data: dist.map((d) => d.count),
        barWidth: '50%',
        itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top' }
      }
    ]
  }
})

const questionAccuracyOption = computed<EChartsOption>(() => {
  const qs = (analytics.value?.questions || []).filter((q) => q.accuracy != null)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const q = qs[p.dataIndex]
        return `第 ${q.order_index + 1} 题<br/>正确率 ${q.accuracy}%<br/>作答 ${q.answered} 人 · 答对 ${q.correct} 人`
      }
    },
    grid: { left: 45, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: qs.map((q) => `${q.order_index + 1}`),
      name: '题号',
      axisLabel: { interval: Math.max(0, Math.floor(qs.length / 30)) }
    },
    yAxis: { type: 'value', name: '正确率 %', max: 100 },
    series: [
      {
        type: 'bar',
        data: qs.map((q) => q.accuracy),
        itemStyle: {
          // 低于 60% 的题标红，教师一眼能看出薄弱题
          color: (p: any) => (p.value < 60 ? '#ef4444' : '#10b981'),
          borderRadius: [3, 3, 0, 0]
        }
      }
    ]
  }
})

const questionDwellOption = computed<EChartsOption>(() => {
  const qs = (analytics.value?.questions || []).filter((q) => q.avg_dwell_seconds != null)
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        const q = qs[p.dataIndex]
        return `第 ${q.order_index + 1} 题<br/>平均停留 ${q.avg_dwell_seconds} 秒`
      }
    },
    grid: { left: 45, right: 20, top: 30, bottom: 40 },
    xAxis: {
      type: 'category',
      data: qs.map((q) => `${q.order_index + 1}`),
      name: '题号',
      axisLabel: { interval: Math.max(0, Math.floor(qs.length / 30)) }
    },
    yAxis: { type: 'value', name: '秒' },
    series: [
      {
        type: 'bar',
        data: qs.map((q) => q.avg_dwell_seconds),
        itemStyle: { color: '#8b5cf6', borderRadius: [3, 3, 0, 0] }
      }
    ]
  }
})

const behaviorOption = computed<EChartsOption>(() => {
  const dist = analytics.value?.behavior_distribution || []
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} 次 ({d}%)' },
    legend: { type: 'scroll', bottom: 0, textStyle: { fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        data: dist.map((d) => ({
          name: d.event_type,
          value: d.count,
          // 违规类事件用暖色，中性记录用灰蓝，视觉上区分开
          itemStyle: { color: d.is_flag ? '#f59e0b' : '#94a3b8' }
        })),
        label: { fontSize: 10 }
      }
    ]
  }
})

const behaviorLabels: Record<string, string> = {
  question_dwell: '题目停留',
  focus_dwell: '焦点停留',
  fullscreen_exit: '退出全屏',
  fullscreen_denied: '拒绝全屏',
  blocked_paste: '尝试粘贴',
  blocked_copy: '尝试复制',
  blocked_cut: '尝试剪切',
  blocked_shortcut: '快捷键拦截',
  blocked_input: '非手敲输入',
  blocked_contextmenu: '右键拦截',
  blocked_selection: '选中拦截',
  devtools_open: '开发者工具',
  focus_loss: '失焦',
  visibility_hidden: '切后台',
  clipboard_read: '读剪贴板',
  session_start: '开始作答',
  session_end: '结束作答',
  fullscreen_enter: '进入全屏'
}

const labelOf = (t: string) => behaviorLabels[t] || t

const hasScoreData = computed(() => (analytics.value?.overview.finished || 0) > 0)

onMounted(loadPapers)
</script>

<template>
  <div class="-m-4 min-h-[calc(100vh-8rem)] bg-gray-50 p-4 dark:bg-zinc-950 md:-m-8 md:p-8">
    <div class="mx-auto flex max-w-[1400px] flex-col gap-6">
      <!-- 页头 -->
      <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
        <div class="flex flex-wrap items-center justify-between gap-4">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
              <BarChart3 class="h-5 w-5" />
            </div>
            <div>
              <h2 class="text-base font-bold text-gray-900 dark:text-zinc-50">考试数据分析</h2>
              <p class="mt-0.5 text-xs text-gray-400 dark:text-zinc-500">
                分数分布、逐题正确率与作答耗时、防作弊行为分布
              </p>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <select v-model="selectedPaperId" class="ui-field w-64" @change="loadAnalytics">
              <option value="" disabled>选择试卷</option>
              <option v-for="p in papers" :key="p.id" :value="p.id">{{ p.title }}</option>
            </select>
          </div>
        </div>
      </section>

      <div v-if="!papers.length" class="minimal-card bg-white p-12 text-center text-sm text-gray-400 dark:bg-zinc-900">
        还没有可分析的试卷。请先在发题工作台发布一份试卷。
      </div>

      <template v-else-if="analytics">
        <!-- 概览卡片 -->
        <section class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <div v-for="card in metricCards" :key="card.label" class="minimal-card bg-white p-4 dark:bg-zinc-900">
            <div class="flex items-center gap-2">
              <span class="flex h-7 w-7 items-center justify-center rounded-md" :class="toneClass[card.tone]">
                <component :is="card.icon" class="h-3.5 w-3.5" />
              </span>
              <span class="text-[11px] text-gray-400 dark:text-zinc-500">{{ card.label }}</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1">
              <span class="text-xl font-bold text-gray-900 dark:text-zinc-50">{{ card.value }}</span>
              <span class="text-[11px] text-gray-400 dark:text-zinc-500">{{ card.unit }}</span>
            </div>
          </div>
        </section>

        <!-- 无作答数据 -->
        <section v-if="!hasScoreData" class="minimal-card bg-white p-12 text-center dark:bg-zinc-900">
          <p class="text-sm text-gray-500 dark:text-zinc-400">这份试卷还没有学生交卷，暂无统计数据。</p>
          <p class="mt-2 text-xs text-gray-400 dark:text-zinc-500">学生交卷后，分数分布与逐题分析会自动出现在这里。</p>
        </section>

        <template v-else>
          <!-- 分数分布 -->
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-4 text-sm font-semibold text-gray-900 dark:text-zinc-50">分数分布</h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">
              按得分率分档；满分未知的试卷无法换算比率，全部归入「不及格」档。
            </p>
            <BaseChart :option="scoreDistributionOption" height="300px" />
          </section>

          <!-- 逐题正确率 -->
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-1 text-sm font-semibold text-gray-900 dark:text-zinc-50">逐题正确率（客观题）</h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">
              低于 60% 的题目标红，是本次考试需要重点讲解的薄弱题。
            </p>
            <BaseChart
              :option="questionAccuracyOption"
              height="320px"
              :is-empty="!(analytics.questions || []).some((q) => q.accuracy != null)"
              empty-text="没有可统计的客观题作答"
            />
          </section>

          <!-- 逐题平均停留 -->
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-1 text-sm font-semibold text-gray-900 dark:text-zinc-50">逐题平均停留时长</h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">
              来自作答过程中的题目停留事件，反映每道题实际花掉的思考时间。
            </p>
            <BaseChart
              :option="questionDwellOption"
              height="320px"
              :is-empty="!(analytics.questions || []).some((q) => q.avg_dwell_seconds != null)"
              empty-text="暂无题目停留数据"
            />
          </section>

          <!-- 行为分布 -->
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-1 text-sm font-semibold text-gray-900 dark:text-zinc-50">作答行为分布</h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">
              橙色为违规类事件（复制粘贴、切屏、退出全屏、开发者工具等），灰色为中性记录。
            </p>
            <BaseChart
              :option="behaviorOption"
              height="340px"
              :is-empty="!(analytics.behavior_distribution || []).length"
              empty-text="暂无行为数据"
            />
            <div class="mt-4 flex flex-wrap gap-2">
              <span
                v-for="b in analytics.behavior_distribution"
                :key="b.event_type"
                class="inline-flex items-center gap-1.5 rounded px-2 py-1 text-[11px]"
                :class="b.is_flag
                  ? 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300'
                  : 'bg-gray-100 text-gray-600 dark:bg-zinc-800 dark:text-zinc-300'"
              >
                {{ labelOf(b.event_type) }}
                <span class="font-semibold">{{ b.count }}</span>
              </span>
            </div>
          </section>

          <!-- 逐题明细表 -->
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-4 text-sm font-semibold text-gray-900 dark:text-zinc-50">逐题明细</h3>
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-gray-100 text-left text-gray-400 dark:border-zinc-800 dark:text-zinc-500">
                    <th class="py-2 pr-4 font-medium">题号</th>
                    <th class="py-2 pr-4 font-medium">类型</th>
                    <th class="py-2 pr-4 font-medium">作答人数</th>
                    <th class="py-2 pr-4 font-medium">正确 / 得分率</th>
                    <th class="py-2 pr-4 font-medium">平均停留</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="q in analytics.questions"
                    :key="q.question_id"
                    class="border-b border-gray-50 text-gray-700 dark:border-zinc-800/50 dark:text-zinc-300"
                  >
                    <td class="py-2 pr-4 font-semibold">{{ q.order_index + 1 }}</td>
                    <td class="py-2 pr-4">{{ q.question_type }}</td>
                    <td class="py-2 pr-4">{{ q.answered }}</td>
                    <td class="py-2 pr-4">
                      <span v-if="q.accuracy != null">{{ q.accuracy }}%</span>
                      <span v-else-if="q.avg_score_rate != null">{{ q.avg_score_rate }}%（得分率）</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                    <td class="py-2 pr-4">
                      <span v-if="q.avg_dwell_seconds != null">{{ q.avg_dwell_seconds }} s</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </template>

      <div v-else-if="loading" class="minimal-card bg-white p-12 text-center text-sm text-gray-400 dark:bg-zinc-900">
        正在加载分析数据…
      </div>
    </div>
  </div>
</template>
