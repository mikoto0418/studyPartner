<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ArrowLeft, Tv, Search, Plus, Clock, Play, CheckCircle2, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { bilibiliApi } from '../../api/modules/bilibili'
import type { BilibiliResourceOut } from '../../api/modules/bilibili'

// State
const resources = ref<BilibiliResourceOut[]>([])
const keyword = ref('')
const activeResource = ref<BilibiliResourceOut | null>(null)
const currentEpisode = ref(1)

// Dialog
const importDialogVisible = ref(false)
const importForm = ref({
  bvid: '',
  title: '',
  description: '',
  author_name: '',
  total_episodes: 1,
  category: '学术论文',
  is_shared: true
})

// Timer and Session metrics
const watchTimeInCurrentPeriod = ref(0)
const totalSessionWatchTime = ref(0)
let watchTimer: any = null
let secondsTimer: any = null

// Load video resources
const loadResources = async () => {
  try {
    const res = await bilibiliApi.listResources({ keyword: keyword.value })
    resources.value = res.data || []
  } catch (error) {
    console.warn("Failed to load bilibili resources. Using mocks.")
    resources.value = [
      {
        id: 'r1',
        creator_id: 'u1',
        bvid: 'BV1Rx411c7m9',
        title: '【学术前沿】Transformer 架构深度剖析与自注意力推导',
        description: '本视频详细推导了 Transformer 架构的核心 Self-Attention 机制，并探讨了在自然语言处理与多模态领域的演进。',
        author_name: 'AI研习社官号',
        total_episodes: 3,
        category: '学术论文',
        is_shared: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      {
        id: 'r2',
        creator_id: 'u1',
        bvid: 'BV1jK4y1P7S6',
        title: '写给开发者的向量数据库入门指南（含 Qdrant 与 milvus 实战）',
        description: '系统讲解向量检索底层 HNSW、IVF 索引原理，以及如何通过 API 高效对接知识库项目。',
        author_name: '科技老杜',
        total_episodes: 1,
        category: '前沿技术',
        is_shared: true,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]
  }
}

// Import action
const handleImport = async () => {
  if (!importForm.value.bvid.trim()) {
    ElMessage.warning('请输入 BVID (形如 BV...)')
    return
  }
  if (!importForm.value.title.trim()) {
    ElMessage.warning('请输入视频标题')
    return
  }

  try {
    await bilibiliApi.addResource({
      bvid: importForm.value.bvid.trim(),
      title: importForm.value.title.trim(),
      description: importForm.value.description.trim() || undefined,
      author_name: importForm.value.author_name.trim() || undefined,
      total_episodes: importForm.value.total_episodes,
      category: importForm.value.category,
      is_shared: importForm.value.is_shared
    })
    ElMessage.success('导入学习视频成功')
    importDialogVisible.value = false
    // Reset form
    importForm.value = {
      bvid: '',
      title: '',
      description: '',
      author_name: '',
      total_episodes: 1,
      category: '学术论文',
      is_shared: true
    }
    loadResources()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '导入资源失败')
  }
}

// Delete action
const handleDelete = async (item: BilibiliResourceOut) => {
  ElMessageBox.confirm(
    `确定删除学习视频「${item.title}」吗？`,
    '提示',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await bilibiliApi.deleteResource(item.id)
      ElMessage.success('删除视频资源成功')
      loadResources()
    } catch (e: any) {
      ElMessage.error(e.response?.data?.message || '删除失败，仅限上传者本人删除')
    }
  }).catch(() => {})
}

// Formatted seconds helper
const formatWatchTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

// Open video room
const enterRoom = (resource: BilibiliResourceOut) => {
  activeResource.value = resource
  currentEpisode.value = 1
  watchTimeInCurrentPeriod.value = 0
  totalSessionWatchTime.value = 0

  // Log open event
  bilibiliApi.logWatchEvent({
    resource_id: resource.id,
    event_type: 'open',
    episode_number: currentEpisode.value,
    watch_duration: 0
  })

  // Set real timer for screen display (increments local clock every second)
  secondsTimer = setInterval(() => {
    watchTimeInCurrentPeriod.value += 1
    totalSessionWatchTime.value += 1
  }, 1000)

  // Send heartbeat every 30 seconds
  watchTimer = setInterval(async () => {
    try {
      await bilibiliApi.logWatchEvent({
        resource_id: resource.id,
        event_type: 'heartbeat',
        episode_number: currentEpisode.value,
        watch_duration: 30
      })
      // Reset periodic watch time ticker
      watchTimeInCurrentPeriod.value = 0
    } catch (err) {
      console.warn("Heartbeat logging failure", err)
    }
  }, 30000)
}

// Close video room / Return to list
const leaveRoom = async () => {
  if (!activeResource.value) return

  if (watchTimer) {
    clearInterval(watchTimer)
    watchTimer = null
  }
  if (secondsTimer) {
    clearInterval(secondsTimer)
    secondsTimer = null
  }

  // Report residual watch seconds
  const remainder = watchTimeInCurrentPeriod.value
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value.id,
      event_type: 'close',
      episode_number: currentEpisode.value,
      watch_duration: remainder > 0 ? remainder : 1
    })
  } catch (e) {
    console.error("Failed to report close event duration", e)
  }

  activeResource.value = null
  loadResources()
}

// Switch episode/part
const handleEpisodeChange = async (ep: number) => {
  if (ep === currentEpisode.value) return
  
  // Log close of current ep
  const remainder = watchTimeInCurrentPeriod.value
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value!.id,
      event_type: 'close',
      episode_number: currentEpisode.value,
      watch_duration: remainder > 0 ? remainder : 1
    })
  } catch (e) {}

  // Switch
  currentEpisode.value = ep
  watchTimeInCurrentPeriod.value = 0

  // Log open of new ep
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value!.id,
      event_type: 'open',
      episode_number: ep,
      watch_duration: 0
    })
  } catch (e) {}
}

// Mark video completed
const handleManualComplete = async () => {
  if (!activeResource.value) return
  try {
    await bilibiliApi.logWatchEvent({
      resource_id: activeResource.value.id,
      event_type: 'manual_complete',
      episode_number: currentEpisode.value,
      is_completed: true
    })
    ElMessage.success('恭喜完成本资源视频学习！积分已更新。')
  } catch (error) {
    ElMessage.error('标记失败')
  }
}

// Embed Bilibili link computed property
const bilibiliEmbedSrc = computed(() => {
  if (!activeResource.value) return ''
  // Enable high quality, disable auto play, hide danmaku for clean study environment
  return `https://player.bilibili.com/player.html?bvid=${activeResource.value.bvid}&page=${currentEpisode.value}&high_quality=1&danmaku=0`
})

onMounted(() => {
  loadResources()
})

onUnmounted(() => {
  if (watchTimer) clearInterval(watchTimer)
  if (secondsTimer) clearInterval(secondsTimer)
})
</script>

<template>
  <div class="space-y-6">
    <!-- Header Controls (Visible only on list screen) -->
    <div v-if="!activeResource" class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div>
        <p class="text-xs text-gray-400 dark:text-zinc-500">引入学术与网课视频资源，打造沉浸式协作播放室，自动记录行为心跳。</p>
      </div>

      <div class="flex items-center space-x-3">
        <!-- Search -->
        <div class="relative w-64">
          <Search class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            v-model="keyword"
            @keyup.enter="loadResources"
            type="text"
            placeholder="搜索视频资源..."
            class="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg text-xs focus:outline-none focus:border-blue-500"
          />
        </div>

        <!-- Add Button -->
        <button
          @click="importDialogVisible = true"
          class="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-sm transition-all focus:outline-none"
        >
          <Plus class="w-4 h-4" />
          <span>导入 B站资源</span>
        </button>
      </div>
    </div>

    <!-- 1. Video List (Gallery View) -->
    <div v-if="!activeResource" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      <div
        v-for="item in resources"
        :key="item.id"
        class="minimal-card flex flex-col justify-between h-[200px] hover:border-blue-500/50 hover:shadow-md transition-all group overflow-hidden"
      >
        <div class="p-5 space-y-3">
          <!-- Top Tag and Author -->
          <div class="flex items-center justify-between">
            <span class="text-[9px] px-2 py-0.5 rounded font-medium bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400 border border-blue-100/30">
              {{ item.category || '学术网课' }}
            </span>
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 max-w-[120px] truncate">
              UP: {{ item.author_name || '未知作者' }}
            </span>
          </div>

          <!-- Title -->
          <h4 class="text-xs font-bold text-gray-800 dark:text-zinc-100 line-clamp-2 leading-relaxed">
            {{ item.title }}
          </h4>

          <!-- Desc -->
          <p class="text-[10px] text-gray-400 dark:text-zinc-500 line-clamp-2 leading-relaxed">
            {{ item.description || '暂无描述。' }}
          </p>
        </div>

        <!-- Bottom row -->
        <div class="px-5 py-3.5 bg-gray-50/50 dark:bg-zinc-900/30 border-t border-gray-100/50 dark:border-zinc-800/30 flex items-center justify-between flex-shrink-0">
          <div class="flex items-center space-x-1 text-[10px] text-gray-400 dark:text-zinc-500">
            <Clock class="w-3.5 h-3.5" />
            <span>{{ item.total_episodes }} P 分集</span>
          </div>

          <div class="flex items-center space-x-2">
            <!-- Delete action for resources -->
            <button
              @click.stop="handleDelete(item)"
              class="p-1 rounded hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-950/20 text-gray-400 transition-colors"
            >
              <Trash2 class="w-3.5 h-3.5" />
            </button>

            <!-- Enter Button -->
            <button
              @click="enterRoom(item)"
              class="flex items-center space-x-1 px-3 py-1 bg-blue-50 hover:bg-blue-100 dark:bg-blue-950/30 dark:hover:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-100 dark:border-blue-900/40 rounded text-[10px] font-bold transition-all"
            >
              <Play class="w-3 h-3 fill-current" />
              <span>进入学习房</span>
            </button>
          </div>
        </div>
      </div>

      <!-- Empty state -->
      <div v-if="resources.length === 0" class="col-span-full py-16 text-center minimal-card flex flex-col items-center justify-center space-y-3">
        <Tv class="w-8 h-8 text-gray-300 dark:text-zinc-700" />
        <h4 class="text-xs font-semibold text-gray-500">资源库为空</h4>
        <p class="text-[10px] text-gray-400 max-w-xs">
          这里还没有导入任何 B站学习资源。点击右上角的“导入 B站资源”来添加你的第一个视频。
        </p>
      </div>
    </div>

    <!-- 2. Video Player Room Screen -->
    <div v-else class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
      <!-- Player Panel (9 cols) -->
      <div class="lg:col-span-9 minimal-card p-6 flex flex-col space-y-4">
        <!-- Room header -->
        <div class="flex items-center justify-between pb-3 border-b border-gray-100 dark:border-zinc-800">
          <div class="flex items-center space-x-2">
            <button
              @click="leaveRoom"
              class="p-1 rounded border border-gray-200 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors text-gray-500"
            >
              <ArrowLeft class="w-4 h-4" />
            </button>
            <div>
              <h3 class="text-xs font-bold text-gray-900 dark:text-zinc-50 truncate max-w-md">
                {{ activeResource.title }}
              </h3>
              <p class="text-[9px] text-gray-400">正在学习第 {{ currentEpisode }} P &bull; BVID: {{ activeResource.bvid }}</p>
            </div>
          </div>

          <div class="flex items-center space-x-2">
            <button
              @click="handleManualComplete"
              class="flex items-center space-x-1 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 dark:bg-emerald-950/20 dark:hover:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900/40 rounded-lg text-[10px] font-bold transition-all"
            >
              <CheckCircle2 class="w-3.5 h-3.5" />
              <span>标记本资源学完</span>
            </button>
          </div>
        </div>

        <!-- iframe Video Box -->
        <div class="relative w-full aspect-video bg-zinc-950 rounded-lg overflow-hidden border border-zinc-800">
          <iframe
            v-if="bilibiliEmbedSrc"
            :src="bilibiliEmbedSrc"
            scrolling="no"
            border="0"
            frameborder="no"
            framespacing="0"
            allowfullscreen="true"
            sandbox="allow-top-navigation allow-same-origin allow-forms allow-scripts"
            class="absolute top-0 left-0 w-full h-full"
          ></iframe>
        </div>
      </div>

      <!-- Control Sidebar (3 cols) -->
      <div class="lg:col-span-3 flex flex-col gap-6">
        <!-- Watch Ticker Timer -->
        <div class="minimal-card p-6 flex flex-col items-center justify-center text-center space-y-3">
          <div class="w-10 h-10 rounded-full bg-blue-50 dark:bg-blue-950/20 flex items-center justify-center text-blue-600 dark:text-blue-500">
            <Clock class="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <span class="text-[10px] text-gray-400 dark:text-zinc-500 font-medium block">本次专注时间</span>
            <span class="text-2xl font-bold text-gray-800 dark:text-zinc-100 font-mono tracking-wider">
              {{ formatWatchTime(totalSessionWatchTime) }}
            </span>
          </div>
          <p class="text-[9px] text-gray-400 leading-normal max-w-[180px]">
            专注心跳每 30 秒自动记录。离开房间时会自动合并时长。
          </p>
        </div>

        <!-- Episode Selector -->
        <div class="minimal-card p-6 flex-1 flex flex-col space-y-3 overflow-hidden min-h-[300px]">
          <h4 class="text-xs font-semibold text-gray-900 dark:text-zinc-50 flex-shrink-0">播放分集 ({{ activeResource.total_episodes }})</h4>
          <div class="flex-1 overflow-y-auto space-y-2 pr-1">
            <button
              v-for="ep in activeResource.total_episodes"
              :key="ep"
              @click="handleEpisodeChange(ep)"
              class="w-full text-left p-3 rounded-lg border text-xs transition-all flex items-center justify-between"
              :class="
                ep === currentEpisode
                  ? 'bg-blue-50/50 border-blue-200 text-blue-700 font-semibold dark:bg-blue-950/20 dark:border-blue-900/50 dark:text-blue-400'
                  : 'bg-white hover:bg-gray-50 border-gray-100 hover:border-gray-200 text-gray-600 dark:bg-zinc-900 dark:border-zinc-800/50 dark:hover:bg-zinc-800 dark:text-zinc-300'
              "
            >
              <span>第 {{ ep }} P 课程</span>
              <Play v-if="ep === currentEpisode" class="w-3.5 h-3.5 fill-current" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. Import Dialog -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入 B 站视频学习资源"
      width="450px"
      class="minimalist-dialog"
    >
      <div class="space-y-4">
        <!-- BVID -->
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">B 站视频 BVID <span class="text-red-500">*</span></label>
          <input
            v-model="importForm.bvid"
            type="text"
            placeholder="形如 BV1xx411c7m9"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100 font-mono"
          />
        </div>

        <!-- Title -->
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">视频资源标题 <span class="text-red-500">*</span></label>
          <input
            v-model="importForm.title"
            type="text"
            placeholder="例如：Transformer架构从入门到精通"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
          />
        </div>

        <!-- UP name -->
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">UP主名字（可选）</label>
          <input
            v-model="importForm.author_name"
            type="text"
            placeholder="例如：跟李沐学AI"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
          />
        </div>

        <!-- Episodes & category -->
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1">
            <label class="text-xs text-gray-500 block font-medium">总分P集数</label>
            <input
              v-model.number="importForm.total_episodes"
              type="number"
              min="1"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
            />
          </div>
          <div class="space-y-1">
            <label class="text-xs text-gray-500 block font-medium">视频分类</label>
            <select
              v-model="importForm.category"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-300 bg-white"
            >
              <option value="学术论文">学术论文</option>
              <option value="前沿技术">前沿技术</option>
              <option value="基础理论">基础理论</option>
              <option value="公共网课">公共网课</option>
              <option value="其他">其他</option>
            </select>
          </div>
        </div>

        <!-- description -->
        <div class="space-y-1">
          <label class="text-xs text-gray-500 block font-medium">资源描述（选填）</label>
          <textarea
            v-model="importForm.description"
            rows="3"
            placeholder="可选填视频大纲或课程重点简介..."
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-xs focus:outline-none focus:border-blue-500 text-gray-800 dark:text-zinc-100"
          ></textarea>
        </div>

        <!-- shared check -->
        <div class="flex items-center space-x-2 pt-1.5">
          <input
            id="shared_input"
            v-model="importForm.is_shared"
            type="checkbox"
            class="rounded text-blue-600 focus:ring-blue-500 h-3.5 w-3.5 border-gray-300"
          />
          <label for="shared_input" class="text-xs text-gray-600 dark:text-zinc-400 select-none">允许实验室其他成员在公共资源库看见此视频</label>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="importDialogVisible = false" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleImport" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">提交导入</button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* Hidden scrollbars for clean UI but scrollable contents */
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
