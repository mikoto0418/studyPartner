<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Megaphone, Pin, RefreshCw, Send } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { announcementApi, type Announcement } from '../../api/modules/announcement'

const announcements = ref<Announcement[]>([])
const loading = ref(false)
const publishing = ref(false)

const form = ref({
  title: '',
  content: '',
  target_type: 'all_students' as 'all' | 'all_students' | 'all_teachers' | 'specific_users',
  is_pinned: false
})

const loadAnnouncements = async () => {
  loading.value = true
  try {
    const res = await announcementApi.listAnnouncements()
    announcements.value = res.data || []
  } catch (error) {
    console.warn('Failed to load announcements', error)
    announcements.value = []
  } finally {
    loading.value = false
  }
}

const createAnnouncement = async () => {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    ElMessage.warning('请填写公告标题和正文')
    return
  }

  publishing.value = true
  try {
    await announcementApi.createAnnouncement({
      title: form.value.title.trim(),
      content: form.value.content.trim(),
      status: 'published',
      target_type: form.value.target_type,
      is_pinned: form.value.is_pinned
    })
    form.value = { title: '', content: '', target_type: 'all_students', is_pinned: false }
    ElMessage.success('公告已发布，并同步生成通知')
    await loadAnnouncements()
  } catch (error) {
    console.warn('Failed to publish announcement', error)
  } finally {
    publishing.value = false
  }
}

const targetLabel = (targetType: string) => {
  const labels: Record<string, string> = {
    all: '全部用户',
    all_students: '全部学生',
    all_teachers: '全部老师',
    specific_users: '指定用户'
  }
  return labels[targetType] || targetType
}

const formatTime = (iso?: string) => {
  if (!iso) return '-'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  loadAnnouncements()
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
    <section class="lg:col-span-5 minimal-card p-6 bg-white dark:bg-zinc-900 space-y-5">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
          <Megaphone class="w-4 h-4 text-blue-600" />
          发布公告
        </h3>
        <span class="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
          通知同步
        </span>
      </div>

      <div class="space-y-4 text-xs">
        <label class="space-y-1.5 block">
          <span class="text-gray-500 font-medium">标题</span>
          <input v-model="form.title" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </label>
        <label class="space-y-1.5 block">
          <span class="text-gray-500 font-medium">正文</span>
          <textarea v-model="form.content" rows="6" class="w-full resize-none rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"></textarea>
        </label>
        <label class="space-y-1.5 block">
          <span class="text-gray-500 font-medium">接收范围</span>
          <select v-model="form.target_type" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950">
            <option value="all_students">全部学生</option>
            <option value="all_teachers">全部老师</option>
            <option value="all">全部用户</option>
          </select>
        </label>
        <label class="inline-flex items-center gap-2 text-gray-500">
          <input v-model="form.is_pinned" type="checkbox" class="rounded border-gray-300" />
          <span>置顶公告</span>
        </label>
      </div>

      <button
        @click="createAnnouncement"
        :disabled="publishing"
        class="inline-flex w-full items-center justify-center gap-1.5 rounded bg-blue-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
      >
        <Send class="w-3.5 h-3.5" />
        <span>{{ publishing ? '发布中' : '发布公告' }}</span>
      </button>
    </section>

    <section class="lg:col-span-7 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-[640px]">
      <div class="mb-4 flex items-center justify-between border-b border-gray-100 pb-3 dark:border-zinc-800">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">公告记录</h3>
        <button @click="loadAnnouncements" :disabled="loading" class="inline-flex items-center gap-1 rounded px-2 py-1 text-[10px] font-semibold text-gray-500 hover:bg-gray-50 dark:hover:bg-zinc-800 disabled:opacity-50">
          <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin' : ''" />
          <span>刷新</span>
        </button>
      </div>

      <div class="flex-1 overflow-y-auto space-y-3 pr-1">
        <article
          v-for="item in announcements"
          :key="item.id"
          class="rounded border border-gray-100 bg-gray-50/40 p-4 text-xs dark:border-zinc-800 dark:bg-zinc-950/20"
        >
          <div class="mb-2 flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h4 class="font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-1.5">
                <Pin v-if="item.is_pinned" class="w-3.5 h-3.5 text-amber-500" />
                <span class="truncate">{{ item.title }}</span>
              </h4>
              <p class="mt-1 text-[10px] text-gray-400">{{ targetLabel(item.target_type) }} · {{ formatTime(item.created_at) }}</p>
            </div>
            <span class="rounded px-2 py-0.5 text-[10px] font-mono" :class="item.status === 'published' ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'">
              {{ item.status }}
            </span>
          </div>
          <p class="whitespace-pre-wrap leading-relaxed text-gray-600 dark:text-zinc-300">{{ item.content }}</p>
        </article>

        <div v-if="announcements.length === 0" class="flex h-full items-center justify-center text-xs text-gray-400">
          暂无公告记录。
        </div>
      </div>
    </section>
  </div>
</template>
