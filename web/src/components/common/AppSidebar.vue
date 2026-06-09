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

const MOBILE_BREAKPOINT = 768
const collapsed = ref(false)
const userRole = ref(localStorage.getItem('sp_role') || 'student')
const displayName = ref(localStorage.getItem('sp_display_name') || '')
const username = ref(localStorage.getItem('sp_username') || '')
const shownName = computed(() => displayName.value || '未设置姓名')
const avatarText = computed(() => (displayName.value || '未').charAt(0).toUpperCase())
const roleLabel = computed(() => {
  if (userRole.value === 'admin') return '系统管理员'
  if (userRole.value === 'teacher') return '教师端'
  return '学生端'
})

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
const isActivePath = (path: string) => currentPath.value === path || currentPath.value.startsWith(`${path}/`)

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

const syncCollapsedForViewport = () => {
  if (window.innerWidth < MOBILE_BREAKPOINT) {
    collapsed.value = true
  }
}

onMounted(() => {
  syncCollapsedForViewport()
  window.addEventListener('resize', syncCollapsedForViewport)
  window.addEventListener('profile-updated', refreshIdentity)
})

onUnmounted(() => {
  window.removeEventListener('resize', syncCollapsedForViewport)
  window.removeEventListener('profile-updated', refreshIdentity)
})
</script>

<template>
  <aside
    class="h-full border-r border-gray-200 bg-white px-3 py-4 layout-transition relative z-20 flex flex-col dark:border-zinc-800 dark:bg-zinc-900"
    :class="collapsed ? 'w-20' : 'w-64'"
  >
    <div class="space-y-4">
      <div class="flex items-center justify-between gap-2 px-1">
        <div class="flex min-w-0 items-center gap-2.5 overflow-hidden">
          <div class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md bg-blue-600 text-base font-bold text-white shadow-sm">
            A
          </div>
          <span
            v-if="!collapsed"
            class="truncate text-sm font-semibold text-gray-900 transition-all duration-200 dark:text-zinc-50"
          >
            AI伴学协同平台
          </span>
        </div>

        <button
          @click="toggleCollapse"
          class="ui-icon-button h-7 w-7 flex-shrink-0"
          title="折叠侧边栏"
        >
          <ChevronLeft v-if="!collapsed" class="h-3.5 w-3.5" />
          <ChevronRight v-else class="h-3.5 w-3.5" />
        </button>
      </div>

      <div
        class="rounded-lg border border-gray-200 bg-gray-50/70 p-3 dark:border-zinc-800 dark:bg-zinc-950/50"
        :class="collapsed ? 'px-2' : ''"
      >
        <div class="flex items-center gap-3">
          <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md bg-white text-xs font-bold text-blue-600 shadow-sm ring-1 ring-gray-200 dark:bg-zinc-900 dark:ring-zinc-800">
            {{ avatarText }}
          </div>
          <div v-if="!collapsed" class="min-w-0">
            <p class="truncate text-xs font-semibold text-gray-900 dark:text-zinc-50">{{ shownName }}</p>
            <p class="mt-0.5 truncate text-[10px] text-gray-400 dark:text-zinc-500">{{ roleLabel }} · {{ username || '未同步账号' }}</p>
          </div>
        </div>
      </div>

      <nav class="space-y-1">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          class="group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-all duration-200"
          :class="isActivePath(item.path)
            ? 'bg-blue-50 text-blue-700 font-semibold dark:bg-blue-950/20 dark:text-blue-300'
            : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100'"
          :title="collapsed ? item.name : undefined"
        >
          <span
            class="absolute left-0 top-2 bottom-2 w-0.5 rounded-full bg-blue-600 opacity-0 transition-opacity"
            :class="isActivePath(item.path) ? 'opacity-100' : 'group-hover:opacity-40'"
          ></span>
          <component :is="item.icon" class="h-4 w-4 flex-shrink-0" />
          <span v-if="!collapsed" class="whitespace-nowrap transition-all duration-200">
            {{ item.name }}
          </span>
        </router-link>
      </nav>
    </div>

    <div class="mt-auto space-y-1 border-t border-gray-200 pt-3 dark:border-zinc-800">
      <router-link
        to="/profile"
        class="flex items-center gap-3 rounded-md px-3 py-2 text-xs font-semibold text-gray-500 transition hover:bg-gray-50 hover:text-gray-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100"
        :title="collapsed ? '个人设置' : undefined"
      >
        <Settings class="h-3.5 w-3.5" />
        <span v-if="!collapsed">个人设置</span>
      </router-link>
      <button
        @click="handleLogout"
        class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-xs font-semibold text-red-500 transition hover:bg-red-50 dark:hover:bg-red-950/20"
        :title="collapsed ? '退出系统' : undefined"
      >
        <LogOut class="h-3.5 w-3.5" />
        <span v-if="!collapsed">退出系统</span>
      </button>
    </div>
  </aside>
</template>
