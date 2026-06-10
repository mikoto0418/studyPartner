<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Check, Search, Trash2, UserPlus, Users, X } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { getUserDisplayName, userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'

const props = withDefaults(defineProps<{
  visible: boolean
  modelValue: string[]
  title?: string
}>(), {
  title: '选择学生'
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'update:modelValue': [value: string[]]
  confirm: [users: UserOut[]]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value)
})

const loading = ref(false)
const students = ref<UserOut[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const selectedIds = ref<string[]>([])
const selectedUserMap = ref(new Map<string, UserOut>())
const keyword = ref('')
const grade = ref('')
const major = ref('')
const status = ref('active')

const selectedSet = computed(() => new Set(selectedIds.value))
const selectedUsers = computed(() => selectedIds.value.map(id => selectedUserMap.value.get(id)).filter(Boolean) as UserOut[])
const allPageSelected = computed(() => students.value.length > 0 && students.value.every(item => selectedSet.value.has(item.id)))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

const profileLine = (student: UserOut) => {
  const profile = student.student_profile
  return [profile?.grade, profile?.major, profile?.student_id ? `学号 ${profile.student_id}` : '']
    .filter(Boolean)
    .join(' · ') || '暂无档案信息'
}

const syncKnownUsers = (items: UserOut[]) => {
  const nextMap = new Map(selectedUserMap.value)
  items.forEach(item => {
    if (selectedIds.value.includes(item.id)) nextMap.set(item.id, item)
  })
  selectedUserMap.value = nextMap
}

const loadStudents = async () => {
  loading.value = true
  try {
    const res = await userApi.listUsers({
      role_code: 'student',
      keyword: keyword.value.trim() || undefined,
      grade: grade.value.trim() || undefined,
      major: major.value.trim() || undefined,
      status: status.value || undefined,
      page: page.value,
      page_size: pageSize.value
    })
    students.value = res.data?.items || []
    total.value = res.data?.total || 0
    syncKnownUsers(students.value)
  } catch (error) {
    console.warn('Failed to load students', error)
    ElMessage.error('加载学生列表失败')
  } finally {
    loading.value = false
  }
}

const runSearch = () => {
  page.value = 1
  loadStudents()
}

const toggleStudent = (student: UserOut) => {
  const nextSet = new Set(selectedIds.value)
  const nextMap = new Map(selectedUserMap.value)
  if (nextSet.has(student.id)) {
    nextSet.delete(student.id)
  } else {
    nextSet.add(student.id)
    nextMap.set(student.id, student)
  }
  selectedIds.value = Array.from(nextSet)
  selectedUserMap.value = nextMap
}

const toggleCurrentPage = () => {
  const nextSet = new Set(selectedIds.value)
  const nextMap = new Map(selectedUserMap.value)
  if (allPageSelected.value) {
    students.value.forEach(item => nextSet.delete(item.id))
  } else {
    students.value.forEach(item => {
      nextSet.add(item.id)
      nextMap.set(item.id, item)
    })
  }
  selectedIds.value = Array.from(nextSet)
  selectedUserMap.value = nextMap
}

const removeSelected = (studentId: string) => {
  selectedIds.value = selectedIds.value.filter(id => id !== studentId)
}

const clearSelected = () => {
  selectedIds.value = []
}

const confirmSelection = () => {
  emit('update:modelValue', selectedIds.value)
  emit('confirm', selectedUsers.value)
  dialogVisible.value = false
}

const goPage = (nextPage: number) => {
  page.value = Math.min(Math.max(nextPage, 1), totalPages.value)
  loadStudents()
}

watch(() => props.visible, value => {
  if (!value) return
  selectedIds.value = [...props.modelValue]
  page.value = 1
  loadStudents()
})
</script>

<template>
  <el-dialog v-model="dialogVisible" :title="title" width="960px" class="student-picker-dialog">
    <div class="grid gap-4 lg:grid-cols-[1fr_280px]">
      <section class="min-w-0 rounded-lg border border-gray-100 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div class="grid gap-2 border-b border-gray-100 p-3 dark:border-zinc-800 md:grid-cols-[1fr_120px_120px_110px_auto]">
          <label class="relative block">
            <Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              v-model="keyword"
              @keyup.enter="runSearch"
              class="h-10 w-full rounded-md border border-gray-200 bg-white pl-9 pr-3 text-sm outline-none transition focus:border-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
              placeholder="姓名、账号、学号"
            />
          </label>
          <input
            v-model="grade"
            @keyup.enter="runSearch"
            class="h-10 rounded-md border border-gray-200 px-3 text-sm outline-none transition focus:border-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="年级"
          />
          <input
            v-model="major"
            @keyup.enter="runSearch"
            class="h-10 rounded-md border border-gray-200 px-3 text-sm outline-none transition focus:border-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
            placeholder="专业"
          />
          <select
            v-model="status"
            class="h-10 rounded-md border border-gray-200 bg-white px-3 text-sm outline-none transition focus:border-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
          >
            <option value="">全部状态</option>
            <option value="active">启用</option>
            <option value="inactive">停用</option>
            <option value="disabled">禁用</option>
          </select>
          <button
            type="button"
            @click="runSearch"
            class="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-gray-900 px-4 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-950"
          >
            <Search class="h-4 w-4" />
            搜索
          </button>
        </div>

        <div class="flex items-center justify-between border-b border-gray-100 px-3 py-2 text-xs text-gray-500 dark:border-zinc-800">
          <span>共 {{ total }} 名学生</span>
          <button type="button" @click="toggleCurrentPage" class="inline-flex items-center gap-1 rounded px-2 py-1 hover:bg-gray-100 dark:hover:bg-zinc-800">
            <UserPlus class="h-3.5 w-3.5" />
            {{ allPageSelected ? '取消本页' : '选中本页' }}
          </button>
        </div>

        <div v-loading="loading" class="max-h-[420px] overflow-y-auto">
          <button
            v-for="student in students"
            :key="student.id"
            type="button"
            @click="toggleStudent(student)"
            class="grid w-full grid-cols-[32px_1fr_auto] items-center gap-3 border-b border-gray-50 px-3 py-3 text-left transition last:border-b-0 hover:bg-gray-50 dark:border-zinc-900 dark:hover:bg-zinc-900"
          >
            <span
              class="flex h-5 w-5 items-center justify-center rounded border"
              :class="selectedSet.has(student.id) ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-300 text-transparent dark:border-zinc-700'"
            >
              <Check class="h-3.5 w-3.5" />
            </span>
            <span class="min-w-0">
              <span class="block truncate text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ getUserDisplayName(student) }}</span>
              <span class="mt-0.5 block truncate text-xs text-gray-500">{{ student.username }} · {{ profileLine(student) }}</span>
            </span>
            <span class="rounded bg-gray-100 px-2 py-1 text-[10px] text-gray-500 dark:bg-zinc-800">
              {{ student.status === 'active' ? '启用' : student.status }}
            </span>
          </button>

          <div v-if="students.length === 0 && !loading" class="py-14 text-center text-sm text-gray-400">
            未找到匹配学生
          </div>
        </div>

        <div class="flex items-center justify-between border-t border-gray-100 px-3 py-3 text-xs dark:border-zinc-800">
          <button type="button" @click="goPage(page - 1)" :disabled="page <= 1" class="rounded border border-gray-200 px-3 py-1.5 disabled:opacity-40 dark:border-zinc-700">
            上一页
          </button>
          <span class="text-gray-500">第 {{ page }} / {{ totalPages }} 页</span>
          <button type="button" @click="goPage(page + 1)" :disabled="page >= totalPages" class="rounded border border-gray-200 px-3 py-1.5 disabled:opacity-40 dark:border-zinc-700">
            下一页
          </button>
        </div>
      </section>

      <aside class="rounded-lg border border-gray-100 bg-gray-50/80 p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-zinc-50">
            <Users class="h-4 w-4 text-blue-600" />
            已选 {{ selectedIds.length }}
          </div>
          <button type="button" @click="clearSelected" class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-500 hover:bg-white dark:hover:bg-zinc-800">
            <Trash2 class="h-3.5 w-3.5" />
            清空
          </button>
        </div>

        <div class="mt-3 max-h-[468px] space-y-2 overflow-y-auto pr-1">
          <div
            v-for="student in selectedUsers"
            :key="student.id"
            class="flex items-center justify-between gap-2 rounded-md border border-gray-100 bg-white px-3 py-2 dark:border-zinc-800 dark:bg-zinc-950"
          >
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-gray-900 dark:text-zinc-50">{{ getUserDisplayName(student) }}</p>
              <p class="truncate text-xs text-gray-400">{{ student.username }}</p>
            </div>
            <button type="button" @click="removeSelected(student.id)" class="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-red-500 dark:hover:bg-zinc-800">
              <X class="h-4 w-4" />
            </button>
          </div>

          <div v-if="selectedUsers.length === 0" class="rounded-md border border-dashed border-gray-200 py-10 text-center text-xs text-gray-400 dark:border-zinc-700">
            暂未选择学生
          </div>
        </div>
      </aside>
    </div>

    <template #footer>
      <div class="flex items-center justify-end gap-2">
        <button type="button" @click="dialogVisible = false" class="rounded-md border border-gray-200 px-4 py-2 text-sm dark:border-zinc-700">
          取消
        </button>
        <button type="button" @click="confirmSelection" class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white">
          确认选择
        </button>
      </div>
    </template>
  </el-dialog>
</template>
