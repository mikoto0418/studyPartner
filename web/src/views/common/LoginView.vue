<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  CornerUpLeft,
  Key,
  Lock,
  Mail,
  Moon,
  ShieldCheck,
  Sun,
  User
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api/modules/auth'
import { useAuthStore } from '../../stores/auth'
import { useTheme } from '../../composables/useTheme'

const router = useRouter()
const authStore = useAuthStore()
const { isDark, toggleTheme } = useTheme()

// Modes: 'login' | 'register' | 'reset'
const mode = ref<'login' | 'register' | 'reset'>('login')

// Roles: 'student' | 'teacher' | 'admin'
const activeRole = ref<'student' | 'teacher' | 'admin'>('student')

const roleOptions = [
  { value: 'student', label: '学生' },
  { value: 'teacher', label: '教师' },
  { value: 'admin', label: '管理员' }
] as const

const visibleRoles = computed(() =>
  roleOptions.filter((role) => mode.value === 'login' || role.value !== 'admin')
)

const headings = computed(() => {
  if (mode.value === 'register') {
    return {
      title: '创建学迹账号',
      desc: '注册后即可保存学习行为与学情记忆，让伴学智能体从第一天开始了解你。'
    }
  }
  if (mode.value === 'reset') {
    return {
      title: '重置登录密码',
      desc: '验证注册邮箱后重设密码，既有的学习数据与学情记忆不受影响。'
    }
  }
  return {
    title: '登录 MemoryPath',
    desc: '使用学迹账号进入 AI 伴学与智能体协同空间。'
  }
})

// Form State
const username = ref('')
const email = ref('')
const password = ref('')
const confirmPassword = ref('')
const code = ref('')
const loading = ref(false)

// Cooldown state for verification email code
const cooldown = ref(0)
let timer: number | null = null

const startCooldown = () => {
  cooldown.value = 60
  timer = window.setInterval(() => {
    if (cooldown.value > 0) {
      cooldown.value--
    } else {
      if (timer) {
        clearInterval(timer)
        timer = null
      }
    }
  }, 1000)
}

onUnmounted(() => {
  if (timer) clearInterval(timer)
})

const handleSendCode = async () => {
  if (!email.value) {
    ElMessage.warning('请先输入电子邮箱地址')
    return
  }
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(email.value)) {
    ElMessage.warning('请输入正确的邮箱格式')
    return
  }

  loading.value = true
  try {
    const actionType = mode.value === 'register' ? 'register' : 'reset_password'
    await authApi.sendCode({ email: email.value, action_type: actionType })
    ElMessage.success('验证码已成功发送，请查收邮箱')
    startCooldown()
  } catch (error) {
    // Error notification handled by response interceptor
  } finally {
    loading.value = false
  }
}

const handleLogin = async () => {
  if (!username.value || !password.value) {
    ElMessage.warning('请填写账号和密码')
    return
  }
  
  loading.value = true
  try {
    const response: any = await authApi.login({
      username: username.value,
      password: password.value
    })
    
    const data = response.data
    
    // Store session info
    authStore.login({
      token: data.access_token,
      role: data.user.roles[0]?.code || 'student',
      username: data.user.username,
      displayName: data.user.display_name === '未设置姓名' ? null : data.user.display_name || data.user.nickname || null
    })

    ElMessage.success('登录成功')
    
    const userRole = data.user.roles[0]?.code || 'student'
    if (userRole === 'admin') {
      router.push('/admin/overview')
    } else if (userRole === 'teacher') {
      router.push('/teacher/workbench')
    } else {
      router.push('/student/dashboard')
    }
  } catch (error) {
    // Error is handled by request interceptor
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!username.value || !email.value || !password.value || !code.value) {
    ElMessage.warning('请填写所有必填字段')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('密码长度不能少于 6 位')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await authApi.register({
      username: username.value,
      email: email.value,
      password: password.value,
      role: activeRole.value === 'admin' ? 'student' : activeRole.value, // Prevent admin self-registration
      code: code.value
    })

    ElMessage.success('注册成功！已为您自动登录')
    
    // Auto Login
    const loginRes: any = await authApi.login({
      username: username.value,
      password: password.value
    })
    const data = loginRes.data
    authStore.login({
      token: data.access_token,
      role: data.user.roles[0]?.code || 'student',
      username: data.user.username,
      displayName: data.user.display_name === '未设置姓名' ? null : data.user.display_name || data.user.nickname || null
    })
    
    const userRole = data.user.roles[0]?.code || 'student'
    if (userRole === 'teacher') {
      router.push('/teacher/workbench')
    } else {
      router.push('/student/dashboard')
    }
  } catch (error) {
    // Handled
  } finally {
    loading.value = false
  }
}

const handleResetPassword = async () => {
  if (!email.value || !password.value || !code.value) {
    ElMessage.warning('请填写所有必填字段')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('新密码长度不能少于 6 位')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  loading.value = true
  try {
    await authApi.resetPassword({
      email: email.value,
      new_password: password.value,
      code: code.value
    })
    ElMessage.success('密码重置成功，请使用新密码登录')
    switchMode('login')
  } catch (error) {
    // Handled
  } finally {
    loading.value = false
  }
}

const switchMode = (newMode: 'login' | 'register' | 'reset') => {
  mode.value = newMode
  password.value = ''
  confirmPassword.value = ''
  code.value = ''
}
</script>

<template>
  <div class="relative flex min-h-screen w-full overflow-hidden bg-gray-50 font-sans text-gray-900 transition-colors dark:bg-zinc-950 dark:text-zinc-50">
    <!-- 背景：克制的蓝色光晕 + 细网格，与平台整体视觉保持一致 -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden">
      <div class="absolute -left-32 -top-32 h-96 w-96 rounded-full bg-blue-500/10 blur-3xl"></div>
      <div class="absolute -bottom-40 -right-24 h-[28rem] w-[28rem] rounded-full bg-indigo-500/10 blur-3xl"></div>
      <div
        class="absolute inset-0 opacity-40 dark:opacity-20"
        style="background-image: linear-gradient(to right, rgba(148, 163, 184, 0.14) 1px, transparent 1px), linear-gradient(to bottom, rgba(148, 163, 184, 0.14) 1px, transparent 1px); background-size: 48px 48px; mask-image: radial-gradient(ellipse at center, black 25%, transparent 75%); -webkit-mask-image: radial-gradient(ellipse at center, black 25%, transparent 75%)"
      ></div>
    </div>

    <!-- 左侧品牌区：直接铺满 MemoryPath 学迹主视觉（浅色 / 深色两版） -->
    <aside
      class="relative z-10 hidden flex-shrink-0 overflow-hidden border-r border-gray-200/80 dark:border-zinc-800/80 lg:block"
      style="width: min(69vh, 52vw)"
    >
      <img
        src="/brand/login-hero-light.webp"
        alt="MemoryPath 学迹 · AI 伴学与智能体协同平台：让每一次学习，都留下可追溯的痕迹"
        class="absolute inset-0 h-full w-full object-cover dark:hidden"
      />
      <img
        src="/brand/login-hero-dark.webp"
        alt="MemoryPath 学迹 · AI 伴学与智能体协同平台：让每一次学习，都留下可追溯的痕迹"
        class="absolute inset-0 hidden h-full w-full object-cover dark:block"
      />
    </aside>

    <!-- 右侧表单区 -->
    <main class="relative z-10 flex flex-1 flex-col items-center justify-center px-5 py-10 sm:px-8">
      <button
        type="button"
        class="ui-icon-button absolute right-5 top-5"
        :title="isDark ? '切换到浅色模式' : '切换到深色模式'"
        @click="toggleTheme"
      >
        <Sun v-if="isDark" class="h-4 w-4" />
        <Moon v-else class="h-4 w-4" />
      </button>

      <div class="w-full max-w-[380px]">
        <!-- 移动端品牌头 -->
        <div class="mb-8 flex items-center gap-3 lg:hidden">
          <img
            src="/brand/mp-logo.png"
            alt="MemoryPath 学迹"
            class="h-9 w-9 flex-shrink-0"
          />
          <div class="leading-tight">
            <p class="text-sm font-semibold tracking-tight text-gray-900 dark:text-zinc-50">MemoryPath</p>
            <p class="text-[10px] text-gray-400 dark:text-zinc-500">学迹 · AI 伴学与智能体协同平台</p>
          </div>
        </div>

        <div class="mb-6 space-y-1.5">
          <h2 class="text-xl font-semibold tracking-tight text-gray-900 dark:text-zinc-50">{{ headings.title }}</h2>
          <p class="text-xs leading-relaxed text-gray-400 dark:text-zinc-500">{{ headings.desc }}</p>
        </div>

        <!-- 角色切换（重置密码时隐藏） -->
        <div
          v-if="mode !== 'reset'"
          class="mb-5 flex rounded-md border border-gray-200 bg-gray-100/70 p-1 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <button
            v-for="role in visibleRoles"
            :key="role.value"
            type="button"
            class="flex-1 rounded px-2 py-1.5 text-xs font-semibold transition-colors"
            :class="activeRole === role.value
              ? 'bg-white text-blue-700 shadow-sm dark:bg-zinc-800 dark:text-blue-300'
              : 'text-gray-500 hover:text-gray-800 dark:text-zinc-400 dark:hover:text-zinc-200'"
            @click="activeRole = role.value"
          >
            {{ role.label }}
          </button>
        </div>

        <!-- ================= 登录 ================= -->
        <form v-if="mode === 'login'" class="space-y-4" @submit.prevent="handleLogin">
          <div class="space-y-1.5">
            <label for="login-username" class="ui-field-label">账号</label>
            <div class="relative flex items-center">
              <User class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="login-username"
                v-model="username"
                type="text"
                autocomplete="username"
                placeholder="用户名或邮箱"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <div class="flex items-center justify-between">
              <label for="login-password" class="ui-field-label">密码</label>
              <button
                type="button"
                class="text-xs font-medium text-blue-600 hover:underline dark:text-blue-400"
                @click="switchMode('reset')"
              >
                忘记密码？
              </button>
            </div>
            <div class="relative flex items-center">
              <Lock class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="login-password"
                v-model="password"
                type="password"
                autocomplete="current-password"
                placeholder="请输入密码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="mt-1 flex w-full items-center justify-center gap-1.5 rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            <span v-if="loading">正在登录...</span>
            <template v-else>
              <span>进入 MemoryPath</span>
              <ArrowRight class="h-4 w-4" />
            </template>
          </button>

          <div class="pt-1 text-center text-xs text-gray-500 dark:text-zinc-400">
            还没有账号？
            <button type="button" class="font-semibold text-blue-600 hover:underline dark:text-blue-400" @click="switchMode('register')">
              立即注册
            </button>
          </div>
        </form>

        <!-- ================= 注册 ================= -->
        <form v-else-if="mode === 'register'" class="space-y-4" @submit.prevent="handleRegister">
          <div class="space-y-1.5">
            <label for="register-username" class="ui-field-label">用户名</label>
            <div class="relative flex items-center">
              <User class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="register-username"
                v-model="username"
                type="text"
                autocomplete="username"
                placeholder="你的个性用户名"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="register-email" class="ui-field-label">电子邮箱</label>
            <div class="relative flex items-center">
              <Mail class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="register-email"
                v-model="email"
                type="email"
                autocomplete="email"
                placeholder="用于接收验证码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="register-code" class="ui-field-label">邮箱验证码</label>
            <div class="flex items-center gap-2">
              <div class="relative flex flex-1 items-center">
                <Key class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
                <input
                  id="register-code"
                  v-model="code"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  placeholder="6 位验证码"
                  :disabled="loading"
                  required
                  class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
                />
              </div>
              <button
                type="button"
                :disabled="cooldown > 0 || loading"
                class="shrink-0 rounded-md border border-gray-200 bg-white px-3 py-2.5 text-xs font-semibold text-blue-600 transition hover:border-blue-200 hover:bg-blue-50 disabled:pointer-events-none disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-blue-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/20"
                @click="handleSendCode"
              >
                {{ cooldown > 0 ? `${cooldown}s` : '发送验证码' }}
              </button>
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="register-password" class="ui-field-label">设定密码</label>
            <div class="relative flex items-center">
              <Lock class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="register-password"
                v-model="password"
                type="password"
                autocomplete="new-password"
                placeholder="最少 6 位密码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="register-confirm" class="ui-field-label">确认密码</label>
            <div class="relative flex items-center">
              <ShieldCheck class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="register-confirm"
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
                placeholder="请再次输入密码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="mt-1 flex w-full items-center justify-center rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {{ loading ? '正在创建账号...' : '创建账号并登录' }}
          </button>

          <div class="pt-1 text-center">
            <button
              type="button"
              class="inline-flex items-center gap-1 text-xs font-medium text-gray-400 transition hover:text-gray-600 dark:text-zinc-500 dark:hover:text-zinc-300"
              @click="switchMode('login')"
            >
              <CornerUpLeft class="h-3.5 w-3.5" />
              返回登录
            </button>
          </div>
        </form>

        <!-- ================= 重置密码 ================= -->
        <form v-else-if="mode === 'reset'" class="space-y-4" @submit.prevent="handleResetPassword">
          <div class="space-y-1.5">
            <label for="reset-email" class="ui-field-label">注册邮箱</label>
            <div class="relative flex items-center">
              <Mail class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="reset-email"
                v-model="email"
                type="email"
                autocomplete="email"
                placeholder="请输入绑定邮箱"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="reset-code" class="ui-field-label">邮箱验证码</label>
            <div class="flex items-center gap-2">
              <div class="relative flex flex-1 items-center">
                <Key class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
                <input
                  id="reset-code"
                  v-model="code"
                  type="text"
                  inputmode="numeric"
                  autocomplete="one-time-code"
                  maxlength="6"
                  placeholder="6 位验证码"
                  :disabled="loading"
                  required
                  class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
                />
              </div>
              <button
                type="button"
                :disabled="cooldown > 0 || loading"
                class="shrink-0 rounded-md border border-gray-200 bg-white px-3 py-2.5 text-xs font-semibold text-blue-600 transition hover:border-blue-200 hover:bg-blue-50 disabled:pointer-events-none disabled:opacity-50 dark:border-zinc-800 dark:bg-zinc-900 dark:text-blue-400 dark:hover:border-blue-900 dark:hover:bg-blue-950/20"
                @click="handleSendCode"
              >
                {{ cooldown > 0 ? `${cooldown}s` : '发送验证码' }}
              </button>
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="reset-password" class="ui-field-label">设定新密码</label>
            <div class="relative flex items-center">
              <Lock class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="reset-password"
                v-model="password"
                type="password"
                autocomplete="new-password"
                placeholder="最少 6 位新密码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <div class="space-y-1.5">
            <label for="reset-confirm" class="ui-field-label">确认新密码</label>
            <div class="relative flex items-center">
              <ShieldCheck class="pointer-events-none absolute left-3 h-4 w-4 text-gray-400 dark:text-zinc-500" />
              <input
                id="reset-confirm"
                v-model="confirmPassword"
                type="password"
                autocomplete="new-password"
                placeholder="请再次输入新密码"
                :disabled="loading"
                required
                class="w-full rounded-md border border-gray-200 bg-gray-50 py-2.5 pl-9 pr-3 text-sm text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-blue-500 focus:bg-white disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-50 dark:placeholder:text-zinc-600 dark:focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="loading"
            class="mt-1 flex w-full items-center justify-center rounded-md bg-blue-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500 active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {{ loading ? '正在提交...' : '重置密码' }}
          </button>

          <div class="pt-1 text-center">
            <button
              type="button"
              class="inline-flex items-center gap-1 text-xs font-medium text-gray-400 transition hover:text-gray-600 dark:text-zinc-500 dark:hover:text-zinc-300"
              @click="switchMode('login')"
            >
              <CornerUpLeft class="h-3.5 w-3.5" />
              返回登录
            </button>
          </div>
        </form>

        <p class="mt-8 text-center text-[10px] leading-relaxed text-gray-400 dark:text-zinc-600">
          © 2026 MemoryPath 学迹 · AI 伴学与智能体协同平台
        </p>
      </div>
    </main>
  </div>
</template>
