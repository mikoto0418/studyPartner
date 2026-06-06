<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, Brain, FileText, HeartHandshake, LineChart, RefreshCw, Trophy } from 'lucide-vue-next'
import { authApi } from '../../api/modules/auth'
import { learningPathApi } from '../../api/modules/learning_path'
import type { StudentGrowthOverviewOut } from '../../api/modules/learning_path'

const loading = ref(false)
const growth = ref<StudentGrowthOverviewOut | null>(null)
const currentUserId = ref('')

const loadGrowth = async () => {
  loading.value = true
  try {
    if (!currentUserId.value) {
      const meRes = await authApi.getMe()
      currentUserId.value = meRes.data.id
    }
    const res = await learningPathApi.getStudentGrowth(currentUserId.value)
    growth.value = res.data
  } catch (error) {
    console.warn('Failed to load growth overview', error)
  } finally {
    loading.value = false
  }
}

const metricCards = computed(() => {
  const metrics = growth.value?.metrics || {}
  return [
    { label: '学习路径数', value: metrics.path_count || 0, unit: '条', icon: FileText },
    { label: '已完成路径', value: metrics.completed_paths || 0, unit: '条', icon: Trophy },
    { label: '平均完成度', value: metrics.avg_progress || 0, unit: '%', icon: Activity },
    { label: '近期学习时长', value: metrics.recent_study_minutes || 0, unit: '分钟', icon: LineChart }
  ]
})

const maxStudyMinutes = computed(() => Math.max(...(growth.value?.trend.map(item => Number(item.study_minutes || 0)) || [1]), 1))

onMounted(loadGrowth)
</script>

<template>
  <div class="space-y-6" v-loading="loading">
    <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
      <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div>
          <div class="flex items-center gap-2">
            <HeartHandshake class="w-5 h-5 text-blue-600" />
            <h2 class="text-lg font-bold text-gray-900 dark:text-zinc-50">我的成长全览</h2>
          </div>
          <p class="mt-2 text-xs leading-relaxed text-gray-500 dark:text-zinc-400 max-w-3xl">
            集中呈现学习路径进度、复盘趋势与 Memory 沉淀，帮助快速把握阶段成长状态。
          </p>
        </div>
        <button
          @click="loadGrowth"
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs text-gray-500"
        >
          <RefreshCw class="w-3.5 h-3.5" />
          <span>刷新</span>
        </button>
      </div>
    </div>

    <div v-if="growth" class="space-y-6">
      <div class="grid grid-cols-2 xl:grid-cols-4 gap-6">
        <div
          v-for="card in metricCards"
          :key="card.label"
          class="minimal-card bg-white dark:bg-zinc-900 p-5 flex items-center justify-between"
        >
          <div>
            <span class="text-[10px] text-gray-400 font-medium">{{ card.label }}</span>
            <div class="mt-1 text-2xl font-bold text-gray-900 dark:text-zinc-50">
              {{ card.value }}<span class="ml-1 text-xs text-gray-400">{{ card.unit }}</span>
            </div>
          </div>
          <div class="w-10 h-10 rounded border border-gray-100 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 flex items-center justify-center text-blue-600">
            <component :is="card.icon" class="w-4 h-4" />
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <section class="xl:col-span-8 minimal-card bg-white dark:bg-zinc-900 p-6">
          <div class="flex items-center justify-between mb-5">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
              <LineChart class="w-4 h-4 text-blue-600" />
              <span>近 7 次复盘趋势</span>
            </h3>
            <span class="text-[10px] text-gray-400">学习时长与任务完成</span>
          </div>
          <div class="h-72 flex items-end gap-4 border-b border-l border-gray-100 dark:border-zinc-800 p-4">
            <div
              v-for="item in growth.trend"
              :key="item.date"
              class="flex-1 flex flex-col items-center justify-end gap-2 h-full"
            >
              <div class="w-full max-w-12 rounded-t bg-blue-500/80" :style="{ height: `${Math.max(8, Number(item.study_minutes || 0) / maxStudyMinutes * 210)}px` }"></div>
              <span class="text-[9px] text-gray-400">{{ String(item.date).slice(5) }}</span>
            </div>
            <div v-if="growth.trend.length === 0" class="w-full h-full flex items-center justify-center text-xs text-gray-400">
              暂无复盘趋势数据。
            </div>
          </div>
        </section>

        <section class="xl:col-span-4 minimal-card bg-white dark:bg-zinc-900 p-6">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
            <FileText class="w-4 h-4 text-emerald-600" />
            <span>阶段成长摘要</span>
          </h3>
          <p class="mt-4 text-xs leading-relaxed text-gray-600 dark:text-zinc-300 whitespace-pre-wrap">
            {{ growth.parent_summary }}
          </p>
        </section>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <section class="xl:col-span-7 minimal-card bg-white dark:bg-zinc-900 p-6">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 mb-4">学习路径概览</h3>
          <div class="space-y-3">
            <div
              v-for="path in growth.learning_paths"
              :key="path.id"
              class="p-4 rounded-lg border border-gray-100 dark:border-zinc-800"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <p class="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">{{ path.title }}</p>
                  <p class="mt-1 text-[10px] text-gray-400 line-clamp-1">{{ path.goal }}</p>
                </div>
                <span class="text-[10px] px-2 py-1 rounded bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
                  {{ path.avg_progress }}%
                </span>
              </div>
              <div class="mt-3 h-1.5 bg-gray-100 dark:bg-zinc-800 rounded">
                <div class="h-full bg-blue-600 rounded" :style="{ width: `${Math.min(100, path.avg_progress || 0)}%` }"></div>
              </div>
            </div>
            <div v-if="growth.learning_paths.length === 0" class="py-8 text-center text-xs text-gray-400">
              暂无学习路径数据。
            </div>
          </div>
        </section>

        <section class="xl:col-span-5 minimal-card bg-white dark:bg-zinc-900 p-6">
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2 mb-4">
            <Brain class="w-4 h-4 text-indigo-500" />
            <span>我的 Memory 卡片</span>
          </h3>
          <div class="space-y-3 max-h-[420px] overflow-y-auto">
            <div
              v-for="memory in growth.memory_cards"
              :key="memory.id"
              class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/40 dark:bg-zinc-950/30"
            >
              <div class="flex items-center justify-between">
                <span class="text-[10px] px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">{{ memory.category }}</span>
                <span class="text-[10px] text-gray-400">{{ Math.round((memory.confidence || 0) * 100) }}%</span>
              </div>
              <p class="mt-2 text-xs leading-relaxed text-gray-700 dark:text-zinc-300">{{ memory.content }}</p>
              <p v-if="memory.evidence" class="mt-2 text-[10px] text-gray-400 line-clamp-2">{{ memory.evidence }}</p>
            </div>
            <div v-if="growth.memory_cards.length === 0" class="py-8 text-center text-xs text-gray-400">
              暂无 Memory，完成复盘后会逐渐沉淀。
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>
