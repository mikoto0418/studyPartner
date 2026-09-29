<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Sun, Moon, HelpCircle } from 'lucide-vue-next'
import AppSidebar from '../components/common/AppSidebar.vue'
import { IMPORT_TEMPLATE_JSON, IMPORT_PACKAGE_GUIDE, downloadImportTemplate, downloadImportPackageTemplate } from '../api/modules/assessment'
import { notificationApi } from '../api/modules/notification'
import type { NotificationOut } from '../api/modules/notification'
import { authApi } from '../api/modules/auth'

import { onUnmounted } from 'vue'
import { studyTimeApi } from '../api/modules/study_time'

const route = useRoute()

const isDark = ref(false)
const showNotifications = ref(false)

const pageTitle = computed(() => {
  return (route.meta.title as string) || 'AI伴学平台'
})

const toggleTheme = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

// Notifications state
const notifications = ref<NotificationOut[]>([])

const fetchNotifications = async () => {
  try {
    const res = await notificationApi.listNotifications()
    notifications.value = res.data || []
  } catch (error) {
    console.warn('Failed to fetch notifications', error)
    notifications.value = []
  }
}

const unreadCount = computed(() => notifications.value.filter(n => !n.read_at).length)

const syncCurrentIdentity = async () => {
  try {
    const res = await authApi.getMe()
    const user = res.data
    if (!user) return
    localStorage.setItem('sp_username', user.username)
    if (user.display_name && user.display_name !== '未设置姓名') {
      localStorage.setItem('sp_display_name', user.display_name)
    } else {
      localStorage.removeItem('sp_display_name')
    }
    window.dispatchEvent(new Event('profile-updated'))
  } catch (error) {
    console.warn('Failed to sync current identity', error)
  }
}

const markAllAsRead = async () => {
  try {
    await notificationApi.markAllAsRead()
    notifications.value.forEach(n => {
      if (!n.read_at) n.read_at = new Date().toISOString()
    })
  } catch (error) {
    console.warn('Failed to mark all notifications as read', error)
  }
}

const markSingleAsRead = async (item: NotificationOut) => {
  if (item.read_at) return
  try {
    await notificationApi.markAsRead(item.id)
    item.read_at = new Date().toISOString()
  } catch (error) {
    console.warn('Failed to mark notification as read', error)
  }
}

const formatNotificationTime = (isoStr: string) => {
  const diff = Date.now() - new Date(isoStr).getTime()
  if (diff < 60000) return '刚刚'
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  return `${Math.floor(hours / 24)}天前`
}

let notificationTimer: any = null
let heartbeatTimer: any = null

const handleNewNotification = (event: Event) => {
  const item = (event as CustomEvent<NotificationOut>).detail
  if (!item?.id) return
  if (notifications.value.some(n => n.id === item.id)) return
  notifications.value.unshift(item)
}

onMounted(() => {
  syncCurrentIdentity()
  fetchNotifications()
  window.addEventListener('new-notification', handleNewNotification)
  // Poll notifications every 60 seconds
  notificationTimer = setInterval(fetchNotifications, 60000)

  // Start study time heartbeat if student
  const userRole = localStorage.getItem('sp_role')
  if (userRole === 'student') {
    const sessionId = crypto.randomUUID()
    const sendHeartbeat = async () => {
      try {
        await studyTimeApi.reportHeartbeat({
          session_id: sessionId,
          duration_seconds: 30,
          source: 'platform'
        })
      } catch (e) {
        console.error('Failed to report study time heartbeat', e)
      }
    }
    sendHeartbeat()
    heartbeatTimer = setInterval(sendHeartbeat, 30000)
  }
})

// ---------- 操作指南（悬浮问号 + 首次登录引导）----------
// 按当前所在端给对应角色的步骤说明：同一套界面下，学生/教师/管理员看到的东西完全不同，
// 给一份通用说明等于没说。用路由前缀判断，不额外引入角色依赖。
const helpVisible = ref(false)

type HelpScope = 'student' | 'teacher' | 'admin' | 'common'

const roleScope = computed<HelpScope>(() => {
  const path = route.path || ''
  if (path.startsWith('/student')) return 'student'
  if (path.startsWith('/teacher')) return 'teacher'
  if (path.startsWith('/admin')) return 'admin'
  return 'common'
})

const HELP_GUIDES: Record<
  HelpScope,
  { title: string; steps: string[]; code?: { label: string; content: string } }
> = {
  student: {
    title: '学生操作指南',
    steps: [
      '在「我的试卷」里选择试卷，点「进入全屏并开始作答」。',
      '作答期间请保持全屏：退出全屏、切窗口、粘贴、右键都会被记录，累计退出会被自动交卷。',
      '写长答案时系统会自动保存草稿，不必手动提交。',
      '交卷后可在试卷列表进入「查看」，逐题查看自己的答案、得分与参考答案。',
      '含主观题时，待批改阶段只显示客观题小计，老师批完才是最终成绩。'
    ]
  },
  teacher: {
    title: '教师操作指南',
    steps: [
      '发题工作台：上传试卷文档 → 等 AI 拆题 → 人工校对分值与答案 → 选发布对象（按班级 / 按指导学生 / 按学生手填 ID）→ 发布。',
      '发布时可开关「要求全程全屏作答」；关闭则允许学生窗口化作答，复制粘贴等限制仍生效。',
      '批改：监考中心 → 批改。可先点「AI 预批」拿建议分，确认后保存才计入成绩；成绩列表支持按状态、姓名筛选。',
      '导出成绩单：监考中心右上角「导出成绩单 PDF」，只含已保存的分数，未批完的主观题留空不记 0 分。',
      '班级看板：「创建班级」建班；「批量建号」粘贴「学号,姓名[,年级,专业]」可一次开号并直接进班。',
      '导入题目：「发题工作台 → 导入 JSON/压缩包」，可下载下面的 JSON 模板或压缩包骨架照填，跳过 AI 拆题直接建卷。'
    ],
    code: { label: '导入用 JSON 模板（paper.json）', content: IMPORT_TEMPLATE_JSON }
  },
  admin: {
    title: '管理员操作指南',
    steps: [
      '用户管理：查看、新建、编辑用户与学号档案。',
      '模型配置：为每个子任务指定模型通道。没有单独配置的任务会显示「未配置」，此时对应功能不可用。',
      '公告发布 / 系统设置：下发通知与调整运行参数。',
      '管理概览：查看账号统计、知识库容量与近期大模型调用记录。'
    ]
  },
  common: {
    title: '使用说明',
    steps: [
      '右上角可切换浅色 / 深色主题。',
      '铃铛图标查看通知。',
      '左侧导航进入各功能模块；不同角色看到的入口不同。'
    ]
  }
}

const helpGuide = computed(() => HELP_GUIDES[roleScope.value] || HELP_GUIDES.common)

// 每个端只在第一次进入时自动弹一次，避免每次进来都挡在面前。
const helpSeenKey = computed(() => `sp-help-seen:${roleScope.value}`)

// 首次进入该端：在问号上方冒一次气泡，说明「这是使用说明」，看过就不再提示。
const helpHintVisible = ref(false)
const copied = ref(false)

const copyTemplate = async () => {
  const content = HELP_GUIDES.teacher.code?.content || ''
  if (!content) return
  try {
    await navigator.clipboard.writeText(content)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch {
    // 剪贴板不可用（非 https / 无权限）时静默，页面上直接选中复制即可
  }
}

onMounted(() => {
  try {
    if (!localStorage.getItem(helpSeenKey.value)) {
      localStorage.setItem(helpSeenKey.value, '1')
      helpHintVisible.value = true
    }
  } catch {
    // 隐私模式下 localStorage 可能不可用，忽略即可
  }
})

onUnmounted(() => {
  if (notificationTimer) clearInterval(notificationTimer)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
  window.removeEventListener('new-notification', handleNewNotification)
})
</script>

<template>
  <div class="flex w-screen h-screen overflow-hidden bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-zinc-50 transition-colors">
    <!-- App Sidebar -->
    <AppSidebar />

    <!-- 操作指南：悬浮问号；首次进入在按钮上方冒一次气泡提醒 -->
    <div class="fixed bottom-6 right-6 z-40 flex flex-col items-end gap-2">
      <div
        v-if="helpHintVisible"
        class="relative max-w-[230px] rounded-lg bg-gray-900 px-3 py-2 text-[11px] leading-relaxed text-white shadow-lg dark:bg-zinc-100 dark:text-zinc-900"
      >
        <p class="font-semibold">这是使用说明</p>
        <p class="mt-0.5 opacity-80">第一次登录提示一次，以后不再显示。</p>
        <button
          class="absolute -right-1.5 -top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-gray-700 text-[9px] leading-none text-white dark:bg-zinc-300 dark:text-zinc-900"
          @click="helpHintVisible = false"
        >
          ×
        </button>
      </div>
      <button
        class="flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition hover:bg-blue-500"
        title="操作指南"
        @click="helpVisible = true"
      >
        <HelpCircle class="w-5 h-5" />
      </button>
    </div>

    <el-drawer v-model="helpVisible" :title="helpGuide.title" size="420px" append-to-body>
      <ol class="space-y-3 text-sm leading-relaxed text-gray-700 dark:text-zinc-200">
        <li v-for="(step, idx) in helpGuide.steps" :key="idx" class="flex gap-2">
          <span class="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full bg-blue-50 text-[11px] font-semibold text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
            {{ idx + 1 }}
          </span>
          <span>{{ step }}</span>
        </li>
      </ol>

      <div v-if="helpGuide.code" class="mt-6">
        <div class="flex items-center justify-between">
          <p class="text-xs font-semibold text-gray-700 dark:text-zinc-200">{{ helpGuide.code.label }}</p>
          <span class="flex items-center gap-3">
            <button class="text-[11px] font-semibold text-blue-600 dark:text-blue-400" @click="downloadImportTemplate()">
              下载 JSON
            </button>
            <button class="text-[11px] font-semibold text-blue-600 dark:text-blue-400" @click="downloadImportPackageTemplate()">
              下载压缩包骨架
            </button>
            <button class="text-[11px] font-semibold text-gray-500 dark:text-zinc-400" @click="copyTemplate">
              {{ copied ? '已复制' : '复制内容' }}
            </button>
          </span>
        </div>
        <pre class="mt-2 max-h-72 overflow-auto rounded-lg bg-gray-50 p-3 font-mono text-[10px] leading-relaxed text-gray-700 dark:bg-zinc-950 dark:text-zinc-300">{{ helpGuide.code.content }}</pre>

        <p class="mt-5 text-xs font-semibold text-gray-700 dark:text-zinc-200">压缩包与图片怎么对应（说明）</p>
        <pre class="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg bg-gray-50 p-3 font-mono text-[10px] leading-relaxed text-gray-700 dark:bg-zinc-950 dark:text-zinc-300">{{ IMPORT_PACKAGE_GUIDE }}</pre>
      </div>

      <p class="mt-6 text-[11px] text-gray-400">随时点右下角的问号可以再看一遍。</p>
    </el-drawer>

    <!-- Main Section -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden relative">
      
      <!-- Topbar Header -->
      <header class="h-16 border-b border-gray-200 dark:border-zinc-800 flex items-center justify-between px-4 md:px-8 bg-white dark:bg-zinc-900 flex-shrink-0 z-10">
        <!-- Title -->
        <div>
          <h2 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">
            {{ pageTitle }}
          </h2>
        </div>

        <!-- Right actions -->
        <div class="flex items-center space-x-4">
          
          <!-- Theme Toggle -->
          <button
            @click="toggleTheme"
            class="ui-icon-button border-transparent"
            title="切换主题"
          >
            <Sun v-if="isDark" class="w-4 h-4" />
            <Moon v-else class="w-4 h-4" />
          </button>

          <!-- Notification Bell Dropdown -->
          <div class="relative">
            <button
              @click="showNotifications = !showNotifications"
              class="ui-icon-button relative border-transparent"
              title="通知"
            >
              <Bell class="w-4 h-4" />
              <span
                v-if="unreadCount > 0"
                class="absolute top-1 right-1 w-2 h-2 bg-blue-600 rounded-full"
              ></span>
            </button>

            <!-- Notifications Card -->
            <div
              v-if="showNotifications"
              class="absolute right-0 mt-2 w-80 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-lg shadow-lg py-2 z-30"
            >
              <!-- Card Header -->
              <div class="px-4 py-2 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between">
                <span class="text-xs font-semibold">最新通知</span>
                <button
                  v-if="unreadCount > 0"
                  @click="markAllAsRead"
                  class="text-[10px] text-blue-600 hover:underline"
                >
                  全部标记已读
                </button>
              </div>

              <!-- Notifications list -->
              <div class="max-h-60 overflow-y-auto">
                <div
                  v-for="item in notifications"
                  :key="item.id"
                  @click="markSingleAsRead(item)"
                  class="px-4 py-3 hover:bg-gray-50 dark:hover:bg-zinc-800/40 border-b border-gray-50 dark:border-zinc-800/20 last:border-0 flex items-start space-x-2 cursor-pointer"
                >
                  <!-- Read status dot -->
                  <span
                    class="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0"
                    :class="item.read_at ? 'bg-transparent' : 'bg-blue-600'"
                  ></span>
                  
                  <div class="flex-1 min-w-0">
                    <div class="flex justify-between items-baseline mb-0.5">
                      <h4 class="text-xs font-medium truncate" :class="item.read_at ? 'text-gray-500' : 'text-gray-800 dark:text-zinc-100'">
                        {{ item.title }}
                      </h4>
                      <span class="text-[9px] text-gray-400 dark:text-zinc-500">{{ formatNotificationTime(item.created_at) }}</span>
                    </div>
                    <p class="text-[10px] text-gray-400 dark:text-zinc-500 leading-normal line-clamp-2">
                      {{ item.content }}
                    </p>
                  </div>
                </div>
                
                <div v-if="notifications.length === 0" class="py-6 text-center text-xs text-gray-400">
                  没有新通知
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      <!-- Click outside listener for notifications -->
      <div
        v-if="showNotifications"
        @click="showNotifications = false"
        class="fixed inset-0 z-20"
      ></div>

      <!-- Main Content Area -->
      <main class="flex-1 overflow-y-auto bg-gray-50 dark:bg-zinc-950 p-4 md:p-8 relative">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>

    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
