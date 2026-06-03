<script setup lang="ts">
import { ref } from 'vue'


const username = ref(localStorage.getItem('sp_username') || '张三')
const email = ref('zhangsan@example.com')
const phone = ref('13800000000')

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')

const activeTab = ref('profile')
const saveSuccess = ref(false)

const handleSaveProfile = () => {
  saveSuccess.value = true
  setTimeout(() => {
    saveSuccess.value = false
  }, 2000)
}
</script>

<template>
  <div class="max-w-4xl mx-auto py-6 space-y-6">
    <div class="flex gap-8">
      
      <!-- Left sidebar items -->
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

      <!-- Right main settings -->
      <div class="flex-1 minimal-card p-8">
        
        <div v-if="saveSuccess" class="mb-4 p-2.5 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/50 text-emerald-600 dark:text-emerald-400 text-xs rounded">
          设置保存成功！
        </div>

        <!-- Tab 1: Profile -->
        <div v-if="activeTab === 'profile'" class="space-y-6">
          <h3 class="text-sm font-semibold border-b border-gray-100 dark:border-zinc-800 pb-3">基本信息</h3>
          
          <div class="flex items-center space-x-6">
            <div class="w-16 h-16 rounded-full bg-blue-100 dark:bg-zinc-800 flex items-center justify-center text-xl font-bold text-blue-600 dark:text-zinc-300">
              {{ username.charAt(0) }}
            </div>
            <div>
              <button class="text-xs text-blue-600 dark:text-blue-500 font-semibold hover:underline">上传新头像</button>
              <p class="text-[10px] text-gray-400 mt-1">支持 JPG、PNG 格式，大小不超过 2MB</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4 pt-2">
            <div class="space-y-1">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">姓名</label>
              <input
                v-model="username"
                type="text"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">邮箱</label>
              <input
                v-model="email"
                type="email"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1 col-span-2">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">电话</label>
              <input
                v-model="phone"
                type="text"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div class="pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-end">
            <button
              @click="handleSaveProfile"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded text-xs shadow-sm transition-all"
            >
              保存更改
            </button>
          </div>
        </div>

        <!-- Tab 2: Security -->
        <div v-if="activeTab === 'security'" class="space-y-6">
          <h3 class="text-sm font-semibold border-b border-gray-100 dark:border-zinc-800 pb-3">修改密码</h3>
          
          <div class="space-y-4 max-w-md">
            <div class="space-y-1">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">旧密码</label>
              <input
                v-model="oldPassword"
                type="password"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">新密码</label>
              <input
                v-model="newPassword"
                type="password"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>

            <div class="space-y-1">
              <label class="text-xs text-gray-500 dark:text-zinc-400 block font-medium">确认新密码</label>
              <input
                v-model="confirmPassword"
                type="password"
                class="w-full px-3 py-2 bg-gray-50 dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded text-xs text-gray-900 dark:text-zinc-50 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div class="pt-4 border-t border-gray-100 dark:border-zinc-800 flex justify-end">
            <button
              @click="handleSaveProfile"
              class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded text-xs shadow-sm transition-all"
            >
              更新密码
            </button>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>
