<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Database, Mail, RefreshCw, Settings, ShieldCheck } from 'lucide-vue-next'
import { adminApi, type AdminRuntimeSettingsOut } from '../../api/modules/admin'

const settingsData = ref<AdminRuntimeSettingsOut | null>(null)
const loading = ref(false)

const loadSettings = async () => {
  loading.value = true
  try {
    const res = await adminApi.getSettings()
    settingsData.value = res.data
  } catch (error) {
    console.warn('Failed to load admin settings', error)
    settingsData.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>

<template>
  <div class="space-y-6">
    <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex items-center justify-between">
      <div class="space-y-1">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
          <Settings class="w-4 h-4 text-blue-600" />
          系统常规设置
        </h3>
        <p class="text-xs text-gray-400">当前页面展示服务端运行配置摘要，敏感配置仅显示状态。</p>
      </div>
      <button
        @click="loadSettings"
        :disabled="loading"
        class="inline-flex items-center gap-1.5 rounded bg-zinc-900 px-3 py-2 text-xs font-semibold text-zinc-100 disabled:opacity-50"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
        <span>{{ loading ? '刷新中' : '刷新' }}</span>
      </button>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="minimal-card p-5 bg-white dark:bg-zinc-900 space-y-4">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center gap-1.5">
            <ShieldCheck class="w-4 h-4 text-emerald-600" />
            运行环境
          </h4>
          <span class="rounded px-2 py-0.5 text-[10px] font-mono" :class="settingsData?.app_debug ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'">
            {{ settingsData?.app_debug ? 'debug' : 'release' }}
          </span>
        </div>
        <div class="space-y-2 text-xs text-gray-500 dark:text-zinc-400">
          <div class="flex justify-between"><span>APP_ENV</span><span class="font-mono">{{ settingsData?.app_env || '-' }}</span></div>
          <div class="flex justify-between"><span>内置调度器</span><span class="font-mono">{{ settingsData?.inline_scheduler_enabled ? 'enabled' : 'disabled' }}</span></div>
        </div>
      </div>

      <div class="minimal-card p-5 bg-white dark:bg-zinc-900 space-y-4">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center gap-1.5">
            <Mail class="w-4 h-4 text-blue-600" />
            SMTP 邮件
          </h4>
          <span class="rounded px-2 py-0.5 text-[10px] font-mono" :class="settingsData?.smtp_configured ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'">
            {{ settingsData?.smtp_configured ? 'configured' : 'missing' }}
          </span>
        </div>
        <div class="space-y-2 text-xs text-gray-500 dark:text-zinc-400">
          <div class="flex justify-between"><span>SMTP_HOST</span><span class="font-mono">{{ settingsData?.smtp_host || '-' }}</span></div>
          <div class="flex justify-between"><span>FROM_EMAIL</span><span class="font-mono">{{ settingsData?.smtp_from_email || '-' }}</span></div>
        </div>
      </div>

      <div class="minimal-card p-5 bg-white dark:bg-zinc-900 space-y-4">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center gap-1.5">
            <Database class="w-4 h-4 text-purple-600" />
            外部服务
          </h4>
          <span class="rounded bg-purple-50 px-2 py-0.5 text-[10px] font-mono text-purple-700">
            runtime
          </span>
        </div>
        <div class="space-y-2 text-xs text-gray-500 dark:text-zinc-400">
          <div class="flex justify-between gap-4"><span>MinIO</span><span class="font-mono truncate">{{ settingsData?.minio_endpoint || '-' }}</span></div>
          <div class="flex justify-between gap-4"><span>Bucket</span><span class="font-mono truncate">{{ settingsData?.minio_bucket_name || '-' }}</span></div>
          <div class="flex justify-between gap-4"><span>Qdrant</span><span class="font-mono truncate">{{ settingsData?.qdrant_endpoint || '-' }}</span></div>
        </div>
      </div>
    </div>

    <div class="minimal-card p-6 bg-white dark:bg-zinc-900">
      <h4 class="mb-4 text-xs font-bold text-gray-900 dark:text-zinc-50">模型通道状态</h4>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
        <div class="rounded border border-gray-100 dark:border-zinc-800 px-4 py-3 flex justify-between">
          <span class="text-gray-500">已登记通道数</span>
          <span class="font-mono font-semibold">{{ settingsData?.llm_provider_count ?? 0 }}</span>
        </div>
        <div class="rounded border border-gray-100 dark:border-zinc-800 px-4 py-3 flex justify-between">
          <span class="text-gray-500">启用通道数</span>
          <span class="font-mono font-semibold">{{ settingsData?.enabled_llm_provider_count ?? 0 }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
