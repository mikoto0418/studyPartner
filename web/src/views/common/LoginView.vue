<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Mail, Key, ShieldCheck, ArrowRight, CornerUpLeft } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api/modules/auth'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

// Modes: 'login' | 'register' | 'reset'
const mode = ref<'login' | 'register' | 'reset'>('login')

// Roles: 'student' | 'teacher' | 'admin'
const activeRole = ref<'student' | 'teacher' | 'admin'>('student')

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
  <div class="relative flex flex-col items-center justify-center w-screen h-screen bg-slate-950 text-zinc-50 overflow-hidden font-sans">
    
    <!-- Background Animated Gradients -->
    <div class="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-950 to-slate-950 z-0"></div>
    <div class="absolute -top-40 -left-40 w-96 h-96 rounded-full bg-indigo-500/10 blur-[120px] pointer-events-none"></div>
    <div class="absolute -bottom-40 -right-40 w-96 h-96 rounded-full bg-violet-600/10 blur-[120px] pointer-events-none"></div>

    <!-- Core Card Wrapper (Glassmorphism) -->
    <div class="w-full max-w-md p-8 bg-slate-900/50 backdrop-blur-md border border-slate-800 rounded-2xl shadow-2xl z-10 transition-all duration-300">
      
      <!-- Brand Header -->
      <div class="flex flex-col items-center justify-center space-y-2 mb-6">
        <div class="w-10 h-10 rounded-lg bg-gradient-to-tr from-blue-600 to-violet-600 flex items-center justify-center text-white font-extrabold text-xl shadow-md">
          SP
        </div>
        <h1 class="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-200 bg-clip-text text-transparent">
          AI伴学与智能体协同平台
        </h1>
        <p class="text-xs text-slate-400">
          极简智能学习协同空间 · 工业级升级版
        </p>
      </div>

      <!-- ROLE TAB SELECTOR (Login & Register Modes only) -->
      <div v-if="mode !== 'reset'" class="flex w-full bg-slate-950/60 p-1 rounded-lg mb-6 border border-slate-800/80 text-xs">
        <button
          @click="activeRole = 'student'"
          class="flex-1 py-1.5 rounded-md text-center transition-all focus:outline-none"
          :class="activeRole === 'student' ? 'bg-blue-600/80 text-white font-medium shadow-sm' : 'text-slate-400 hover:text-slate-200'"
        >
          学生{{ mode === 'register' ? '注册' : '登录' }}
        </button>
        <button
          @click="activeRole = 'teacher'"
          class="flex-1 py-1.5 rounded-md text-center transition-all focus:outline-none"
          :class="activeRole === 'teacher' ? 'bg-blue-600/80 text-white font-medium shadow-sm' : 'text-slate-400 hover:text-slate-200'"
        >
          教师{{ mode === 'register' ? '注册' : '登录' }}
        </button>
        <button
          v-if="mode === 'login'"
          @click="activeRole = 'admin'"
          class="flex-1 py-1.5 rounded-md text-center transition-all focus:outline-none"
          :class="activeRole === 'admin' ? 'bg-blue-600/80 text-white font-medium shadow-sm' : 'text-slate-400 hover:text-slate-200'"
        >
          管理员
        </button>
      </div>

      <!-- ================= LOGIN FORM ================= -->
      <form v-if="mode === 'login'" @submit.prevent="handleLogin" class="space-y-4">
        <!-- Account input -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">账号</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <User class="w-4 h-4" />
            </span>
            <input
              v-model="username"
              type="text"
              placeholder="用户名或邮箱"
              class="w-full pl-9 pr-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Password input -->
        <div class="space-y-1.5">
          <div class="flex justify-between items-center">
            <label class="text-xs text-slate-400 font-medium">密码</label>
            <button type="button" @click="switchMode('reset')" class="text-xs text-blue-500 hover:underline">忘记密码?</button>
          </div>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <Lock class="w-4 h-4" />
            </span>
            <input
              v-model="password"
              type="password"
              placeholder="请输入密码"
              class="w-full pl-9 pr-3 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Action Button -->
        <button
          type="submit"
          class="w-full mt-4 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-lg text-sm shadow-md transition-all duration-150 transform active:scale-[0.98] flex items-center justify-center space-x-1"
          :disabled="loading"
        >
          <span v-if="loading">正在登录...</span>
          <span v-else class="flex items-center space-x-1">
            <span>进入协同空间</span>
            <ArrowRight class="w-4 h-4" />
          </span>
        </button>

        <div class="text-center pt-2">
          <span class="text-xs text-slate-500">还没有账号? </span>
          <button type="button" @click="switchMode('register')" class="text-xs text-blue-400 hover:underline">立即注册</button>
        </div>
      </form>

      <!-- ================= REGISTER FORM ================= -->
      <form v-else-if="mode === 'register'" @submit.prevent="handleRegister" class="space-y-4">
        <!-- Username -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">用户名</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <User class="w-4 h-4" />
            </span>
            <input
              v-model="username"
              type="text"
              placeholder="您的个性用户名"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Email -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">电子邮箱</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <Mail class="w-4 h-4" />
            </span>
            <input
              v-model="email"
              type="email"
              placeholder="请输入绑定邮箱"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Verification Code -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">邮箱验证码</label>
          <div class="flex space-x-2">
            <div class="relative flex-1 flex items-center">
              <span class="absolute left-3 text-slate-500">
                <Key class="w-4 h-4" />
              </span>
              <input
                v-model="code"
                type="text"
                maxlength="6"
                placeholder="6位验证码"
                class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
                :disabled="loading"
                required
              />
            </div>
            <button
              type="button"
              @click="handleSendCode"
              class="px-3 text-xs border border-slate-800 bg-slate-950 text-blue-400 hover:bg-slate-900 rounded-lg font-medium transition-all disabled:opacity-50"
              :disabled="cooldown > 0 || loading"
            >
              {{ cooldown > 0 ? `${cooldown}s` : '发送验证码' }}
            </button>
          </div>
        </div>

        <!-- Password -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">设定密码</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <Lock class="w-4 h-4" />
            </span>
            <input
              v-model="password"
              type="password"
              placeholder="最少 6 位密码"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Confirm Password -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">确认密码</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <ShieldCheck class="w-4 h-4" />
            </span>
            <input
              v-model="confirmPassword"
              type="password"
              placeholder="请再次输入密码"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          class="w-full py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-lg text-sm transition-all"
          :disabled="loading"
        >
          确认注册并进入系统
        </button>

        <div class="text-center pt-1">
          <button type="button" @click="switchMode('login')" class="inline-flex items-center text-xs text-slate-400 hover:text-slate-200 space-x-1">
            <CornerUpLeft class="w-3.5 h-3.5" />
            <span>返回登录</span>
          </button>
        </div>
      </form>

      <!-- ================= RESET PASSWORD FORM ================= -->
      <form v-else-if="mode === 'reset'" @submit.prevent="handleResetPassword" class="space-y-4">
        <p class="text-xs text-slate-400 mb-2 leading-relaxed">
          请输入您的注册邮箱，我们将向该邮箱发送一个 6 位验证码以重置密码。
        </p>
        
        <!-- Email -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">注册邮箱</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <Mail class="w-4 h-4" />
            </span>
            <input
              v-model="email"
              type="email"
              placeholder="请输入绑定邮箱"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Code -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">邮箱验证码</label>
          <div class="flex space-x-2">
            <div class="relative flex-1 flex items-center">
              <span class="absolute left-3 text-slate-500">
                <Key class="w-4 h-4" />
              </span>
              <input
                v-model="code"
                type="text"
                maxlength="6"
                placeholder="6位验证码"
                class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
                :disabled="loading"
                required
              />
            </div>
            <button
              type="button"
              @click="handleSendCode"
              class="px-3 text-xs border border-slate-800 bg-slate-950 text-blue-400 hover:bg-slate-900 rounded-lg font-medium transition-all disabled:opacity-50"
              :disabled="cooldown > 0 || loading"
            >
              {{ cooldown > 0 ? `${cooldown}s` : '发送验证码' }}
            </button>
          </div>
        </div>

        <!-- New Password -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">设定新密码</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <Lock class="w-4 h-4" />
            </span>
            <input
              v-model="password"
              type="password"
              placeholder="最少 6 位新密码"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <!-- Confirm New Password -->
        <div class="space-y-1.5">
          <label class="text-xs text-slate-400 font-medium">确认新密码</label>
          <div class="relative flex items-center">
            <span class="absolute left-3 text-slate-500">
              <ShieldCheck class="w-4 h-4" />
            </span>
            <input
              v-model="confirmPassword"
              type="password"
              placeholder="请再次输入新密码"
              class="w-full pl-9 pr-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 transition-all"
              :disabled="loading"
              required
            />
          </div>
        </div>

        <button
          type="submit"
          class="w-full py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium rounded-lg text-sm transition-all"
          :disabled="loading"
        >
          确定重置密码
        </button>

        <div class="text-center pt-1">
          <button type="button" @click="switchMode('login')" class="inline-flex items-center text-xs text-slate-400 hover:text-slate-200 space-x-1">
            <CornerUpLeft class="w-3.5 h-3.5" />
            <span>返回登录</span>
          </button>
        </div>
      </form>

    </div>
  </div>
</template>
