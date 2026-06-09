<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Users, Brain, HardDrive, Cpu, Terminal, CheckCircle } from 'lucide-vue-next'
import { adminApi, type AdminOverviewOut, type LLMUsageLogOut } from '../../api/modules/admin'

const overview = ref<AdminOverviewOut | null>(null)
const loadingStats = ref(false)

const totalUsers = computed(() => overview.value?.total_users || 0)
const llmCallsToday = computed(() => overview.value?.llm_calls_today || 0)
const storageUsed = computed(() => formatBytes(overview.value?.storage_bytes || 0))
const serviceStatus = computed(() => overview.value?.service_status || 'unknown')
const usageLogs = computed<LLMUsageLogOut[]>(() => overview.value?.recent_usage_logs || [])

const formatBytes = (bytes: number) => {
  if (bytes <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 2)} ${units[index]}`
}

const formatTime = (iso: string) => {
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatLatency = (latency?: number) => {
  if (latency === undefined || latency === null) return '-'
  return `${latency}ms`
}

const loadStats = async () => {
  loadingStats.value = true
  try {
    const res = await adminApi.getOverview()
    overview.value = res.data
  } catch (error) {
    console.warn('Failed to load admin overview', error)
    overview.value = null
  } finally {
    loadingStats.value = false
  }
}

onMounted(() => {
  loadStats()
})
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">系统注册账号数</span>
          <span class="text-2xl font-bold text-gray-800 dark:text-zinc-50 font-mono">{{ totalUsers }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-blue-50 dark:bg-blue-950/20 flex items-center justify-center text-blue-600 dark:text-blue-500 border border-blue-100/30">
          <Users class="w-4 h-4" />
        </div>
      </div>

      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">今日大模型调用总量</span>
          <span class="text-2xl font-bold text-purple-600 dark:text-purple-500 font-mono">{{ llmCallsToday }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-purple-50 dark:bg-purple-950/20 flex items-center justify-center text-purple-600 dark:text-purple-500 border border-purple-100/30">
          <Brain class="w-4 h-4" />
        </div>
      </div>

      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">知识库文件容量</span>
          <span class="text-2xl font-bold text-indigo-600 dark:text-indigo-500 font-mono">{{ storageUsed }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-indigo-50 dark:bg-indigo-950/20 flex items-center justify-center text-indigo-600 dark:text-indigo-500 border border-indigo-100/30">
          <HardDrive class="w-4 h-4" />
        </div>
      </div>

      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">系统网关运行状态</span>
          <span class="text-2xl font-bold flex items-center space-x-1.5" :class="serviceStatus === 'healthy' ? 'text-emerald-600 dark:text-emerald-500' : 'text-amber-600 dark:text-amber-500'">
            <span class="w-2.5 h-2.5 rounded-full mr-1" :class="serviceStatus === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'"></span>
            <span>{{ serviceStatus }}</span>
          </span>
        </div>
        <div class="w-10 h-10 rounded bg-emerald-50 dark:bg-emerald-950/20 flex items-center justify-center text-emerald-600 dark:text-emerald-500 border border-emerald-100/30">
          <CheckCircle class="w-4 h-4" />
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
      <div class="lg:col-span-4 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col justify-between space-y-4">
        <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center space-x-1.5">
          <Cpu class="w-4 h-4 text-blue-600" />
          <span>服务统计来源</span>
        </h4>

        <div class="space-y-3.5 flex-1 justify-center flex flex-col text-xs">
          <div class="rounded border border-gray-100 dark:border-zinc-800 px-3 py-2">
            <div class="flex justify-between text-gray-500">
              <span>账号统计</span>
              <span class="font-bold">{{ totalUsers }}</span>
            </div>
          </div>
          <div class="rounded border border-gray-100 dark:border-zinc-800 px-3 py-2">
            <div class="flex justify-between text-gray-500">
              <span>今日 LLM 调用</span>
              <span class="font-bold">{{ llmCallsToday }}</span>
            </div>
          </div>
          <div class="rounded border border-gray-100 dark:border-zinc-800 px-3 py-2">
            <div class="flex justify-between text-gray-500">
              <span>文件记录容量</span>
              <span class="font-bold">{{ storageUsed }}</span>
            </div>
          </div>
        </div>

        <button @click="loadStats" :disabled="loadingStats" class="w-full py-2 rounded bg-zinc-900 text-zinc-100 text-xs font-semibold disabled:opacity-50">
          {{ loadingStats ? '刷新中' : '刷新概览' }}
        </button>
      </div>

      <div class="lg:col-span-8 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-[350px]">
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between flex-shrink-0">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Terminal class="w-4 h-4 text-purple-600" />
            <span>大模型调用审计日志</span>
          </h4>
          <span class="text-[9px] text-purple-600 bg-purple-50 dark:bg-purple-950/40 px-2 py-0.5 rounded font-bold font-mono">
            llm_usage_logs
          </span>
        </div>

        <div class="flex-1 overflow-y-auto mt-4 space-y-3 pr-1">
          <div
            v-for="log in usageLogs"
            :key="log.id"
            class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/20 dark:bg-zinc-950/10 flex items-center justify-between text-[11px] font-mono hover:border-purple-500/30 transition-all"
          >
            <div class="space-y-1">
              <div class="flex items-center space-x-2">
                <span class="font-bold text-gray-700 dark:text-zinc-300">[{{ log.task_type }}]</span>
                <span class="text-[10px] bg-purple-50 dark:bg-purple-950/20 text-purple-600 dark:text-purple-400 px-1.5 rounded">
                  {{ log.model_name }}
                </span>
              </div>
              <p class="text-[9px] text-gray-400">Tokens: {{ log.total_tokens }} &bull; API时延: {{ formatLatency(log.latency_ms) }}</p>
              <p v-if="!log.success" class="text-[9px] text-red-500">{{ log.error_message || '调用失败' }}</p>
            </div>

            <div class="flex items-center space-x-2 flex-shrink-0">
              <span class="text-[9px] text-gray-400">{{ formatTime(log.created_at) }}</span>
              <span class="w-1.5 h-1.5 rounded-full" :class="log.success ? 'bg-emerald-500' : 'bg-red-500'"></span>
            </div>
          </div>
          <div v-if="usageLogs.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400">
            暂无大模型调用记录。
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 4px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
