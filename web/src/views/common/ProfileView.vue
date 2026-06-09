<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Save, ShieldCheck, UserRound } from 'lucide-vue-next'
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
const roleText = computed(() => currentUser.value?.roles.map((role) => role.name).join(' / ') || '未同步角色')

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
  <div class="mx-auto max-w-6xl space-y-5" v-loading="loading">
    <section class="surface-panel p-5">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div class="flex items-center gap-4">
          <div class="flex h-16 w-16 items-center justify-center rounded-lg bg-blue-50 text-2xl font-bold text-blue-600 ring-1 ring-blue-100 dark:bg-blue-950/20 dark:text-blue-300 dark:ring-blue-900/60">
            {{ avatarText }}
          </div>
          <div>
            <p class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ displayName }}</p>
            <p class="mt-1 text-xs text-gray-400 dark:text-zinc-500">登录账号：{{ currentUser?.username || '-' }}</p>
          </div>
        </div>
        <div class="inline-flex w-fit items-center gap-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-semibold text-gray-600 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300">
          <UserRound class="h-3.5 w-3.5 text-blue-600 dark:text-blue-400" />
          {{ roleText }}
        </div>
      </div>
    </section>

    <div class="grid gap-5 lg:grid-cols-[220px_1fr]">
      <aside class="surface-panel h-fit p-2">
        <button
          @click="activeTab = 'profile'"
          class="segmented-button w-full"
          :class="activeTab === 'profile' ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100'"
        >
          <UserRound class="h-4 w-4" />
          <span>个人信息</span>
        </button>
        <button
          @click="activeTab = 'security'"
          class="segmented-button mt-1 w-full"
          :class="activeTab === 'security' ? 'bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300' : 'text-gray-500 hover:bg-gray-50 hover:text-gray-900 dark:text-zinc-400 dark:hover:bg-zinc-800/60 dark:hover:text-zinc-100'"
        >
          <ShieldCheck class="h-4 w-4" />
          <span>安全设置</span>
        </button>
      </aside>

      <section class="surface-panel p-6">
        <form v-if="activeTab === 'profile'" class="space-y-8" @submit.prevent="handleSaveProfile">
          <div class="grid gap-6 md:grid-cols-[220px_1fr]">
            <div class="section-side-label">
              <h3>基本信息</h3>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <label class="space-y-1">
                <span class="ui-field-label">姓名 / 显示名称</span>
                <input v-model="profileForm.nickname" type="text" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">邮箱</span>
                <input v-model="profileForm.email" type="email" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">电话（选填）</span>
                <input v-model="profileForm.phone" type="text" class="ui-field" />
              </label>
            </div>
          </div>

          <div v-if="isStudent" class="grid gap-6 border-t border-gray-100 pt-8 md:grid-cols-[220px_1fr] dark:border-zinc-800">
            <div class="section-side-label">
              <h3>学生档案</h3>
            </div>
            <div class="grid gap-4 sm:grid-cols-2">
              <label class="space-y-1">
                <span class="ui-field-label">学号（选填）</span>
                <input v-model="profileForm.student_id" type="text" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">年级（选填）</span>
                <input v-model="profileForm.grade" type="text" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">专业（选填）</span>
                <input v-model="profileForm.major" type="text" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">研究方向（选填）</span>
                <input v-model="profileForm.research_direction" type="text" class="ui-field" />
              </label>
              <label class="space-y-1 sm:col-span-2">
                <span class="ui-field-label">个人简介（选填）</span>
                <textarea v-model="profileForm.bio" rows="4" class="ui-field resize-none"></textarea>
              </label>
            </div>
          </div>

          <div class="flex justify-end border-t border-gray-100 pt-5 dark:border-zinc-800">
            <button type="submit" :disabled="savingProfile" class="ui-button-primary">
              <Save class="h-3.5 w-3.5" />
              <span>{{ savingProfile ? '保存中' : '保存更改' }}</span>
            </button>
          </div>
        </form>

        <form v-if="activeTab === 'security'" class="space-y-8" @submit.prevent="handleChangePassword">
          <div class="grid gap-6 md:grid-cols-[220px_1fr]">
            <div class="section-side-label">
              <h3>修改密码</h3>
            </div>
            <div class="grid max-w-lg gap-4">
              <label class="space-y-1">
                <span class="ui-field-label">旧密码</span>
                <input v-model="oldPassword" type="password" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">新密码</span>
                <input v-model="newPassword" type="password" class="ui-field" />
              </label>
              <label class="space-y-1">
                <span class="ui-field-label">确认新密码</span>
                <input v-model="confirmPassword" type="password" class="ui-field" />
              </label>
            </div>
          </div>

          <div class="flex justify-end border-t border-gray-100 pt-5 dark:border-zinc-800">
            <button type="submit" :disabled="savingPassword" class="ui-button-primary">
              <ShieldCheck class="h-3.5 w-3.5" />
              <span>{{ savingPassword ? '更新中' : '更新密码' }}</span>
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>
