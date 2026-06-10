<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Activity,
  CheckCircle2,
  Cpu,
  Database,
  Key,
  MessageSquare,
  Play,
  RefreshCw,
  ShieldAlert
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { adminApi, type LLMProviderConfigOut } from '../../api/modules/admin'

const providerName = ref('siliconflow')
const displayName = ref('SiliconFlow')
const enabled = ref(true)
const rpmLimit = ref<number | undefined>()
const tpmLimit = ref<number | undefined>()

const chatBaseUrl = ref('https://api.siliconflow.cn/v1')
const chatApiKey = ref('')
const showChatApiKey = ref(false)
const chatModel = ref('deepseek-ai/DeepSeek-V4-Flash')

const embeddingBaseUrl = ref('https://api.siliconflow.cn/v1')
const embeddingApiKey = ref('')
const showEmbeddingApiKey = ref(false)
const embeddingModel = ref('BAAI/bge-m3')

const loading = ref(false)
const saving = ref(false)
const testingTarget = ref<'chat' | 'embedding' | null>(null)
const testLogs = ref<string[]>([])
const testLatency = ref<number | null>(null)
const testStatus = ref<'idle' | 'success' | 'failed'>('idle')
const configs = ref<LLMProviderConfigOut[]>([])

const chatTasks = [
  { value: 'student_chat', label: '学生伴学对话' },
  { value: 'teacher_assistant', label: '教师智能助教' },
  { value: 'daily_review', label: '每日自动复盘' },
  { value: 'memory_extract', label: '学情记忆提取' },
  { value: 'memory_update', label: '学情记忆更新' },
  { value: 'knowledge_qa', label: '知识库问答' },
  { value: 'learning_path_generate', label: '学习路径生成' },
  { value: 'document_summary', label: '文档摘要' }
]

const taskTypes = [
  ...chatTasks.map((task) => ({ ...task, channel: '对话通道' })),
  { value: 'knowledge_embedding', label: '知识库向量嵌入', channel: '嵌入通道' }
]

const chatConfigs = computed(() => configs.value.filter((item) => item.task_type !== 'knowledge_embedding'))
const embeddingConfig = computed(() => configs.value.find((item) => item.task_type === 'knowledge_embedding'))
const hasExistingChatKey = computed(() => chatConfigs.value.some((item) => item.has_api_key))
const hasExistingEmbeddingKey = computed(() => Boolean(embeddingConfig.value?.has_api_key))
const testingConnection = computed(() => testingTarget.value !== null)

const taskRows = computed(() =>
  taskTypes.map((task) => {
    const config = configs.value.find((item) => item.task_type === task.value)
    const isEmbedding = task.value === 'knowledge_embedding'
    return {
      ...task,
      model: config?.model_name || (isEmbedding ? embeddingModel.value : chatModel.value),
      baseUrl: config?.base_url || (isEmbedding ? embeddingBaseUrl.value : chatBaseUrl.value),
      enabled: config?.enabled ?? enabled.value,
      rpm: config?.rpm_limit,
      hasKey: config?.has_api_key ?? (isEmbedding ? hasExistingEmbeddingKey.value : hasExistingChatKey.value)
    }
  })
)

const loadConfigs = async () => {
  loading.value = true
  try {
    const res = await adminApi.listLlmConfigs()
    configs.value = res.data || []
    const firstConfig = configs.value[0]
    const firstChatConfig = chatConfigs.value[0]
    const embedding = embeddingConfig.value

    const displayConfig = firstChatConfig || embedding || firstConfig
    if (displayConfig) {
      providerName.value = displayConfig.provider_name
      displayName.value = displayConfig.display_name || displayConfig.provider_name
      enabled.value = displayConfig.enabled
      rpmLimit.value = displayConfig.rpm_limit
      tpmLimit.value = displayConfig.tpm_limit
    }
    if (firstChatConfig) {
      chatBaseUrl.value = firstChatConfig.base_url
      chatModel.value = firstChatConfig.model_name
    }
    if (embedding) {
      embeddingBaseUrl.value = embedding.base_url
      embeddingModel.value = embedding.model_name
    }
  } catch (error) {
    console.warn('加载模型配置失败', error)
    configs.value = []
  } finally {
    loading.value = false
  }
}

const handleSaveConfig = async () => {
  if (!chatBaseUrl.value.trim() || !embeddingBaseUrl.value.trim() || !chatModel.value.trim() || !embeddingModel.value.trim()) {
    ElMessage.warning('请分别填写对话模型和嵌入模型的 Base URL 与模型名')
    return
  }
  if (!chatApiKey.value.trim() && !hasExistingChatKey.value) {
    ElMessage.warning('首次保存对话模型配置必须填写对话 API Key')
    return
  }
  if (!embeddingApiKey.value.trim() && !hasExistingEmbeddingKey.value) {
    ElMessage.warning('首次保存嵌入模型配置必须填写嵌入 API Key')
    return
  }

  saving.value = true
  try {
    const payload = {
      provider_name: providerName.value,
      display_name: displayName.value,
      chat_base_url: chatBaseUrl.value.trim(),
      chat_model: chatModel.value.trim(),
      embedding_base_url: embeddingBaseUrl.value.trim(),
      embedding_model: embeddingModel.value.trim(),
      task_types: chatTasks.map((item) => item.value),
      enabled: enabled.value,
      rpm_limit: rpmLimit.value,
      tpm_limit: tpmLimit.value,
      ...(chatApiKey.value.trim() ? { chat_api_key: chatApiKey.value.trim() } : {}),
      ...(embeddingApiKey.value.trim() ? { embedding_api_key: embeddingApiKey.value.trim() } : {})
    }
    const res = await adminApi.saveLlmConfigs(payload)
    configs.value = res.data || []
    chatApiKey.value = ''
    embeddingApiKey.value = ''
    ElMessage.success('模型通道配置已保存')
    await loadConfigs()
  } catch (error) {
    console.warn('保存模型配置失败', error)
  } finally {
    saving.value = false
  }
}

const handleTestGateway = async (target: 'chat' | 'embedding') => {
  const apiKey = target === 'chat' ? chatApiKey.value.trim() : embeddingApiKey.value.trim()
  if (!apiKey) {
    ElMessage.warning(target === 'chat' ? '请先输入本次要测试的对话 API Key' : '请先输入本次要测试的嵌入 API Key')
    return
  }

  testingTarget.value = target
  testStatus.value = 'idle'
  testLatency.value = null
  testLogs.value = [
    target === 'chat'
      ? '正在测试对话模型通道，会真实调用当前模型。'
      : '正在测试嵌入模型通道，会真实生成一条测试向量。'
  ]

  try {
    const res = await adminApi.testLlmConnection({
      provider_name: providerName.value,
      base_url: target === 'chat' ? chatBaseUrl.value.trim() : embeddingBaseUrl.value.trim(),
      api_key: apiKey,
      model_name: target === 'chat' ? chatModel.value.trim() : embeddingModel.value.trim(),
      endpoint_type: target
    })
    testLatency.value = res.data?.latency_ms ?? null
    testLogs.value.push(`测试成功，模型：${res.data?.model_name || (target === 'chat' ? chatModel.value : embeddingModel.value)}`)
    testStatus.value = 'success'
    ElMessage.success(target === 'chat' ? '对话模型通道测试成功' : '嵌入模型通道测试成功')
  } catch (error) {
    testLogs.value.push('测试失败，请检查 Base URL、API Key、模型名和服务商网络连通性。')
    testStatus.value = 'failed'
    console.warn('模型通道测试失败', error)
  } finally {
    testingTarget.value = null
  }
}

onMounted(() => {
  loadConfigs()
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
    <div class="lg:col-span-8 flex flex-col gap-6">
      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 space-y-5">
        <div class="flex items-center justify-between gap-4">
          <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Key class="w-4 h-4 text-blue-600" />
            <span>模型通道配置</span>
          </h3>
          <button
            @click="handleSaveConfig"
            :disabled="saving"
            class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded text-[10px] font-bold shadow-sm disabled:opacity-50"
          >
            {{ saving ? '保存中' : '保存配置' }}
          </button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">服务商</span>
            <input v-model="providerName" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">显示名称</span>
            <input v-model="displayName" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="flex items-center gap-2 pt-6 text-gray-600 dark:text-zinc-300">
            <input v-model="enabled" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            <span>启用这些模型通道</span>
          </label>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <section class="rounded-lg border border-blue-100 dark:border-blue-950/60 bg-blue-50/30 dark:bg-blue-950/10 p-4 space-y-4">
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
                <MessageSquare class="w-4 h-4 text-blue-600" />
                <span>对话 / 推理模型</span>
              </h4>
              <span class="text-[10px] text-gray-400">聊天、总结、路径生成</span>
            </div>
            <label class="space-y-1.5 block text-xs">
              <span class="text-gray-500 font-medium block">对话 Base URL</span>
              <input v-model="chatBaseUrl" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
            </label>
            <label class="space-y-1.5 block text-xs">
              <span class="text-gray-500 font-medium block">对话模型名</span>
              <input v-model="chatModel" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
            </label>
            <div class="space-y-1.5 text-xs">
              <label class="text-gray-500 font-medium block">对话 API Key</label>
              <div class="flex items-center space-x-2">
                <input
                  v-model="chatApiKey"
                  :type="showChatApiKey ? 'text' : 'password'"
                  placeholder="留空表示沿用已保存密钥"
                  class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 text-gray-800 dark:text-zinc-100 font-mono rounded focus:outline-none focus:border-blue-500"
                />
                <button @click="showChatApiKey = !showChatApiKey" class="px-2.5 py-2 border border-gray-200 dark:border-zinc-800 rounded bg-white hover:bg-gray-50 dark:bg-zinc-900 text-[10px] font-medium">
                  {{ showChatApiKey ? '隐藏' : '显示' }}
                </button>
              </div>
              <p class="text-[10px] text-gray-400">{{ hasExistingChatKey ? '已保存对话密钥。页面不会回显密钥明文。' : '未保存对话密钥，首次保存必须填写。' }}</p>
            </div>
          </section>

          <section class="rounded-lg border border-emerald-100 dark:border-emerald-950/60 bg-emerald-50/30 dark:bg-emerald-950/10 p-4 space-y-4">
            <div class="flex items-center justify-between gap-3">
              <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
                <Database class="w-4 h-4 text-emerald-600" />
                <span>嵌入 / 向量模型</span>
              </h4>
              <span class="text-[10px] text-gray-400">知识库检索向量</span>
            </div>
            <label class="space-y-1.5 block text-xs">
              <span class="text-gray-500 font-medium block">嵌入 Base URL</span>
              <input v-model="embeddingBaseUrl" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 rounded focus:outline-none focus:border-emerald-500" />
            </label>
            <label class="space-y-1.5 block text-xs">
              <span class="text-gray-500 font-medium block">嵌入模型名</span>
              <input v-model="embeddingModel" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 rounded focus:outline-none focus:border-emerald-500" />
            </label>
            <div class="space-y-1.5 text-xs">
              <label class="text-gray-500 font-medium block">嵌入 API Key</label>
              <div class="flex items-center space-x-2">
                <input
                  v-model="embeddingApiKey"
                  :type="showEmbeddingApiKey ? 'text' : 'password'"
                  placeholder="留空表示沿用已保存密钥"
                  class="flex-1 px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 text-gray-800 dark:text-zinc-100 font-mono rounded focus:outline-none focus:border-emerald-500"
                />
                <button @click="showEmbeddingApiKey = !showEmbeddingApiKey" class="px-2.5 py-2 border border-gray-200 dark:border-zinc-800 rounded bg-white hover:bg-gray-50 dark:bg-zinc-900 text-[10px] font-medium">
                  {{ showEmbeddingApiKey ? '隐藏' : '显示' }}
                </button>
              </div>
              <p class="text-[10px] text-gray-400">{{ hasExistingEmbeddingKey ? '已保存嵌入密钥。页面不会回显密钥明文。' : '未保存嵌入密钥，首次保存必须填写。' }}</p>
            </div>
          </section>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">每分钟请求上限</span>
            <input v-model.number="rpmLimit" type="number" min="0" placeholder="不填表示不限制" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
          <label class="space-y-1.5">
            <span class="text-gray-500 font-medium block">每分钟 Token 上限</span>
            <input v-model.number="tpmLimit" type="number" min="0" placeholder="不填表示不限制" class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500" />
          </label>
        </div>
      </div>

      <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-1 flex flex-col">
        <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 mb-3 flex items-center space-x-1.5">
          <Cpu class="w-4 h-4 text-purple-600" />
          <span>子任务模型映射</span>
        </h3>

        <div class="flex-1 overflow-x-auto">
          <table class="w-full text-left text-xs border-collapse">
            <thead>
              <tr class="border-b border-gray-100 dark:border-zinc-800 text-gray-400">
                <th class="py-2.5 font-medium">任务类型</th>
                <th class="py-2.5 font-medium">通道</th>
                <th class="py-2.5 font-medium">模型</th>
                <th class="py-2.5 font-medium">Base URL</th>
                <th class="py-2.5 font-medium">状态</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-50 dark:divide-zinc-800/50">
              <tr v-for="item in taskRows" :key="item.value" class="text-gray-600 dark:text-zinc-300">
                <td class="py-3 font-semibold">{{ item.label }} <span class="font-mono text-[9px] text-gray-400">({{ item.value }})</span></td>
                <td class="py-3 text-[10px] text-gray-500">{{ item.channel }}</td>
                <td class="py-3 font-mono text-[10px] text-gray-500 dark:text-zinc-400">{{ item.model }}</td>
                <td class="py-3 font-mono text-[10px] text-gray-400 max-w-[220px] truncate">{{ item.baseUrl }}</td>
                <td class="py-3">
                  <span class="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold" :class="item.enabled && item.hasKey ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400' : 'bg-gray-100 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400'">
                    {{ item.enabled && item.hasKey ? '已启用' : '未配置' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="loading" class="py-8 text-center text-xs text-gray-400">正在加载配置...</div>
        </div>
      </div>
    </div>

    <div class="lg:col-span-4 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-full justify-between gap-6 min-h-[400px]">
      <div class="space-y-4 flex-1 flex flex-col">
        <div class="pb-3 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between">
          <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
            <Activity class="w-4 h-4 text-emerald-500" />
            <span>模型通道自检</span>
          </h3>
          <span v-if="testStatus === 'success'" class="text-[9px] bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 px-2 py-0.5 rounded font-mono font-bold">
            延迟 {{ testLatency }}ms
          </span>
        </div>

        <p class="text-[10px] text-gray-400">测试会由后端发起真实请求，分别验证对话接口和向量接口。</p>

        <div class="flex-1 bg-zinc-950 border border-zinc-800 rounded-lg p-4 font-mono text-[10px] text-zinc-400 space-y-2 overflow-y-auto min-h-[180px]">
          <div v-for="(log, idx) in testLogs" :key="idx" class="flex items-start space-x-1.5">
            <span class="text-emerald-500">&gt;</span>
            <span class="leading-normal">{{ log }}</span>
          </div>
          <div v-if="testingConnection" class="flex items-center space-x-1.5 text-zinc-600">
            <RefreshCw class="w-3 h-3 animate-spin" />
            <span>{{ testingTarget === 'chat' ? '等待对话通道测试结果...' : '等待嵌入通道测试结果...' }}</span>
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
              {{ testStatus === 'success' ? '后端已经完成真实模型接口调用。' : '请检查 Base URL、API Key、模型名和网络连通性。' }}
            </p>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          @click="handleTestGateway('chat')"
          :disabled="testingConnection"
          class="w-full flex items-center justify-center space-x-1.5 py-2.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-100 border border-zinc-700 dark:bg-zinc-950 dark:hover:bg-zinc-900 dark:border-zinc-800 rounded-lg text-xs font-semibold focus:outline-none disabled:opacity-50"
        >
          <Play class="w-3.5 h-3.5 fill-current" />
          <span>{{ testingTarget === 'chat' ? '测试中' : '测试对话' }}</span>
        </button>
        <button
          @click="handleTestGateway('embedding')"
          :disabled="testingConnection"
          class="w-full flex items-center justify-center space-x-1.5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-500 rounded-lg text-xs font-semibold focus:outline-none disabled:opacity-50"
        >
          <Play class="w-3.5 h-3.5 fill-current" />
          <span>{{ testingTarget === 'embedding' ? '测试中' : '测试嵌入' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>
