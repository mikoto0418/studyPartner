<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { authApi } from '../../api/modules/auth'
import { userApi, type UserOut } from '../../api/modules/user'

const currentUser = ref<UserOut | null>(null)
const loading = ref(false)
const savingProfile = ref(false)
const savingPassword = ref(false)

const profileForm = ref({
  nickname: '',
  email: '',
  phone: '',
  student_id: '',
  grade: '',
  major: '',
  research_direction: '',
  bio: ''
})

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const activeTab = ref('profile')

const displayName = computed(() => profileForm.value.nickname.trim() || '未设置姓名')
const avatarText = computed(() => (profileForm.value.nickname.trim() || '未').charAt(0).toUpperCase())
const isStudent = computed(() => currentUser.value?.roles.some((role) => role.code === 'student') || false)

const loadProfile = async () => {
  loading.value = true
  try {
    const res = await authApi.getMe()
    currentUser.value = res.data
    const profile = res.data?.student_profile
    profileForm.value = {
      nickname: res.data?.nickname || '',
      email: res.data?.email || '',
      phone: res.data?.phone || '',
      student_id: profile?.student_id || '',
      grade: profile?.grade || '',
      major: profile?.major || '',
      research_direction: profile?.research_direction || '',
      bio: profile?.bio || ''
    }
    if (res.data) syncDisplayStorage(res.data)
  } catch (error) {
    console.warn('Failed to load profile', error)
  } finally {
    loading.value = false
  }
}

function syncDisplayStorage(user: UserOut) {
  localStorage.setItem('sp_username', user.username)
  if (user.display_name && user.display_name !== '未设置姓名') {
    localStorage.setItem('sp_display_name', user.display_name)
  } else {
    localStorage.removeItem('sp_display_name')
  }
  window.dispatchEvent(new Event('profile-updated'))
}

const handleSaveProfile = async () => {
  if (!currentUser.value) return
  if (!profileForm.value.email.trim()) {
    ElMessage.warning('邮箱不能为空')
    return
  }

  savingProfile.value = true
  try {
    const userRes = await userApi.updateUser(currentUser.value.id, {
      nickname: profileForm.value.nickname.trim() || null,
      email: profileForm.value.email.trim(),
      phone: profileForm.value.phone.trim() || null
    })
    const updatedUser = userRes.data
    let mergedUser = updatedUser

    if (isStudent.value) {
      const profileRes = await userApi.updateStudentProfile(updatedUser.id, {
        student_id: profileForm.value.student_id.trim() || null,
        grade: profileForm.value.grade.trim() || null,
        major: profileForm.value.major.trim() || null,
        research_direction: profileForm.value.research_direction.trim() || null,
        bio: profileForm.value.bio.trim() || null
      })
      mergedUser = {
        ...updatedUser,
        student_profile: profileRes.data
      }
    }

    currentUser.value = mergedUser
    syncDisplayStorage(mergedUser)
    ElMessage.success('个人信息已保存')
  } catch (error) {
    console.warn('Failed to save profile', error)
  } finally {
    savingProfile.value = false
  }
}

const handleChangePassword = async () => {
  if (!oldPassword.value || !newPassword.value || !confirmPassword.value) {
    ElMessage.warning('请填写完整密码信息')
    return
  }
  if (newPassword.value.length < 6) {
    ElMessage.warning('新密码长度不能少于 6 位')
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  savingPassword.value = true
  try {
    await authApi.changePassword({
      old_password: oldPassword.value,
      new_password: newPassword.value
    })
    oldPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    ElMessage.success('密码已更新')
  } catch (error) {
    console.warn('Failed to change password', error)
  } finally {
    savingPassword.value = false
  }
}

onMounted(loadProfile)
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 space-y-6" v-loading="loading">
    <div class="flex gap-8">
      <div class="w-48 space-y-1">
        <button
          @click="activeTab = 'profile'"
          class="w-full text-left px-3 py-2 text-xs rounded transition-colors"
          :class="activeTab === 'profile' ? 'bg-gray-200 dark:bg-zinc-800 text-gray-900 dark:text-zinc-50 font-semibold' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-zinc-800/50'"
        >
          个人信息
        </button>
        <button
          @click="activeTab = 'security'"
          class="w-full text-left px-3 py-2 text-xs rounded transition-colors"
          :class="activeTab === 'security' ? 'bg-gray-200 dark:bg-zinc-800 text-gray-900 dark:text-zinc-50 font-semibold' : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-zinc-800/50'"
        >
          安全设置
        </button>
      </div>

      <div class="flex-1 minimal-card p-8">
        <div v-if="activeTab === 'profile'" class="space-y-6">
          <div class="border-b border-gray-100 dark:border-zinc-800 pb-3">
            <h3 class="text-sm font-semibold">基本信息</h3>
            <p class="mt-1 text-[10px] text-gray-400">姓名用于侧边栏、教师端学生列表和 AI 伴学称呼；登录用户名不会被当作姓名。</p>
          </div>

          <div class="flex items-center space-x-6">
            <div class="w-16 h-16 rounded-full bg-blue-100 dark:bg-zinc-800 flex items-center justify-center text-xl font-bold text-blue-600 dark:text-zinc-300">
              {{ avatarText }}
            </div>
            <div>
              <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ displayName }}</p>
              <p class="text-[10px] text-gray-400 mt-1">登录账号：{{ currentUser?.username || '-' }}</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 pt-2">
            <label class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">姓名 / 显示名称</span>
              <input v-model="profileForm.nickname" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">邮箱</span>
              <input v-model="profileForm.email" type="email" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">电话（选填）</span>
              <input v-model="profileForm.phone" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label v-if="isStudent" class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">学号（选填）</span>
              <input v-model="profileForm.student_id" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label v-if="isStudent" class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">年级（选填）</span>
              <input v-model="profileForm.grade" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label v-if="isStudent" class="space-y-1">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">专业（选填）</span>
              <input v-model="profileForm.major" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label v-if="isStudent" class="space-y-1 col-span-2">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">研究方向（选填）</span>
              <input v-model="profileForm.research_direction" type="text" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label v-if="isStudent" class="space-y-1 col-span-2">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">个人简介（选填）</span>
              <textarea v-model="profileForm.bio" rows="3" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500 resize-none"></textarea>
            </label>
          </div>

          <div class="pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-end">
            <button
              @click="handleSaveProfile"
              :disabled="savingProfile"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded text-xs shadow-sm transition-all disabled:opacity-50"
            >
              {{ savingProfile ? '保存中' : '保存更改' }}
            </button>
          </div>
        </div>

        <div v-if="activeTab === 'security'" class="space-y-6">
          <h3 class="text-sm font-semibold border-b border-gray-100 dark:border-zinc-800 pb-3">修改密码</h3>

          <div class="space-y-4 max-w-md">
            <label class="space-y-1 block">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">旧密码</span>
              <input v-model="oldPassword" type="password" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label class="space-y-1 block">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">新密码</span>
              <input v-model="newPassword" type="password" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>

            <label class="space-y-1 block">
              <span class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">确认新密码</span>
              <input v-model="confirmPassword" type="password" class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500" />
            </label>
          </div>

          <div class="pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-end">
            <button
              @click="handleChangePassword"
              :disabled="savingPassword"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded text-xs shadow-sm transition-all disabled:opacity-50"
            >
              {{ savingPassword ? '更新中' : '更新密码' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
