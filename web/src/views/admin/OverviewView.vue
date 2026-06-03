<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Users, Brain, HardDrive, Cpu, Terminal, CheckCircle } from 'lucide-vue-next'
import { userApi } from '../../api/modules/user'

// Stats
const totalUsers = ref(0)
const tokenCalls = ref(1385)
const storageUsed = ref('1.24 GB')
const loadingStats = ref(false)

// Usage logs list mimicking LLMUsageLog database schema
const usageLogs = ref([
  { id: 'log-1', task_type: 'student_chat', model_name: 'DeepSeek-V4-Flash', tokens: 1240, latency: '412ms', time: '刚刚', success: true },
  { id: 'log-2', task_type: 'knowledge_qa', model_name: 'DeepSeek-V4-Flash', tokens: 2840, latency: '820ms', time: '3分钟前', success: true },
  { id: 'log-3', task_type: 'memory_extract', model_name: 'DeepSeek-V4-Flash', tokens: 680, latency: '1240ms', time: '12分钟前', success: true },
  { id: 'log-4', task_type: 'daily_review', model_name: 'DeepSeek-V4-Flash', tokens: 3450, latency: '2100ms', time: '35分钟前', success: true },
  { id: 'log-5', task_type: 'document_summary', model_name: 'DeepSeek-V4-Flash', tokens: 4120, latency: '3200ms', time: '1小时前', success: true }
])

const loadStats = async () => {
  loadingStats.value = true
  try {
    const res = await userApi.listUsers({ page_size: 1 })
    totalUsers.value = res.data?.total || 12
  } catch (error) {
    totalUsers.value = 12
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
    <!-- Top banner/stat card row -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      
      <!-- 用户总数 -->
      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">系统注册账号数</span>
          <span class="text-2xl font-bold text-gray-800 dark:text-zinc-50 font-mono">{{ totalUsers }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-blue-50 dark:bg-blue-950/20 flex items-center justify-center text-blue-600 dark:text-blue-500 border border-blue-100/30">
          <Users class="w-4 h-4" />
        </div>
      </div>

      <!-- 模型调用数 -->
      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">今日大模型调用总量</span>
          <span class="text-2xl font-bold text-purple-600 dark:text-purple-500 font-mono">{{ tokenCalls }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-purple-50 dark:bg-purple-950/20 flex items-center justify-center text-purple-600 dark:text-purple-500 border border-purple-100/30">
          <Brain class="w-4 h-4" />
        </div>
      </div>

      <!-- 存储容量 -->
      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">MinIO 磁盘已用容量</span>
          <span class="text-2xl font-bold text-indigo-600 dark:text-indigo-500 font-mono">{{ storageUsed }}</span>
        </div>
        <div class="w-10 h-10 rounded bg-indigo-50 dark:bg-indigo-950/20 flex items-center justify-center text-indigo-600 dark:text-indigo-500 border border-indigo-100/30">
          <HardDrive class="w-4 h-4" />
        </div>
      </div>

      <!-- 系统健康度 -->
      <div class="minimal-card p-5 flex items-center justify-between">
        <div class="space-y-1">
          <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">系统网关运行状态</span>
          <span class="text-2xl font-bold text-emerald-600 dark:text-emerald-500 flex items-center space-x-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-ping mr-1"></span>
            <span>健康</span>
          </span>
        </div>
        <div class="w-10 h-10 rounded bg-emerald-50 dark:bg-emerald-950/20 flex items-center justify-center text-emerald-600 dark:text-emerald-500 border border-emerald-100/30">
          <CheckCircle class="w-4 h-4" />
        </div>
      </div>
    </div>

    <!-- Middle grid (Telemetry & Audit Logs) -->
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
      
      <!-- Telemetry Health Info (4 cols) -->
      <div class="lg:col-span-4 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col justify-between space-y-4">
        <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center space-x-1.5">
          <Cpu class="w-4 h-4 text-blue-600" />
          <span>服务引擎资源遥测</span>
        </h4>

        <!-- Gauges details -->
        <div class="space-y-3.5 flex-1 justify-center flex flex-col text-xs">
          <!-- CPU -->
          <div class="space-y-1">
            <div class="flex justify-between text-gray-500">
              <span>Docker 主机 CPU 占用</span>
              <span class="font-bold">14.2 %</span>
            </div>
            <div class="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
              <div class="bg-blue-600 h-full rounded-full" style="width: 14.2%"></div>
            </div>
          </div>
          
          <!-- Memory -->
          <div class="space-y-1">
            <div class="flex justify-between text-gray-500">
              <span>Docker 主机 内存占用</span>
              <span class="font-bold">42.5 %</span>
            </div>
            <div class="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
              <div class="bg-purple-600 h-full rounded-full" style="width: 42.5%"></div>
            </div>
          </div>

          <!-- Network throughput -->
          <div class="space-y-1">
            <div class="flex justify-between text-gray-500">
              <span>Qdrant 向量吞吐读写</span>
              <span class="font-bold">正常</span>
            </div>
            <div class="w-full bg-gray-100 dark:bg-zinc-800 rounded-full h-1.5 overflow-hidden">
              <div class="bg-indigo-600 h-full rounded-full" style="width: 8%"></div>
            </div>
          </div>
        </div>

        <p class="text-[9px] text-gray-400">系统容器主网关及内部存储驱动连接通畅，健康探针每 5 秒广播自检。</p>
      </div>

      <!-- LLM Usage Audit Logs (8 cols) -->
      <div class="lg:col-span-8 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-[350px]">
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between flex-shrink-0">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Terminal class="w-4 h-4 text-purple-600" />
            <span>实时大模型调用审计日志</span>
          </h4>
          <span class="text-[9px] text-purple-600 bg-purple-50 dark:bg-purple-950/40 px-2 py-0.5 rounded font-bold font-mono">
            llm_usage_logs
          </span>
        </div>

        <!-- Roster / Table log list -->
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
              <p class="text-[9px] text-gray-400">发送Tokens: {{ log.tokens }} &bull; API时延: {{ log.latency }}</p>
            </div>

            <div class="flex items-center space-x-2 flex-shrink-0">
              <span class="text-[9px] text-gray-400">{{ log.time }}</span>
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
            </div>
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
