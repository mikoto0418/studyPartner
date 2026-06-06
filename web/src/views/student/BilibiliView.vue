<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileVideo,
  PauseCircle,
  Play,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bilibiliApi } from '../../api/modules/bilibili'
import type {
  BilibiliMetaOut,
  BilibiliResourceOut,
  BilibiliStreamInfo,
  BilibiliWatchStatOut,
} from '../../api/modules/bilibili'

const resources = ref<BilibiliResourceOut[]>([])
const keyword = ref('')
const activeResource = ref<BilibiliResourceOut | null>(null)
const currentEpisode = ref(1)
const showBackupPlayer = ref(false)
const nativeStream = ref<BilibiliStreamInfo | null>(null)
const streamLoading = ref(false)
const streamError = ref('')
const playerReloadKey = ref(0)

const importDialogVisible = ref(false)
const recognizingMeta = ref(false)
const importForm = ref({
  bvid: '',
  title: '',
  description: '',
  cover_url: '',
  author_name: '',
  total_episodes: 1,
  total_duration: undefined as number | undefined,
  episodes_info: [] as any[],
  category: '学术网课',
  is_shared: true,
})

const totalSessionWatchTime = ref(0)
const watchTimeInCurrentPeriod = ref(0)
const pauseCountInSession = ref(0)
const watchStats = ref<BilibiliWatchStatOut[]>([])
let secondsTimer: ReturnType<typeof setInterval> | null = null
let watchTimer: ReturnType<typeof setInterval> | null = null

const bilibiliEmbedSrc = computed(() => {
  if (!activeResource.value) return ''
  const params = new URLSearchParams({
    bvid: activeResource.value.bvid,
    p: String(currentEpisode.value),
    autoplay: '0',
    high_quality: '1',
    danmaku: '0',
    isOutside: 'true',
  })
  return `https://player.bilibili.com/player.html?${params.toString()}`
})

const nativeVideoSrc = computed(() => {
  if (!nativeStream.value?.src) return ''
  const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
  return `${baseUrl.replace(/\/$/, '')}${nativeStream.value.src}`
})

const activeEpisodeInfo = computed(() => {
  const info = activeResource.value?.episodes_info?.[currentEpisode.value - 1]
  return info || null
})

function normalizeBvid(input: string) {
  const match = input.trim().match(/BV[0-9A-Za-z]+/)
  return match ? match[0] : input.trim()
}

function formatWatchTime(seconds: number) {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

function formatMinutes(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}

function formatClock(iso: string) {
  const date = new Date(iso)
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function episodeLabel(ep: number) {
  const info = activeResource.value?.episodes_info?.[ep - 1]
  const title = info?.part || info?.title
  return title ? `第 ${ep} P · ${title}` : `第 ${ep} P 课程`
}

function resetImportForm() {
  importForm.value = {
    bvid: '',
    title: '',
    description: '',
    cover_url: '',
    author_name: '',
    total_episodes: 1,
    total_duration: undefined,
    episodes_info: [],
    category: '学术网课',
    is_shared: true,
  }
}

function resumeKey() {
  if (!activeResource.value) return ''
  return `study_partner:bilibili:${activeResource.value.id}:${currentEpisode.value}`
}

function startLocalTiming() {
  if (secondsTimer) return
  secondsTimer = setInterval(() => {
    totalSessionWatchTime.value += 1
    watchTimeInCurrentPeriod.value += 1
  }, 1000)
}

function stopLocalTiming() {
  if (secondsTimer) {
    clearInterval(secondsTimer)
    secondsTimer = null
  }
}

function startHeartbeat() {
  if (!activeResource.value || watchTimer) return
  watchTimer = setInterval(async () => {
    if (!activeResource.value) return
    const duration = watchTimeInCurrentPeriod.value
    if (duration <= 0) return
    watchTimeInCurrentPeriod.value = 0
    try {
      await bilibiliApi.logWatchEvent({
        resource_id: activeResource.value.id,
        event_type: 'heartbeat',
        episode_number: currentEpisode.value,
        watch_duration: duration,
      })
      loadWatchStats()
    } catch (error) {
      // Keep local timer alive even when telemetry fails.
    }
  }, 30000)
}

function stopHeartbeat() {
  if (watchTimer) {
    clearInterval(watchTimer)
    watchTimer = null
  }
}

async function loadResources() {
  try {
    const res = await bilibiliApi.listResources({ keyword: keyword.value.trim() || undefined })
    resources.value = res.data || []
  } catch (error) {
    resources.value = []
  }
}

async function loadWatchStats() {
  if (!activeResource.value) return
  try {
    const res = await bilibiliApi.getStats({ resource_id: activeResource.value.id, limit: 12 })
    watchStats.value = res.data || []
  } catch (error) {
    watchStats.value = []
  }
}

async function recognizeBilibiliMeta() {
  const bvid = normalizeBvid(importForm.value.bvid)
  if (!bvid) {
    ElMessage.warning('请先输入 BV 号或 B站链接')
    return
  }

  recognizingMeta.value = true
  importForm.value.bvid = bvid
  try {
    const res = await bilibiliApi.getMeta(bvid)
    const meta = res.data as BilibiliMetaOut
    importForm.value.title = meta.title || importForm.value.title
    importForm.value.description = meta.description || ''
    importForm.value.cover_url = meta.cover_url || ''
    importForm.value.author_name = meta.author_name || ''
    importForm.value.total_episodes = meta.total_episodes || 1
    importForm.value.total_duration = meta.total_duration
    importForm.value.episodes_info = meta.episodes_info || []
    ElMessage.success('已识别视频信息')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '识别失败，请确认 BV 号有效')
  } finally {
    recognizingMeta.value = false
  }
}

async function handleImport() {
  const bvid = normalizeBvid(importForm.value.bvid)
  if (!bvid) {
    ElMessage.warning('请输入 BV 号或 B站链接')
    return
  }
  if (!importForm.value.title.trim()) {
    await recognizeBilibiliMeta()
  }
  if (!importForm.value.title.trim()) {
    ElMessage.warning('请填写视频标题')
    return
  }

  try {
    await bilibiliApi.addResource({
      bvid,
      title: importForm.value.title.trim(),
      description: importForm.value.description.trim() || undefined,
      cover_url: importForm.value.cover_url || undefined,
      author_name: importForm.value.author_name.trim() || undefined,
      total_episodes: Math.max(1, Number(importForm.value.total_episodes) || 1),
      total_duration: importForm.value.total_duration,
      category: importForm.value.category,
      episodes_info: importForm.value.episodes_info,
      is_shared: importForm.value.is_shared,
    })
    ElMessage.success('B站资源已导入')
    importDialogVisible.value = false
    resetImportForm()
    loadResources()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '导入失败')
  }
}

async function handleDelete(item: BilibiliResourceOut) {
  try {
    await ElMessageBox.confirm(`确定删除「${item.title}」吗？`, '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await bilibiliApi.deleteResource(item.id)
    ElMessage.success('资源已删除')
    loadResources()
  } catch (error) {
    // user cancelled or request failed
  }
}

async function loadNativeStream() {
  if (!activeResource.value) return
  streamLoading.value = true
  streamError.value = ''
  nativeStream.value = null
  try {
    const res = await bilibiliApi.getStreamInfo({
      bvid: activeResource.value.bvid,
      episode: currentEpisode.value,
    })
    nativeStream.value = res.data
  } catch (error: any) {
    streamError.value = error.response?.data?.message || error.message || '备用视频源解析失败'
  } finally {
    streamLoading.value = false
  }
}

async function enterRoom(resource: BilibiliResourceOut) {
  activeResource.value = resource
  currentEpisode.value = 1
  showBackupPlayer.value = false
  nativeStream.value = null
  streamError.value = ''
  playerReloadKey.value = 0
  totalSessionWatchTime.value = 0
  watchTimeInCurrentPeriod.value = 0
  pauseCountInSession.value = 0
  watchStats.value = []

  startLocalTiming()
  startHeartbeat()
  bilibiliApi.logWatchEvent({
    resource_id: resource.id,
    event_type: 'open',
    episode_number: currentEpisode.value,
    watch_duration: 0,
  }).catch(() => {})
  loadWatchStats()
}

async function leaveRoom() {
  if (!activeResource.value) return
  stopLocalTiming()
  stopHeartbeat()

  const resource = activeResource.value
  const duration = Math.max(1, watchTimeInCurrentPeriod.value)
  watchTimeInCurrentPeriod.value = 0
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: resource.id,
      event_type: 'close',
      episode_number: currentEpisode.value,
      watch_duration: duration,
    })
  } catch (error) {
    // best effort close event
  }

  activeResource.value = null
  showBackupPlayer.value = false
  nativeStream.value = null
  streamError.value = ''
  loadResources()
}

function selectEmbeddedPlayer() {
  showBackupPlayer.value = false
}

async function selectBackupPlayer() {
  showBackupPlayer.value = true
  if (!nativeStream.value && !streamLoading.value) {
    await loadNativeStream()
  }
}

async function handleEpisodeChange(ep: number) {
  if (!activeResource.value || ep === currentEpisode.value) return
  const previousDuration = Math.max(1, watchTimeInCurrentPeriod.value)
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value.id,
      event_type: 'close',
      episode_number: currentEpisode.value,
      watch_duration: previousDuration,
    })
  } catch (error) {
    // best effort
  }

  currentEpisode.value = ep
  watchTimeInCurrentPeriod.value = 0
  playerReloadKey.value += 1
  nativeStream.value = null
  streamError.value = ''
  if (showBackupPlayer.value) await loadNativeStream()

  bilibiliApi.logWatchEvent({
    resource_id: activeResource.value.id,
    event_type: 'open',
    episode_number: currentEpisode.value,
    watch_duration: 0,
  }).catch(() => {})
  loadWatchStats()
}

async function handleManualComplete() {
  if (!activeResource.value) return
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value.id,
      event_type: 'manual_complete',
      episode_number: currentEpisode.value,
      is_completed: true,
      watch_duration: Math.max(0, watchTimeInCurrentPeriod.value),
    })
    ElMessage.success('已标记本资源学完')
    loadWatchStats()
  } catch (error) {
    ElMessage.error('标记失败')
  }
}

function handleNativeLoadedMetadata(event: Event) {
  const video = event.target as HTMLVideoElement
  const saved = Number(localStorage.getItem(resumeKey()) || 0)
  if (saved > 3 && Number.isFinite(saved) && (!video.duration || saved < video.duration - 3)) {
    video.currentTime = saved
  }
}

function handleNativeTimeUpdate(event: Event) {
  const video = event.target as HTMLVideoElement
  if (video.currentTime > 0) {
    localStorage.setItem(resumeKey(), video.currentTime.toFixed(1))
  }
}

function handleNativePlay() {
  startLocalTiming()
}

async function handleNativePause() {
  if (!activeResource.value) return
  stopLocalTiming()
  pauseCountInSession.value += 1
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value.id,
      event_type: 'pause',
      episode_number: currentEpisode.value,
      watch_duration: Math.max(0, watchTimeInCurrentPeriod.value),
    })
    watchTimeInCurrentPeriod.value = 0
    loadWatchStats()
  } catch (error) {
    // pause telemetry is best effort
  }
}

function reloadBackupPlayer() {
  playerReloadKey.value += 1
  nativeStream.value = null
  loadNativeStream()
}

function reloadEmbeddedPlayer() {
  playerReloadKey.value += 1
}

onMounted(() => {
  loadResources()
})

onUnmounted(() => {
  stopLocalTiming()
  stopHeartbeat()
})
</script>

<template>
  <div class="space-y-6">
    <div v-if="!activeResource" class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
      <div>
        <p class="text-xs text-gray-400 dark:text-zinc-500">导入 B站课程资源，学习记录会沉淀到个人统计。</p>
      </div>

      <div class="flex items-center gap-3">
        <div class="relative w-64">
          <Search class="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
          <input
            v-model="keyword"
            @keyup.enter="loadResources"
            type="text"
            placeholder="搜索视频资源"
            class="w-full rounded-lg border border-gray-200 bg-white py-2 pl-9 pr-4 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-900"
          />
        </div>

        <button
          @click="importDialogVisible = true"
          class="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-500"
        >
          <Plus class="h-4 w-4" />
          <span>导入资源</span>
        </button>
      </div>
    </div>

    <div v-if="!activeResource" class="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
      <article
        v-for="item in resources"
        :key="item.id"
        class="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm transition hover:border-blue-300 hover:shadow-md dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div class="aspect-video bg-zinc-950">
          <img v-if="item.cover_url" :src="item.cover_url" :alt="item.title" class="h-full w-full object-cover" />
          <div v-else class="flex h-full items-center justify-center text-zinc-500">
            <FileVideo class="h-9 w-9" />
          </div>
        </div>
        <div class="space-y-3 p-4">
          <div class="flex items-center justify-between gap-2 text-[10px]">
            <span class="rounded bg-blue-50 px-2 py-0.5 font-medium text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
              {{ item.category || 'B站课程' }}
            </span>
            <span class="truncate text-gray-400">UP: {{ item.author_name || '未知' }}</span>
          </div>
          <h3 class="line-clamp-2 min-h-[2.6rem] text-sm font-semibold leading-relaxed text-gray-900 dark:text-zinc-50">{{ item.title }}</h3>
          <p class="line-clamp-2 min-h-[2rem] text-[11px] leading-relaxed text-gray-400 dark:text-zinc-500">{{ item.description || '暂无简介' }}</p>
          <div class="flex items-center justify-between border-t border-gray-100 pt-3 dark:border-zinc-800">
            <span class="inline-flex items-center gap-1 text-[11px] text-gray-400">
              <Clock class="h-3.5 w-3.5" />
              <span>{{ item.total_episodes }} P</span>
            </span>
            <div class="flex items-center gap-2">
              <button
                @click="handleDelete(item)"
                class="rounded p-1 text-gray-300 transition hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/20"
                title="删除"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
              <button
                @click="enterRoom(item)"
                class="inline-flex items-center gap-1 rounded border border-blue-100 bg-blue-50 px-3 py-1.5 text-[11px] font-semibold text-blue-700 transition hover:bg-blue-100 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300"
              >
                <Play class="h-3.5 w-3.5 fill-current" />
                <span>进入学习</span>
              </button>
            </div>
          </div>
        </div>
      </article>

      <div v-if="resources.length === 0" class="col-span-full flex h-64 flex-col items-center justify-center rounded-lg border border-dashed border-gray-200 text-center text-gray-400 dark:border-zinc-800 dark:text-zinc-500">
        <FileVideo class="mb-3 h-10 w-10 text-gray-200 dark:text-zinc-800" />
        <p class="text-xs font-medium">还没有 B站学习资源</p>
      </div>
    </div>

    <div v-else class="grid grid-cols-1 gap-6 xl:grid-cols-12">
      <section class="xl:col-span-9 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <div class="mb-4 flex flex-col gap-3 border-b border-gray-100 pb-4 dark:border-zinc-800 md:flex-row md:items-center md:justify-between">
          <div class="flex min-w-0 items-center gap-2">
            <button @click="leaveRoom" class="rounded border border-gray-200 p-1 text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800">
              <ArrowLeft class="h-4 w-4" />
            </button>
            <div class="min-w-0">
              <h2 class="truncate text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ activeResource.title }}</h2>
              <p class="mt-0.5 truncate text-[10px] text-gray-400">
                {{ episodeLabel(currentEpisode) }} · {{ activeResource.bvid }}
              </p>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <button
              @click="selectEmbeddedPlayer"
              class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[11px] font-semibold transition"
              :class="!showBackupPlayer ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300' : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800'"
            >
              <ExternalLink class="h-3.5 w-3.5" />
              <span>外链播放器</span>
            </button>
            <button
              @click="selectBackupPlayer"
              class="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-[11px] font-semibold transition"
              :class="showBackupPlayer ? 'border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-300' : 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800'"
            >
              <FileVideo class="h-3.5 w-3.5" />
              <span>备用源</span>
            </button>
            <button
              @click="handleManualComplete"
              class="inline-flex items-center gap-1.5 rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] font-semibold text-emerald-700 transition hover:bg-emerald-100 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300"
            >
              <CheckCircle2 class="h-3.5 w-3.5" />
              <span>标记学完</span>
            </button>
          </div>
        </div>

        <div v-if="!showBackupPlayer" class="space-y-3">
          <div class="flex items-center justify-between rounded-lg border border-blue-100 bg-blue-50/60 px-3 py-2 text-[11px] text-blue-700 dark:border-blue-900/40 dark:bg-blue-950/20 dark:text-blue-300">
            <span>外链播放器 · {{ activeEpisodeInfo?.part || activeEpisodeInfo?.title || `第 ${currentEpisode} P` }}</span>
            <button @click="reloadEmbeddedPlayer" class="inline-flex items-center gap-1 rounded border border-blue-200 bg-white px-2 py-1 font-semibold dark:border-blue-900/50 dark:bg-zinc-900">
              <RefreshCw class="h-3 w-3" />
              <span>重载</span>
            </button>
          </div>
          <div class="relative aspect-video overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
            <iframe
              :key="`embed-${currentEpisode}-${playerReloadKey}`"
              :src="bilibiliEmbedSrc"
              scrolling="no"
              border="0"
              frameborder="no"
              framespacing="0"
              allowfullscreen="true"
              allow="autoplay; fullscreen; picture-in-picture"
              class="absolute inset-0 h-full w-full"
            ></iframe>
          </div>
        </div>

        <div v-else class="space-y-3">
          <div class="flex items-center justify-between rounded-lg border border-indigo-100 bg-indigo-50/60 px-3 py-2 text-[11px] text-indigo-700 dark:border-indigo-900/40 dark:bg-indigo-950/20 dark:text-indigo-300">
            <span>备用入口 · {{ activeEpisodeInfo?.part || activeEpisodeInfo?.title || `第 ${currentEpisode} P` }}</span>
            <button @click="reloadBackupPlayer" class="inline-flex items-center gap-1 rounded border border-indigo-200 bg-white px-2 py-1 font-semibold dark:border-indigo-900/50 dark:bg-zinc-900">
              <RefreshCw class="h-3 w-3" />
              <span>重载</span>
            </button>
          </div>

          <div class="relative aspect-video overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950">
            <div v-if="streamLoading" class="absolute inset-0 flex items-center justify-center text-xs text-zinc-300">
              正在准备备用视频源...
            </div>

            <video
              v-else-if="nativeVideoSrc"
              :key="`native-${currentEpisode}-${playerReloadKey}`"
              :src="nativeVideoSrc"
              controls
              playsinline
              preload="metadata"
              class="absolute inset-0 h-full w-full bg-black"
              @loadedmetadata="handleNativeLoadedMetadata"
              @timeupdate="handleNativeTimeUpdate"
              @play="handleNativePlay"
              @pause="handleNativePause"
            ></video>

            <iframe
              v-else
              :key="`iframe-${currentEpisode}-${playerReloadKey}`"
              :src="bilibiliEmbedSrc"
              scrolling="no"
              border="0"
              frameborder="no"
              framespacing="0"
              allowfullscreen="true"
              allow="autoplay; fullscreen; picture-in-picture"
              class="absolute inset-0 h-full w-full"
            ></iframe>
          </div>

          <p v-if="streamError" class="rounded border border-amber-100 bg-amber-50 px-3 py-2 text-[11px] text-amber-700 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-300">
            {{ streamError }}
          </p>
        </div>
      </section>

      <aside class="xl:col-span-3 space-y-5">
        <section class="rounded-lg border border-gray-200 bg-white p-5 text-center shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <div class="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-blue-50 text-blue-600 dark:bg-blue-950/30 dark:text-blue-300">
            <Clock class="h-5 w-5" />
          </div>
          <p class="text-[11px] text-gray-400">本次学习</p>
          <p class="mt-1 font-mono text-2xl font-bold text-gray-900 dark:text-zinc-50">{{ formatWatchTime(totalSessionWatchTime) }}</p>
          <div class="mt-3 flex justify-center gap-2 text-[10px]">
            <span class="inline-flex items-center gap-1 rounded bg-gray-100 px-2 py-1 text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
              <PauseCircle class="h-3 w-3" />
              <span>暂停 {{ pauseCountInSession }}</span>
            </span>
          </div>
        </section>

        <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h3 class="mb-3 text-xs font-semibold text-gray-900 dark:text-zinc-50">播放分集 ({{ activeResource.total_episodes }})</h3>
          <div class="max-h-64 space-y-2 overflow-y-auto pr-1">
            <button
              v-for="ep in activeResource.total_episodes"
              :key="ep"
              @click="handleEpisodeChange(ep)"
              class="flex w-full items-center justify-between gap-2 rounded-lg border p-3 text-left text-xs transition"
              :class="ep === currentEpisode ? 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900/50 dark:bg-blue-950/20 dark:text-blue-300' : 'border-gray-100 bg-white text-gray-600 hover:bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800'"
            >
              <span class="line-clamp-2">{{ episodeLabel(ep) }}</span>
              <Play v-if="ep === currentEpisode" class="h-3.5 w-3.5 shrink-0 fill-current" />
            </button>
          </div>
        </section>

        <section class="rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <h3 class="mb-3 text-xs font-semibold text-gray-900 dark:text-zinc-50">观看统计</h3>
          <div class="space-y-2">
            <div v-for="stat in watchStats" :key="`${stat.resource_id}-${stat.episode_number}-${stat.start_time}`" class="rounded-lg border border-gray-100 bg-gray-50/60 p-3 text-[11px] dark:border-zinc-800 dark:bg-zinc-950/20">
              <div class="flex items-center justify-between font-medium text-gray-800 dark:text-zinc-200">
                <span>{{ formatClock(stat.start_time) }} - {{ formatClock(stat.end_time) }}</span>
                <span>第 {{ stat.episode_number }} P</span>
              </div>
              <div class="mt-1 flex items-center justify-between text-gray-400">
                <span>{{ formatMinutes(stat.watch_seconds) }}</span>
                <span>暂停 {{ stat.pause_count }} 次</span>
              </div>
            </div>
            <div v-if="watchStats.length === 0" class="rounded-lg border border-dashed border-gray-200 py-8 text-center text-[11px] text-gray-400 dark:border-zinc-800">
              暂无观看记录
            </div>
          </div>
        </section>
      </aside>
    </div>

    <el-dialog v-model="importDialogVisible" title="导入 B站视频资源" width="520px" class="minimalist-dialog">
      <div class="space-y-4 text-xs">
        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">BV 号或 B站链接 <span class="text-red-500">*</span></label>
          <div class="flex gap-2">
            <input
              v-model="importForm.bvid"
              @blur="() => { if (importForm.bvid && !importForm.title) recognizeBilibiliMeta() }"
              type="text"
              placeholder="例如 BV1xx411c7m9 或视频链接"
              class="min-w-0 flex-1 rounded border border-gray-200 bg-gray-50 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"
            />
            <button
              @click="recognizeBilibiliMeta"
              :disabled="recognizingMeta"
              class="inline-flex items-center gap-1.5 rounded border border-blue-100 bg-blue-50 px-3 py-2 font-semibold text-blue-700 transition hover:bg-blue-100 disabled:opacity-60 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-blue-300"
            >
              <RefreshCw v-if="recognizingMeta" class="h-3.5 w-3.5 animate-spin" />
              <Sparkles v-else class="h-3.5 w-3.5" />
              <span>识别</span>
            </button>
          </div>
        </div>

        <div v-if="importForm.cover_url || importForm.title" class="flex gap-3 rounded-lg border border-gray-100 bg-gray-50 p-3 dark:border-zinc-800 dark:bg-zinc-950/20">
          <img v-if="importForm.cover_url" :src="importForm.cover_url" alt="" class="h-20 w-32 rounded object-cover" />
          <div class="min-w-0 flex-1 space-y-1">
            <p class="line-clamp-2 text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ importForm.title || '待识别标题' }}</p>
            <p class="text-[11px] text-gray-400">UP: {{ importForm.author_name || '未知' }} · {{ importForm.total_episodes }} P</p>
          </div>
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">标题 <span class="text-red-500">*</span></label>
          <input v-model="importForm.title" type="text" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">UP 主</label>
            <input v-model="importForm.author_name" type="text" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
          </div>
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">总分 P</label>
            <input v-model.number="importForm.total_episodes" type="number" min="1" class="w-full rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950" />
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div class="space-y-1.5">
            <label class="font-medium text-gray-500">分类</label>
            <select v-model="importForm.category" class="w-full rounded border border-gray-200 bg-white px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950">
              <option value="学术网课">学术网课</option>
              <option value="前沿技术">前沿技术</option>
              <option value="基础理论">基础理论</option>
              <option value="公开课程">公开课程</option>
              <option value="其他">其他</option>
            </select>
          </div>
          <label class="mt-6 flex items-center gap-2 text-gray-600 dark:text-zinc-400">
            <input v-model="importForm.is_shared" type="checkbox" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            <span>公共资源可见</span>
          </label>
        </div>

        <div class="space-y-1.5">
          <label class="font-medium text-gray-500">简介</label>
          <textarea v-model="importForm.description" rows="3" class="w-full resize-none rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs outline-none focus:border-blue-500 dark:border-zinc-800 dark:bg-zinc-950"></textarea>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <button @click="importDialogVisible = false" class="rounded border border-gray-200 px-3 py-1.5 text-xs text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800">取消</button>
          <button @click="handleImport" class="rounded bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-500">提交导入</button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 999px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
