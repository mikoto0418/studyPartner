<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, Plus, Edit, Trash2, Shield } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'

// States
const users = ref<UserOut[]>([])
const totalUsers = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const loading = ref(false)

// Filters
const searchKeyword = ref('')
const selectedRole = ref('')
const selectedStatus = ref('')

// Dialogs
const userDialogVisible = ref(false)
const dialogType = ref<'create' | 'edit'>('create')
const editUserId = ref<string | null>(null)

const userForm = ref({
  username: '',
  password: '',
  nickname: '',
  email: '',
  phone: '',
  role_codes: ['student'] as string[],
  status: 'active',
  // Student Profile Extensions
  student_id: '',
  grade: '',
  major: '',
  research_direction: ''
})

// Load Users from API
const loadUsers = async () => {
  loading.value = true
  try {
    const res = await userApi.listUsers({
      role_code: selectedRole.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value
    })
    
    // Client-side simple search filter for keyword and status if needed (or backend query)
    let fetched = res.data?.items || []
    let totalCount = res.data?.total || 0

    if (searchKeyword.value.trim()) {
      const kw = searchKeyword.value.toLowerCase()
      fetched = fetched.filter((u: UserOut) => 
        u.username.toLowerCase().includes(kw) || 
        (u.nickname && u.nickname.toLowerCase().includes(kw)) ||
        u.email.toLowerCase().includes(kw)
      )
      totalCount = fetched.length
    }

    if (selectedStatus.value) {
      fetched = fetched.filter((u: UserOut) => u.status === selectedStatus.value)
      totalCount = fetched.length
    }

    users.value = fetched
    totalUsers.value = totalCount
  } catch (error) {
    console.error("Failed to load users list", error)
    ElMessage.error("获取用户列表失败")
  } finally {
    loading.value = false
  }
}

// Show Create Modal
const showCreateModal = () => {
  dialogType.value = 'create'
  editUserId.value = null
  userForm.value = {
    username: '',
    password: '',
    nickname: '',
    email: '',
    phone: '',
    role_codes: ['student'],
    status: 'active',
    student_id: '',
    grade: '2026级',
    major: '计算机科学与技术',
    research_direction: ''
  }
  userDialogVisible.value = true
}

// Show Edit Modal
const showEditModal = (row: UserOut) => {
  dialogType.value = 'edit'
  editUserId.value = row.id
  
  userForm.value = {
    username: row.username,
    password: '', // blank for security
    nickname: row.nickname || '',
    email: row.email,
    phone: row.phone || '',
    role_codes: row.roles.map(r => r.code),
    status: row.status,
    // Extract Student Profile if available
    student_id: row.student_profile?.student_id || '',
    grade: row.student_profile?.grade || '',
    major: row.student_profile?.major || '',
    research_direction: row.student_profile?.research_direction || ''
  }
  userDialogVisible.value = true
}

// Submit Create/Edit
const handleUserSubmit = async () => {
  // Validate
  if (!userForm.value.username.trim()) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (dialogType.value === 'create' && !userForm.value.password) {
    ElMessage.warning('请输入初始密码')
    return
  }
  if (!userForm.value.email.trim()) {
    ElMessage.warning('请输入电子邮箱')
    return
  }

  try {
    if (dialogType.value === 'create') {
      // Create user
      const createPayload = {
        username: userForm.value.username.trim(),
        password: userForm.value.password,
        nickname: userForm.value.nickname.trim() || undefined,
        email: userForm.value.email.trim(),
        phone: userForm.value.phone.trim() || undefined,
        role_codes: userForm.value.role_codes,
        status: userForm.value.status
      }
      
      const res = await userApi.createUser(createPayload)
      const createdUser = res.data

      // If role contains student, create/update their profile extensions
      if (userForm.value.role_codes.includes('student') && createdUser) {
        await userApi.updateStudentProfile(createdUser.id, {
          student_id: userForm.value.student_id.trim() || undefined,
          grade: userForm.value.grade.trim() || undefined,
          major: userForm.value.major.trim() || undefined,
          research_direction: userForm.value.research_direction.trim() || undefined
        })
      }
      ElMessage.success('创建用户成功')
    } else {
      // Edit User
      if (!editUserId.value) return
      
      const editPayload: any = {
        nickname: userForm.value.nickname.trim() || undefined,
        email: userForm.value.email.trim(),
        phone: userForm.value.phone.trim() || undefined,
        status: userForm.value.status
      }
      if (userForm.value.password) {
        editPayload.password = userForm.value.password
      }

      await userApi.updateUser(editUserId.value, editPayload)

      // Update student profile extensions if student role
      if (userForm.value.role_codes.includes('student')) {
        await userApi.updateStudentProfile(editUserId.value, {
          student_id: userForm.value.student_id.trim() || undefined,
          grade: userForm.value.grade.trim() || undefined,
          major: userForm.value.major.trim() || undefined,
          research_direction: userForm.value.research_direction.trim() || undefined
        })
      }
      ElMessage.success('更新用户信息成功')
    }
    
    userDialogVisible.value = false
    loadUsers()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.message || '操作失败')
  }
}

// Toggle Account Status (active / disabled)
const toggleUserStatus = async (row: UserOut) => {
  const nextStatus = row.status === 'active' ? 'disabled' : 'active'
  try {
    await userApi.updateUser(row.id, { status: nextStatus })
    ElMessage.success(nextStatus === 'active' ? '账号已成功启用' : '账号已成功禁用')
    loadUsers()
  } catch (e) {
    ElMessage.error('切换状态失败')
  }
}

// Delete User
const handleDeleteUser = (row: UserOut) => {
  ElMessageBox.confirm(
    `确定删除系统账号「${row.username}」吗？此操作不可逆。`,
    '高危警示',
    {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'error',
    }
  ).then(async () => {
    try {
      await userApi.deleteUser(row.id)
      ElMessage.success('删除用户成功')
      loadUsers()
    } catch (e) {
      ElMessage.error('删除用户失败')
    }
  }).catch(() => {})
}

onMounted(() => {
  loadUsers()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Filter bar -->
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
      <div class="flex flex-wrap items-center gap-3">
        <!-- Search Keyword -->
        <div class="relative w-60">
          <Search class="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
          <input
            v-model="searchKeyword"
            @keyup.enter="loadUsers"
            type="text"
            placeholder="搜索用户名/邮箱/昵称..."
            class="w-full pl-9 pr-4 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg text-xs focus:outline-none focus:border-blue-500"
          />
        </div>

        <!-- Role Filter -->
        <select
          v-model="selectedRole"
          @change="loadUsers"
          class="px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg text-xs focus:outline-none text-gray-600 dark:text-zinc-300"
        >
          <option value="">全部系统角色</option>
          <option value="admin">系统管理员</option>
          <option value="teacher">指导教师</option>
          <option value="student">平台学生</option>
        </select>

        <!-- Status Filter -->
        <select
          v-model="selectedStatus"
          @change="loadUsers"
          class="px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 rounded-lg text-xs focus:outline-none text-gray-600 dark:text-zinc-300"
        >
          <option value="">全部账号状态</option>
          <option value="active">正常启用</option>
          <option value="disabled">禁用封禁</option>
        </select>

        <!-- Refresh -->
        <button
          @click="loadUsers"
          class="p-2 border border-gray-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900 hover:bg-gray-50 text-gray-500"
        >
          <RefreshCw class="w-3.5 h-3.5" />
        </button>
      </div>

      <!-- Add Account Button -->
      <button
        @click="showCreateModal"
        class="flex items-center space-x-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-sm focus:outline-none"
      >
        <Plus class="w-4 h-4" />
        <span>新建系统用户</span>
      </button>
    </div>

    <!-- Table content -->
    <div class="minimal-card overflow-hidden bg-white dark:bg-zinc-900" v-loading="loading">
      <el-table :data="users" style="width: 100%" class="minimalist-table text-xs">
        <el-table-column prop="username" label="用户名" width="120" />
        <el-table-column prop="nickname" label="昵称" width="120">
          <template #default="{ row }">
            <span>{{ row.nickname || '未设定' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="电子邮箱" width="180" />
        
        <!-- Role tags -->
        <el-table-column label="关联角色" width="130">
          <template #default="{ row }">
            <div class="flex flex-wrap gap-1">
              <span
                v-for="r in row.roles"
                :key="r.id"
                class="text-[9px] px-1.5 py-0.5 rounded font-bold capitalize"
                :class="
                  r.code === 'admin' ? 'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400' :
                  r.code === 'teacher' ? 'bg-purple-50 text-purple-600 dark:bg-purple-950/20 dark:text-purple-400' :
                  'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400'
                "
              >
                {{ r.name }}
              </span>
            </div>
          </template>
        </el-table-column>

        <!-- Student ID & Major details -->
        <el-table-column label="学情关联档案">
          <template #default="{ row }">
            <div v-if="row.student_profile" class="text-[10px] text-gray-400">
              <span class="font-mono">{{ row.student_profile.student_id || 'SPXXXX' }}</span>
              <span> &bull; </span>
              <span>{{ row.student_profile.grade }} &bull; {{ row.student_profile.major }}</span>
            </div>
            <div v-else class="text-[10px] text-gray-300 dark:text-zinc-700">
              非学生角色或无档案
            </div>
          </template>
        </el-table-column>

        <!-- Status -->
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <span
              class="inline-flex items-center px-2 py-0.5 rounded-full text-[9px] font-bold"
              :class="
                row.status === 'active'
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-400'
                  : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400'
              "
            >
              {{ row.status === 'active' ? '正常启用' : '禁用封禁' }}
            </span>
          </template>
        </el-table-column>

        <!-- Last Login -->
        <el-table-column label="最后登录" width="160">
          <template #default="{ row }">
            <span class="text-[10px] text-gray-400 font-mono">
              {{ row.last_login_at ? new Date(row.last_login_at).toLocaleString() : '从未来访' }}
            </span>
          </template>
        </el-table-column>

        <!-- Actions -->
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="flex items-center space-x-2">
              <button
                @click="showEditModal(row)"
                class="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                title="编辑用户信息"
              >
                <Edit class="w-3.5 h-3.5" />
              </button>
              <button
                @click="toggleUserStatus(row)"
                class="p-1 transition-colors"
                :class="row.status === 'active' ? 'text-gray-400 hover:text-amber-600' : 'text-gray-400 hover:text-emerald-600'"
                :title="row.status === 'active' ? '禁用账号' : '启用账号'"
              >
                <Shield class="w-3.5 h-3.5" />
              </button>
              <button
                @click="handleDeleteUser(row)"
                class="p-1 text-gray-400 hover:text-red-500 transition-colors"
                title="彻底删除用户"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <!-- Pagination -->
      <div class="px-6 py-4 border-t border-gray-100 dark:border-zinc-800 flex justify-between items-center bg-gray-50/50 dark:bg-zinc-900/30">
        <span class="text-[10px] text-gray-400">共计 {{ totalUsers }} 个系统账号</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="totalUsers"
          layout="prev, pager, next"
          @current-change="loadUsers"
          size="small"
        />
      </div>
    </div>

    <!-- Create/Edit User Dialog -->
    <el-dialog
      v-model="userDialogVisible"
      :title="dialogType === 'create' ? '新建系统用户' : '编辑系统用户'"
      width="480px"
      class="minimalist-dialog"
    >
      <div class="space-y-4 text-xs">
        <!-- Username (Disabled on Edit) -->
        <div class="space-y-1">
          <label class="text-gray-500 font-medium">登录用户名 <span class="text-red-500">*</span></label>
          <input
            v-model="userForm.username"
            type="text"
            placeholder="仅限字母、数字、下划线"
            :disabled="dialogType === 'edit'"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500 disabled:opacity-50"
          />
        </div>

        <!-- Password -->
        <div class="space-y-1">
          <label class="text-gray-500 font-medium">
            {{ dialogType === 'create' ? '登录初始密码' : '重置登录密码（留空表示不修改）' }}
            <span v-if="dialogType === 'create'" class="text-red-500">*</span>
          </label>
          <input
            v-model="userForm.password"
            type="password"
            placeholder="输入密码"
            class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
          />
        </div>

        <div class="grid grid-cols-2 gap-4">
          <!-- Nickname -->
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">用户姓名 / 昵称</label>
            <input
              v-model="userForm.nickname"
              type="text"
              placeholder="显示姓名"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
            />
          </div>
          <!-- Email -->
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">电子邮箱 <span class="text-red-500">*</span></label>
            <input
              v-model="userForm.email"
              type="email"
              placeholder="user@example.com"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <!-- Phone and Roles -->
        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">手机号码（选填）</label>
            <input
              v-model="userForm.phone"
              type="text"
              placeholder="手机号"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500"
            />
          </div>
          <div class="space-y-1">
            <label class="text-gray-500 font-medium">系统角色权限</label>
            <select
              v-model="userForm.role_codes[0]"
              :disabled="dialogType === 'edit'"
              class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded focus:outline-none focus:border-blue-500 bg-white"
            >
              <option value="student">学生 (student)</option>
              <option value="teacher">指导教师 (teacher)</option>
              <option value="admin">系统管理员 (admin)</option>
            </select>
          </div>
        </div>

        <!-- Conditionally Display Student Profile Extensions -->
        <div
          v-if="userForm.role_codes.includes('student')"
          class="p-4 rounded-lg bg-blue-50/20 border border-blue-100/30 dark:bg-blue-950/5 dark:border-blue-900/20 space-y-3"
        >
          <span class="text-[10px] text-blue-600 dark:text-blue-400 font-bold block">学生档案附加字段</span>
          
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1">
              <label class="text-gray-400 text-[10px] font-medium">学号</label>
              <input
                v-model="userForm.student_id"
                type="text"
                placeholder="SP2026xxxx"
                class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-[11px] focus:outline-none focus:border-blue-500"
              />
            </div>
            <div class="space-y-1">
              <label class="text-gray-400 text-[10px] font-medium">所属年级</label>
              <input
                v-model="userForm.grade"
                type="text"
                placeholder="2026级"
                class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-[11px] focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-1">
              <label class="text-gray-400 text-[10px] font-medium">所学专业</label>
              <input
                v-model="userForm.major"
                type="text"
                class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-[11px] focus:outline-none focus:border-blue-500"
              />
            </div>
            <div class="space-y-1">
              <label class="text-gray-400 text-[10px] font-medium">学术研究方向</label>
              <input
                v-model="userForm.research_direction"
                type="text"
                placeholder="例如: 大模型微调"
                class="w-full px-3 py-2 border border-gray-200 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 rounded text-[11px] focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-2 pt-2">
          <button @click="userDialogVisible = false" class="px-3 py-1.5 border border-gray-200 rounded text-xs text-gray-500 hover:bg-gray-50">取消</button>
          <button @click="handleUserSubmit" class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium">保存提交</button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>
