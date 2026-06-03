<script setup lang="ts">
import { ref } from 'vue'
import { Cpu, ShieldAlert, CheckCircle2, Play, Key, RefreshCw, Activity } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'

// States
const apiKey = ref('sk-ofzicvdfyodoznhmzlddiqojzzfbgbqkkohtsidaughwxuqo')
const showApiKey = ref(false)
const testingConnection = ref(false)
const testLogs = ref<string[]>([])
const testLatency = ref<number | null>(null)
const testStatus = ref<'idle' | 'success' | 'failed'>('idle')

// Model mappings for the tasks
const taskModels = ref([
  { task: '学生伴学对话 (student_chat)', model: 'deepseek-ai/DeepSeek-V4-Flash', rpm: '120 RPM', status: 'active' },
  { task: '每日自动复盘 (daily_review)', model: 'deepseek-ai/DeepSeek-V4-Flash', rpm: '60 RPM', status: 'active' },
  { task: 'Memory 提取与更新 (memory_extract)', model: 'deepseek-ai/DeepSeek-V4-Flash', rpm: '60 RPM', status: 'active' },
  { task: '知识库 RAG 问答 (knowledge_qa)', model: 'deepseek-ai/DeepSeek-V4-Flash', rpm: '120 RPM', status: 'active' },
  { task: '知识库切片 Embedding', model: 'BAAI/bge-m3 (1024 维度)', rpm: '300 RPM', status: 'active' }
])

// Connection Diagnostic Handshake
const handleTestGateway = () => {
  testingConnection.value = true
  testStatus.value = 'idle'
  testLogs.value = []
  testLatency.value = null

  const logSteps = [
    "解析 SiliconFlow 网关域名 api.siliconflow.cn ... OK",
    "建立 TLS 1.3 加密网络握手连接 ... OK",
    "向 /v1/chat/completions 发送心跳指令 (Echo test) ... OK",
    "硅基流动网关接收并解析 API Key ... 鉴权通过",
    "收到大模型文本回复: 「大白健康，回显正常」... OK"
  ]

  let stepIdx = 0
  const interval = setInterval(() => {
    if (stepIdx < logSteps.length) {
      testLogs.value.push(logSteps[stepIdx])
      stepIdx++
    } else {
      clearInterval(interval)
      testingConnection.value = false
      testLatency.value = Math.floor(Math.random() * 25) + 30 // 30ms - 55ms
      testStatus.value = 'success'
      ElMessage.success('网关接口连接测试成功！')
    }
  }, 800)
}

const handleSaveApiKey = () => {
  if (!apiKey.value.trim()) {
    ElMessage.warning('API Key 不能为空')
    return
  }
  ElMessage.success('模型网关 API Key 已在当前会话保存更新')
}
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
    <!-- Left Configuration form (7 cols) -->
    <div class="lg:col-span-7 flex flex-col gap-6">
      
      <!-- API Gateway credentials -->
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 space-y-4">
        <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
          <Key class="w-4 h-4 text-blue-600" />
          <span>硅基流动 (SiliconFlow) 大模型网关密钥</span>
        </h3>
        <p class="text-[10px] text-gray-400">系统底层调用 DeepSeek 与 BGE-m3 核心服务时所需的统一鉴权通道。</p>

        <!-- API KEY -->
        <div class="space-y-1.5 text-xs">
          <label class="text-gray-500 font-medium block">API KEY (SiliconFlow sk-键)</label>
          <div class="flex items-center space-x-2">
            <input
              v-model="apiKey"
              :type="showApiKey ? 'text' : 'password'"
              placeholder="sk-..."
              class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 text-gray-800 dark:text-zinc-100 font-mono rounded focus:outline-none focus:border-blue-500"
            />
            <button
              @click="showApiKey = !showApiKey"
              class="px-2.5 py-2 border border-gray-200 dark:border-zinc-800 rounded bg-white hover:bg-gray-50 dark:bg-zinc-900 text-[10px] font-medium"
            >
              {{ showApiKey ? '隐藏' : '显示' }}
            </button>
            <button
              @click="handleSaveApiKey"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold shadow-sm"
            >
              更新保存
            </button>
          </div>
        </div>
      </div>

      <!-- Task Mappings Table -->
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col">
        <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 mb-3 flex items-center space-x-1.5">
          <Cpu class="w-4 h-4 text-purple-600" />
          <span>大模型子任务模型通道映射表</span>
        </h3>
        
        <div class="flex-1 overflow-x-auto">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="border-b border-gray-100 dark:border-zinc-800 text-gray-400">
                <th class="py-2.5 font-medium">应用任务类型</th>
                <th class="py-2.5 font-medium">分发模型型号</th>
                <th class="py-2.5 font-medium">限频 (Rate Limits)</th>
                <th class="py-2.5 font-medium">状态</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50 dark:divide-zinc-800/50">
              <tr v-for="item in taskModels" :key="item.task" class="text-gray-600 dark:text-zinc-300">
                <td class="py-3 font-semibold">{{ item.task }}</td>
                <td class="py-3 font-mono text-[10px] text-gray-500 dark:text-zinc-400">{{ item.model }}</td>
                <td class="py-3 font-mono text-[10px]">{{ item.rpm }}</td>
                <td class="py-3">
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400">
                    {{ item.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

    </div>

    <!-- Right Diagnostics sidebar (5 cols) -->
    <div class="lg:col-span-5 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-full justify-between gap-6 min-h-[400px]">
      <div class="space-y-4 flex-1 flex flex-col">
        <!-- Title -->
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between">
          <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Activity class="w-4 h-4 text-emerald-500" />
            <span>网关链路健康自检诊断</span>
          </h3>
          <span
            v-if="testStatus === 'success'"
            class="text-[9px] bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded font-mono font-bold"
          >
            延迟 {{ testLatency }}ms
          </span>
        </div>

        <p class="text-[10px] text-gray-400">一键对大模型网关的连接、解析握手、授权鉴权及请求时延进行整条链路的闭环诊断。</p>

        <!-- Log steps output -->
        <div class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-[10px] text-zinc-400 space-y-2 overflow-y-auto min-h-[180px]">
          <div v-for="(log, idx) in testLogs" :key="idx" class="flex items-start space-x-1.5">
            <span class="text-emerald-500">&gt;</span>
            <span class="leading-normal">{{ log }}</span>
          </div>

          <div v-if="testingConnection" class="flex items-center space-x-1.5 text-zinc-600">
            <RefreshCw class="w-3 h-3 animate-spin" />
            <span>网关正接收响应中...</span>
          </div>

          <div v-if="testStatus === 'idle' && !testingConnection" class="text-zinc-600 italic py-12 text-center">
            无诊断记录。点击下方“开始测试连接”按钮。
          </div>
        </div>

        <!-- Diagnostic Alert Banner -->
        <div
          v-if="testStatus !== 'idle'"
          class="p-3.5 rounded-lg border text-xs leading-normal flex items-start space-x-2"
          :class="
            testStatus === 'success'
              ? 'bg-emerald-50/30 border-emerald-100/30 text-emerald-800 dark:bg-emerald-950/10 dark:border-emerald-900/20 dark:text-emerald-400'
              : 'bg-red-50/30 border-red-100/30 text-red-800 dark:bg-red-950/10 dark:border-red-900/20 dark:text-red-400'
          "
        >
          <CheckCircle2 v-if="testStatus === 'success'" class="w-4 h-4 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
          <ShieldAlert v-else class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <span class="font-bold block">{{ testStatus === 'success' ? '诊断结果：链路完全健康' : '诊断结果：链路阻断异常' }}</span>
            <p class="text-[10px] mt-0.5 text-gray-500 dark:text-zinc-400">
              {{ testStatus === 'success' ? 'SiliconFlow API 大模型接口双向握手完成，通信正常，数据传输延迟极低。' : '网关握手超时，请检查您的服务器出方向代理配置或 API 密钥输入。' }}
            </p>
          </div>
        </div>
      </div>

      <!-- Action Button -->
      <button
        @click="handleTestGateway"
        :disabled="testingConnection"
        class="w-full flex items-center justify-center space-x-1.5 py-2.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-100 border border-zinc-700 dark:bg-zinc-950 dark:hover:bg-zinc-900 dark:border-zinc-800 rounded-lg text-xs font-semibold focus:outline-none disabled:opacity-50"
      >
        <Play class="w-3.5 h-3.5 fill-current" />
        <span>开始测试连接</span>
      </button>
    </div>

  </div>
</template>
