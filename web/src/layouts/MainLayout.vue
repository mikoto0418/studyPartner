<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Bell, Sun, Moon } from 'lucide-vue-next'
import AppSidebar from '../components/common/AppSidebar.vue'
import { notificationApi } from '../api/modules/notification'
import type { NotificationOut } from '../api/modules/notification'

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
    console.warn("Failed to fetch notifications. Using mock data.")
    // Safe fallback mock notifications
    notifications.value = [
      { id: '1', title: '新任务下达', content: '老师给你下发了「期末研究报告大纲提交」任务。', created_at: new Date().toISOString(), user_id: 'user-1', notification_type: 'task' },
      { id: '2', title: 'AI 建议就绪', content: '根据你昨天的学习数据，伴学助手已为你生成今日规划。', created_at: new Date().toISOString(), user_id: 'user-1', notification_type: 'ai' },
      { id: '3', title: '公告提醒', content: '系统计划于今晚 23:00 进行例行维护。', created_at: new Date(Date.now() - 86400000).toISOString(), read_at: new Date().toISOString(), user_id: 'user-1', notification_type: 'system' }
    ]
  }
}

const unreadCount = computed(() => notifications.value.filter(n => !n.read_at).length)

const markAllAsRead = async () => {
  try {
    await notificationApi.markAllAsRead()
    notifications.value.forEach(n => {
      if (!n.read_at) n.read_at = new Date().toISOString()
    })
  } catch (error) {
    notifications.value.forEach(n => {
      if (!n.read_at) n.read_at = new Date().toISOString()
    })
  }
}

const markSingleAsRead = async (item: NotificationOut) => {
  if (item.read_at) return
  try {
    await notificationApi.markAsRead(item.id)
    item.read_at = new Date().toISOString()
  } catch (error) {
    item.read_at = new Date().toISOString()
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

onMounted(() => {
  fetchNotifications()
  // Poll notifications every 60 seconds
  notificationTimer = setInterval(fetchNotifications, 60000)

  // Start study time heartbeat if student
  const userRole = localStorage.getItem('sp_role')
  if (userRole === 'student') {
    const sessionId = Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15)
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

onUnmounted(() => {
  if (notificationTimer) clearInterval(notificationTimer)
  if (heartbeatTimer) clearInterval(heartbeatTimer)
})
</script>

<template>
  <div class="flex w-screen h-screen overflow-hidden bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-zinc-50 transition-colors">
    <!-- App Sidebar -->
    <AppSidebar />

    <!-- Main Section -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden relative">
      
      <!-- Topbar Header -->
      <header class="h-16 border-b border-gray-200 dark:border-zinc-800 flex items-center justify-between px-8 bg-white dark:bg-zinc-900 flex-shrink-0 z-10">
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
            class="p-1.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-zinc-300 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors focus:outline-none"
          >
            <Sun v-if="isDark" class="w-4 h-4" />
            <Moon v-else class="w-4 h-4" />
          </button>

          <!-- Notification Bell Dropdown -->
          <div class="relative">
            <button
              @click="showNotifications = !showNotifications"
              class="p-1.5 rounded text-gray-400 hover:text-gray-600 dark:hover:text-zinc-300 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors focus:outline-none relative"
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
      <main class="flex-1 overflow-y-auto bg-gray-50 dark:bg-zinc-950 p-8 relative">
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
