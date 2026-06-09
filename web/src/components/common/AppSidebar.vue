<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  LayoutDashboard,
  MessageSquare,
  Calendar,
  BookOpen,
  Tv,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Users,
  Settings2,
  GitBranch,
  BarChart3,
  TrendingUp,
  Megaphone
} from 'lucide-vue-next'

const router = useRouter()
const route = useRoute()

const collapsed = ref(false)
const userRole = ref(localStorage.getItem('sp_role') || 'student')
const displayName = ref(localStorage.getItem('sp_display_name') || '')
const username = ref(localStorage.getItem('sp_username') || '')
const shownName = computed(() => displayName.value || '未设置姓名')
const avatarText = computed(() => (displayName.value || '未').charAt(0).toUpperCase())

// Define menu items based on role
const menuItems = computed(() => {
  if (userRole.value === 'admin') {
    return [
      { name: '管理概览', path: '/admin/overview', icon: LayoutDashboard },
      { name: '用户管理', path: '/admin/users', icon: Users },
      { name: '模型配置', path: '/admin/llm-configs', icon: Settings2 },
      { name: '公告发布', path: '/admin/announcements', icon: Megaphone },
      { name: '系统设置', path: '/admin/settings', icon: Settings }
    ]
  } else if (userRole.value === 'teacher') {
    return [
      { name: '工作台', path: '/teacher/workbench', icon: LayoutDashboard },
      { name: '学生列表', path: '/teacher/students', icon: Users },
      { name: '任务管理', path: '/teacher/tasks', icon: ClipboardList },
      { name: '路径任务', path: '/teacher/learning-paths', icon: GitBranch },
      { name: '班级看板', path: '/teacher/classes', icon: BarChart3 },
      { name: '公告发布', path: '/teacher/announcements', icon: Megaphone }
    ]
  } else {
    // Default student menu
    return [
      { name: '仪表盘', path: '/student/dashboard', icon: LayoutDashboard },
      { name: 'AI伴学', path: '/student/ai-chat', icon: MessageSquare },
      { name: '月历计划', path: '/student/calendar', icon: Calendar },
      { name: '知识库', path: '/student/knowledge', icon: BookOpen },
      { name: 'B站学习', path: '/student/bilibili', icon: Tv },
      { name: '学习路径', path: '/student/learning-paths', icon: GitBranch },
      { name: '成长全览', path: '/student/growth', icon: TrendingUp }
    ]
  }
})

const currentPath = computed(() => route.path)

const toggleCollapse = () => {
  collapsed.value = !collapsed.value
}

const handleLogout = () => {
  localStorage.clear()
  router.push('/login')
}

const refreshIdentity = () => {
  displayName.value = localStorage.getItem('sp_display_name') || ''
  username.value = localStorage.getItem('sp_username') || ''
}

onMounted(() => {
  window.addEventListener('profile-updated', refreshIdentity)
})

onUnmounted(() => {
  window.removeEventListener('profile-updated', refreshIdentity)
})
</script>

<template>
  <aside
    class="h-full bg-white dark:bg-zinc-900 border-r border-gray-200 dark:border-zinc-800 flex flex-col justify-between py-6 px-4 layout-transition relative z-20"
    :class="collapsed ? 'w-20' : 'w-60'"
  >
    <!-- Top Brand Area -->
    <div>
      <div class="flex items-center justify-between mb-8 px-2">
        <div class="flex items-center space-x-2.5 overflow-hidden">
          <div class="w-8 h-8 rounded bg-blue-600 flex-shrink-0 flex items-center justify-center text-white font-bold text-base shadow-sm">
            A
          </div>
          <span
            v-if="!collapsed"
            class="text-sm font-semibold text-gray-900 dark:text-zinc-50 whitespace-nowrap transition-all duration-200"
          >
            AI伴学协同平台
          </span>
        </div>
        
        <!-- Collapse Trigger Icon -->
        <button
          @click="toggleCollapse"
          class="w-6 h-6 rounded border border-gray-200 dark:border-zinc-800 flex items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-zinc-300 hover:bg-gray-50 dark:hover:bg-zinc-800 transition-colors focus:outline-none"
        >
          <ChevronLeft v-if="!collapsed" class="w-3.5 h-3.5" />
          <ChevronRight v-else class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Navigation Menu List -->
      <nav class="space-y-1">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="flex items-center space-x-3 px-3 py-2.5 text-sm rounded-md cursor-pointer transition-all duration-200"
          :class="currentPath === item.path
            ? 'bg-gray-100 dark:bg-zinc-800 text-blue-600 dark:text-blue-500 font-medium'
            : 'text-gray-500 dark:text-zinc-400 hover:bg-gray-50 dark:hover:bg-zinc-800/50 hover:text-gray-900 dark:hover:text-zinc-100'"
        >
          <component :is="item.icon" class="w-4 h-4 flex-shrink-0" />
          <span v-if="!collapsed" class="whitespace-nowrap transition-all duration-200">
            {{ item.name }}
          </span>
        </router-link>
      </nav>
    </div>

    <!-- Bottom Profile Area -->
    <div class="border-t border-gray-200 dark:border-zinc-800 pt-4 px-1 space-y-2">
      <!-- User info card -->
      <div class="flex items-center space-x-3 overflow-hidden">
        <div class="w-8 h-8 rounded-full bg-gray-200 dark:bg-zinc-800 flex items-center justify-center text-xs font-semibold text-gray-600 dark:text-zinc-300 flex-shrink-0">
          {{ avatarText }}
        </div>
        <div v-if="!collapsed" class="overflow-hidden">
          <p class="text-xs font-medium text-gray-900 dark:text-zinc-50 truncate">{{ shownName }}</p>
          <p class="text-[10px] text-gray-400 dark:text-zinc-500 truncate capitalize">{{ userRole }}</p>
        </div>
      </div>

      <!-- Settings & Logout actions -->
      <div class="flex flex-col space-y-0.5 pt-2">
        <router-link
          to="/profile"
          class="flex items-center space-x-3 px-2 py-1.5 text-xs text-gray-400 dark:text-zinc-500 hover:text-gray-900 dark:hover:text-zinc-100 rounded"
        >
          <Settings class="w-3.5 h-3.5" />
          <span v-if="!collapsed">个人设置</span>
        </router-link>
        <button
          @click="handleLogout"
          class="flex items-center space-x-3 px-2 py-1.5 text-xs text-red-500 hover:bg-red-50 dark:hover:bg-red-950/20 rounded w-full text-left"
        >
          <LogOut class="w-3.5 h-3.5" />
          <span v-if="!collapsed">退出系统</span>
        </button>
      </div>
    </div>
  </aside>
</template>
