<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api/modules/auth'
import type { UserOut } from '../../api/modules/user'
import { useAuthStore } from '../../stores/auth'

const emit = defineEmits<{ ready: [] }>()
const router = useRouter()
const auth = useAuthStore()
const ready = ref(false)
const loading = ref(true)
const failed = ref(false)
const pending = ref(false)
const saving = ref(false)
const username = ref('')
const name = ref('')

function accept(user: UserOut) {
  username.value = user.username
  pending.value = Boolean(user.requires_identity_confirmation)
  if (pending.value) return
  auth.username = user.username
  auth.displayName = user.display_name || null
  localStorage.setItem('sp_username', user.username)
  if (user.display_name && user.display_name !== '未设置姓名') {
    localStorage.setItem('sp_display_name', user.display_name)
  } else {
    localStorage.removeItem('sp_display_name')
  }
  window.dispatchEvent(new Event('profile-updated'))
  ready.value = true
  emit('ready')
}

async function load() {
  loading.value = true
  failed.value = false
  try {
    const res = await authApi.getMe()
    accept(res.data)
  } catch {
    failed.value = true
  } finally {
    loading.value = false
  }
}

async function save() {
  if (saving.value) return
  const value = name.value.trim()
  if (!value || value.length > 50 || /[\u0000-\u001f]/.test(value)) {
    ElMessage.warning('请输入本人姓名，长度不超过 50 个字符')
    return
  }
  saving.value = true
  try {
    const res = await authApi.confirmIdentity(value)
    accept(res.data)
    ElMessage.success('姓名已保存')
  } catch {
    // 请求层展示错误；保留输入并允许重试。
  } finally {
    saving.value = false
  }
}

function logout() {
  auth.logout()
  router.replace('/login')
}

onMounted(load)
</script>

<template>
  <slot v-if="ready" />
  <div v-else class="flex min-h-screen items-center justify-center bg-gray-50 p-6 text-gray-700 dark:bg-zinc-950 dark:text-zinc-200">
    <div v-if="loading" role="status">正在确认账号信息…</div>
    <div v-else-if="failed" class="space-y-4 text-center">
      <p>账号信息读取失败，请检查连接后重试。</p>
      <el-button type="primary" @click="load">重试</el-button>
      <el-button @click="logout">退出登录</el-button>
    </div>
    <el-dialog
      :model-value="pending"
      title="请填写本人姓名"
      width="min(440px, 92vw)"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      align-center
    >
      <form class="space-y-5" @submit.prevent="save">
        <p>当前账号：<strong>{{ username }}</strong></p>
        <p class="text-sm text-gray-500">请填写你的真实姓名，老师将通过姓名对应本次二面的作答和成绩。只需填写一次。</p>
        <label for="identity-name" class="block">
          <span class="mb-2 block">本人姓名</span>
          <el-input id="identity-name" v-model="name" maxlength="50" placeholder="请输入本人姓名" autocomplete="name" :disabled="saving" autofocus />
        </label>
        <div class="flex justify-end gap-3">
          <el-button :disabled="saving" @click="logout">换个账号</el-button>
          <el-button type="primary" native-type="submit" :loading="saving">确认并进入</el-button>
        </div>
      </form>
    </el-dialog>
  </div>
</template>
