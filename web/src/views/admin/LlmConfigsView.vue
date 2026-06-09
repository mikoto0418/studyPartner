<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, CheckCircle2, Cpu, Key, Play, RefreshCw, ShieldAlert } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { adminApi, type LLMProviderConfigOut } from '../../api/modules/admin'

const providerName = ref('siliconflow')
const displayName = ref('SiliconFlow')
const baseUrl = ref('https://api.siliconflow.cn/v1')
const apiKey = ref('')
const showApiKey = ref(false)
const chatModel = ref('deepseek-ai/DeepSeek-V4-Flash')
const embeddingModel = ref('BAAI/bge-m3')
const enabled = ref(true)
const rpmLimit = ref<number | undefined>()
const tpmLimit = ref<number | undefined>()

const loading = ref(false)
const saving = ref(false)
const testingConnection = ref(false)
const testLogs = ref<string[]>([])
const testLatency = ref<number | null>(null)
const testStatus = ref<'idle' | 'success' | 'failed'>('idle')
const configs = ref<LLMProviderConfigOut[]>([])

const taskTypes = [
  { value: 'student_chat', label: '学生伴学对话' },
  { value: 'teacher_assistant', label: '教师智脑助教' },
  { value: 'daily_review', label: '每日自动复盘' },
  { value: 'memory_extract', label: 'Memory 提取' },
  { value: 'memory_update', label: 'Memory 更新' },
  { value: 'knowledge_qa', label: '知识库 RAG 问答' },
  { value: 'document_summary', label: '文档摘要' },
  { value: 'knowledge_embedding', label: '知识库 Embedding' }
]

const hasExistingKey = computed(() => configs.value.some((item) => item.has_api_key))

const taskRows = computed(() =>
  taskTypes.map((task) => {
    const config = configs.value.find((item) => item.task_type === task.value)
    return {
      ...task,
      model: config?.model_name || (task.value === 'knowledge_embedding' ? embeddingModel.value : chatModel.value),
      enabled: config?.enabled ?? enabled.value,
      rpm: config?.rpm_limit,
      hasKey: config?.has_api_key ?? hasExistingKey.value
    }
  })
)

const loadConfigs = async () => {
  loading.value = true
  try {
    const res = await adminApi.listLlmConfigs()
    configs.value = res.data || []
    const firstConfig = configs.value[0]
    const chatConfig = configs.value.find((item) => item.task_type !== 'knowledge_embedding') || firstConfig
    const embeddingConfig = configs.value.find((item) => item.task_type === 'knowledge_embedding')

    if (firstConfig) {
      providerName.value = firstConfig.provider_name
      displayName.value = firstConfig.display_name || firstConfig.provider_name
      baseUrl.value = firstConfig.base_url
      enabled.value = firstConfig.enabled
      rpmLimit.value = firstConfig.rpm_limit
      tpmLimit.value = firstConfig.tpm_limit
    }
    if (chatConfig) chatModel.value = chatConfig.model_name
    if (embeddingConfig) embeddingModel.value = embeddingConfig.model_name
  } catch (error) {
    console.warn('Failed to load LLM configs', error)
    configs.value = []
  } finally {
    loading.value = false
  }
}

const handleSaveConfig = async () => {
  if (!baseUrl.value.trim() || !chatModel.value.trim() || !embeddingModel.value.trim()) {
    ElMessage.warning('请填写 Base URL、对话模型与 Embedding 模型')
    return
  }
  if (!apiKey.value.trim() && !hasExistingKey.value) {
    ElMessage.warning('首次保存模型通道必须填写 API Key')
    return
  }

  saving.value = true
  try {
    const payload = {
      provider_name: providerName.value,
      display_name: displayName.value,
      base_url: baseUrl.value.trim(),
      chat_model: chatModel.value.trim(),
      embedding_model: embeddingModel.value.trim(),
      task_types: taskTypes.filter((item) => item.value !== 'knowledge_embedding').map((item) => item.value),
      enabled: enabled.value,
      rpm_limit: rpmLimit.value,
      tpm_limit: tpmLimit.value,
      ...(apiKey.value.trim() ? { api_key: apiKey.value.trim() } : {})
    }
    const res = await adminApi.saveLlmConfigs(payload)
    configs.value = res.data || []
    apiKey.value = ''
    ElMessage.success('LLM 通道配置已保存')
    await loadConfigs()
  } catch (error) {
    console.warn('Failed to save LLM configs', error)
  } finally {
    saving.value = false
  }
}

const handleTestGateway = async () => {
  if (!apiKey.value.trim()) {
    ElMessage.warning('连接测试需要输入本次要验证的 API Key')
    return
  }

  testingConnection.value = true
  testStatus.value = 'idle'
  testLogs.value = ['正在向后端发起真实网关连接测试...']
  testLatency.value = null

  try {
    const res = await adminApi.testLlmConnection({
      provider_name: providerName.value,
      base_url: baseUrl.value.trim(),
      api_key: apiKey.value.trim(),
      model_name: chatModel.value.trim()
    })
    testLatency.value = res.data?.latency_ms ?? null
    testLogs.value.push(`后端网关检测成功，模型：${res.data?.model_name || chatModel.value}`)
    testStatus.value = 'success'
    ElMessage.success('网关接口连接测试成功')
  } catch (error) {
    testLogs.value.push('后端网关检测失败，请检查 Base URL、API Key 或服务器网络。')
    testStatus.value = 'failed'
    console.warn('LLM connection test failed', error)
  } finally {
    testingConnection.value = false
  }
}

onMounted(() => {
  loadConfigs()
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
    <div class="lg:col-span-7 flex flex-col gap-6">
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 space-y-4">
        <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
          <Key class="w-4 h-4 text-blue-600" />
          <span>硅基流动大模型网关配置</span>
        </h3>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">Base URL</span>
            <input v-model="baseUrl" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">显示名称</span>
            <input v-model="displayName" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">对话模型</span>
            <input v-model="chatModel" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">Embedding 模型</span>
            <input v-model="embeddingModel" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
        </div>

        <div class="space-y-1.5 text-xs">
          <label class="text-gray-500 font-medium block">API Key</label>
          <div class="flex items-center space-x-2">
            <input
              v-model="apiKey"
              :type="showApiKey ? 'text' : 'password'"
              placeholder="留空表示沿用已保存密钥"
              class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 text-gray-800 dark:text-zinc-100 font-mono rounded focus:outline-none focus:border-blue-500"
            />
            <button @click="showApiKey = !showApiKey" class="px-2.5 py-2 border border-gray-200 dark:border-zinc-800 rounded bg-white hover:bg-gray-50 dark:bg-zinc-900 text-[10px] font-medium">
              {{ showApiKey ? '隐藏' : '显示' }}
            </button>
            <button @click="handleSaveConfig" :disabled="saving" class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold shadow-sm disabled:opacity-50">
              {{ saving ? '保存中' : '保存配置' }}
            </button>
          </div>
          <p class="text-[10px] text-gray-400">{{ hasExistingKey ? '已保存密钥：是。页面不会回显密钥明文。' : '已保存密钥：否。首次保存必须填写密钥。' }}</p>
        </div>
      </div>

      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col">
        <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 mb-3 flex items-center space-x-1.5">
          <Cpu class="w-4 h-4 text-purple-600" />
          <span>大模型子任务模型通道映射表</span>
        </h3>

        <div class="flex-1 overflow-x-auto">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="border-b border-gray-100 dark:border-zinc-800 text-gray-400">
                <th class="py-2.5 font-medium">任务类型</th>
                <th class="py-2.5 font-medium">模型</th>
                <th class="py-2.5 font-medium">RPM</th>
                <th class="py-2.5 font-medium">状态</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50 dark:divide-zinc-800/50">
              <tr v-for="item in taskRows" :key="item.value" class="text-gray-600 dark:text-zinc-300">
                <td class="py-3 font-semibold">{{ item.label }} <span class="font-mono text-[9px] text-gray-400">({{ item.value }})</span></td>
                <td class="py-3 font-mono text-[10px] text-gray-500 dark:text-zinc-400">{{ item.model }}</td>
                <td class="py-3 font-mono text-[10px]">{{ item.rpm || '-' }}</td>
                <td class="py-3">
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold" :class="item.enabled && item.hasKey ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400' : 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'">
                    {{ item.enabled && item.hasKey ? 'active' : 'unconfigured' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="loading" class="py-8 text-center text-xs text-gray-400">正在加载配置...</div>
        </div>
      </div>
    </div>

    <div class="lg:col-span-5 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-full justify-between gap-6 min-h-[400px]">
      <div class="space-y-4 flex-1 flex flex-col">
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between">
          <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Activity class="w-4 h-4 text-emerald-500" />
            <span>网关链路健康自检</span>
          </h3>
          <span v-if="testStatus === 'success'" class="text-[9px] bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded font-mono font-bold">
            延迟 {{ testLatency }}ms
          </span>
        </div>

        <p class="text-[10px] text-gray-400">点击测试会调用后端真实网关探测接口，结果来自服务端返回。</p>

        <div class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-[10px] text-zinc-400 space-y-2 overflow-y-auto min-h-[180px]">
          <div v-for="(log, idx) in testLogs" :key="idx" class="flex items-start space-x-1.5">
            <span class="text-emerald-500">&gt;</span>
            <span class="leading-normal">{{ log }}</span>
          </div>
          <div v-if="testingConnection" class="flex items-center space-x-1.5 text-zinc-600">
            <RefreshCw class="w-3 h-3 animate-spin" />
            <span>等待后端真实检测结果...</span>
          </div>
          <div v-if="testStatus === 'idle' && !testingConnection && testLogs.length === 0" class="text-zinc-600 italic py-12 text-center">
            暂无诊断记录。
          </div>
        </div>

        <div
          v-if="testStatus !== 'idle'"
          class="p-3.5 rounded-lg border text-xs leading-normal flex items-start space-x-2"
          :class="testStatus === 'success'
            ? 'bg-emerald-50/30 border-emerald-100/30 text-emerald-800 dark:bg-emerald-950/10 dark:border-emerald-900/20 dark:text-emerald-400'
            : 'bg-red-50/30 border-red-100/30 text-red-800 dark:bg-red-950/10 dark:border-red-900/20 dark:text-red-400'"
        >
          <CheckCircle2 v-if="testStatus === 'success'" class="w-4 h-4 text-emerald-600 dark:text-emerald-400 mt-0.5 flex-shrink-0" />
          <ShieldAlert v-else class="w-4 h-4 text-red-600 dark:text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <span class="font-bold block">{{ testStatus === 'success' ? '诊断结果：连接成功' : '诊断结果：连接失败' }}</span>
            <p class="text-[10px] mt-0.5 text-gray-500 dark:text-zinc-400">
              {{ testStatus === 'success' ? '后端已经完成真实网关健康检查。' : '请检查服务器网络、Base URL 和 API Key。' }}
            </p>
          </div>
        </div>
      </div>

      <button
        @click="handleTestGateway"
        :disabled="testingConnection"
        class="w-full flex items-center justify-center space-x-1.5 py-2.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-100 border border-zinc-700 dark:bg-zinc-950 dark:hover:bg-zinc-900 dark:border-zinc-800 rounded-lg text-xs font-semibold focus:outline-none disabled:opacity-50"
      >
        <Play class="w-3.5 h-3.5 fill-current" />
        <span>{{ testingConnection ? '测试中' : '开始测试连接' }}</span>
      </button>
    </div>
  </div>
</template>
