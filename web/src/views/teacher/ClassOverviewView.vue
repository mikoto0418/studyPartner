<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Activity, BarChart3, Brain, LineChart, Plus, RefreshCw, Users } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { learningPathApi } from '../../api/modules/learning_path'
import type { ClassOut, ClassOverviewOut } from '../../api/modules/learning_path'
import { userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'

const classes = ref<ClassOut[]>([])
const students = ref<UserOut[]>([])
const selectedClassId = ref('')
const overview = ref<ClassOverviewOut | null>(null)
const loading = ref(false)
const createDialogVisible = ref(false)

const classForm = ref({
  name: '',
  description: '',
  grade: '',
  subject: '',
  student_ids: [] as string[]
})

const maxTrendProgress = computed(() => Math.max(...(overview.value?.trend.map(item => Number(item.avg_progress || 0)) || [1]), 1))
const displayNameOf = (student: UserOut) => student.display_name || student.nickname?.trim() || '未设置姓名'
const optionLabelOf = (student: UserOut) => `${displayNameOf(student)}（账号：${student.username}）`

const loadData = async () => {
  loading.value = true
  try {
    const [classRes, studentRes] = await Promise.all([
      learningPathApi.listClasses(),
      userApi.listUsers({ role_code: 'student', page_size: 100 })
    ])
    classes.value = classRes.data || []
    students.value = studentRes.data?.items || []
    if (!selectedClassId.value && classes.value.length > 0) {
      selectedClassId.value = classes.value[0].id
    }
    if (selectedClassId.value) await loadOverview(selectedClassId.value)
  } catch (error) {
    console.warn('Failed to load class overview data', error)
  } finally {
    loading.value = false
  }
}

const loadOverview = async (classId: string) => {
  selectedClassId.value = classId
  overview.value = null
  try {
    const res = await learningPathApi.getClassOverview(classId)
    overview.value = res.data
  } catch (error) {
    ElMessage.error('获取班级概况失败')
  }
}

const createClass = async () => {
  if (!classForm.value.name.trim()) {
    ElMessage.warning('请输入班级名称')
    return
  }
  try {
    const res = await learningPathApi.createClass(classForm.value)
    classes.value.unshift(res.data)
    selectedClassId.value = res.data.id
    createDialogVisible.value = false
    classForm.value = { name: '', description: '', grade: '', subject: '', student_ids: [] }
    await loadOverview(res.data.id)
    ElMessage.success('班级已创建')
  } catch (error) {
    ElMessage.error('创建班级失败')
  }
}

const metricCards = computed(() => {
  const metrics = overview.value?.metrics || {}
  return [
    { label: '班级人数', value: metrics.student_count || 0, unit: '人', icon: Users, tone: 'blue' },
    { label: '平均路径进度', value: metrics.avg_progress || 0, unit: '%', icon: Activity, tone: 'emerald' },
    { label: '活跃路径分配', value: metrics.active_paths || 0, unit: '条', icon: LineChart, tone: 'amber' },
    { label: 'Memory 条目', value: metrics.memory_count || 0, unit: '条', icon: Brain, tone: 'indigo' }
  ]
})

onMounted(loadData)
</script>

<template>
  <div class="h-[calc(100vh-8rem)] flex gap-6 -m-4 p-4 overflow-hidden">
    <aside class="w-80 minimal-card bg-white dark:bg-zinc-900 p-5 flex flex-col">
      <div class="flex items-center justify-between pb-4 border-b border-gray-100 dark:border-zinc-800">
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">班级 Memory 看板</h3>
          <p class="mt-1 text-[10px] text-gray-400">以班级为单位查看学情概况</p>
        </div>
        <button
          @click="createDialogVisible = true"
          title="创建班级"
          class="p-2 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
        >
          <Plus class="w-4 h-4" />
        </button>
      </div>

      <div class="flex-1 overflow-y-auto mt-4 space-y-2" v-loading="loading">
        <button
          v-for="item in classes"
          :key="item.id"
          @click="loadOverview(item.id)"
          class="w-full p-3 text-left rounded-lg border transition-all"
          :class="selectedClassId === item.id
            ? 'border-blue-200 bg-blue-50/70 text-blue-800 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-300'
            : 'border-gray-100 bg-white hover:bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60'"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="text-xs font-semibold truncate">{{ item.name }}</span>
            <span class="text-[9px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-zinc-800 text-gray-500">{{ item.member_count }} 人</span>
          </div>
          <p class="mt-1 text-[10px] text-gray-400 line-clamp-2">{{ item.description || item.subject || '暂无班级描述' }}</p>
        </button>

        <div v-if="classes.length === 0 && !loading" class="py-12 text-center text-xs text-gray-400">
          暂无班级，请先创建。
        </div>
      </div>
    </aside>

    <section class="flex-1 overflow-y-auto pr-2">
      <div v-if="overview" class="space-y-6">
        <div class="minimal-card bg-white dark:bg-zinc-900 p-6">
          <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div>
              <div class="flex items-center gap-2">
                <Users class="w-5 h-5 text-blue-600" />
                <h2 class="text-lg font-bold text-gray-900 dark:text-zinc-50">{{ overview.class_info.name }}</h2>
              </div>
              <p class="mt-2 text-xs text-gray-500 dark:text-zinc-400 leading-relaxed">{{ overview.class_info.description || '这个班级还没有补充说明。' }}</p>
              <div class="mt-3 flex flex-wrap gap-2 text-[10px] text-gray-500">
                <span class="px-2 py-1 rounded bg-gray-100 dark:bg-zinc-800">{{ overview.class_info.grade || '未设年级' }}</span>
                <span class="px-2 py-1 rounded bg-gray-100 dark:bg-zinc-800">{{ overview.class_info.subject || '未设学科' }}</span>
              </div>
            </div>
            <button
              @click="selectedClassId && loadOverview(selectedClassId)"
              class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs text-gray-500"
            >
              <RefreshCw class="w-3.5 h-3.5" />
              <span>刷新</span>
            </button>
          </div>
        </div>

        <div class="grid grid-cols-2 xl:grid-cols-4 gap-6">
          <div
            v-for="card in metricCards"
            :key="card.label"
            class="minimal-card bg-white dark:bg-zinc-900 p-5 flex items-center justify-between"
          >
            <div>
              <span class="text-[10px] text-gray-400 font-medium">{{ card.label }}</span>
              <div class="mt-1 text-2xl font-bold text-gray-900 dark:text-zinc-50">
                {{ card.value }}<span class="ml-1 text-xs text-gray-400">{{ card.unit }}</span>
              </div>
            </div>
            <div class="w-10 h-10 rounded border border-gray-100 dark:border-zinc-800 bg-gray-50 dark:bg-zinc-950 flex items-center justify-center text-blue-600">
              <component :is="card.icon" class="w-4 h-4" />
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div class="xl:col-span-8 minimal-card bg-white dark:bg-zinc-900 p-6">
            <div class="flex items-center justify-between mb-5">
              <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
                <BarChart3 class="w-4 h-4 text-blue-600" />
                <span>近 7 天班级趋势</span>
              </h3>
              <span class="text-[10px] text-gray-400">基于路径进度、活跃学生和 Memory 累积</span>
            </div>
            <div class="h-72 flex items-end gap-3 border-b border-l border-gray-100 dark:border-zinc-800 p-4">
              <div
                v-for="item in overview.trend"
                :key="item.date"
                class="flex-1 flex flex-col items-center justify-end gap-2 h-full"
              >
                <div class="w-full max-w-10 rounded-t bg-blue-500/80" :style="{ height: `${Math.max(8, Number(item.avg_progress || 0) / maxTrendProgress * 210)}px` }"></div>
                <span class="text-[9px] text-gray-400">{{ String(item.date).slice(5) }}</span>
              </div>
            </div>
          </div>

          <div class="xl:col-span-4 minimal-card bg-white dark:bg-zinc-900 p-6">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center gap-2">
              <Brain class="w-4 h-4 text-indigo-500" />
              <span>Memory 聚合</span>
            </h3>
            <p class="mt-3 text-xs leading-relaxed text-gray-500 dark:text-zinc-400">{{ overview.memory_summary.summary }}</p>
            <div class="mt-5 space-y-3">
              <div
                v-for="item in overview.memory_summary.top_categories"
                :key="item.category"
                class="space-y-1"
              >
                <div class="flex justify-between text-[10px] text-gray-500">
                  <span>{{ item.category }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="h-1.5 bg-gray-100 dark:bg-zinc-800 rounded">
                  <div class="h-full bg-indigo-500 rounded" :style="{ width: `${Math.min(100, item.count * 18)}%` }"></div>
                </div>
              </div>
              <div v-if="overview.memory_summary.top_categories.length === 0" class="py-8 text-center text-xs text-gray-400">
                暂无 Memory 聚合数据。
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-12 gap-6">
          <div class="xl:col-span-5 minimal-card bg-white dark:bg-zinc-900 p-6">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 mb-4">需关注学生</h3>
            <div class="space-y-3">
              <div
                v-for="item in overview.attention_students"
                :key="item.user_id"
                class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 bg-gray-50/40 dark:bg-zinc-950/30"
              >
                <div class="flex items-center justify-between">
                  <span class="text-xs font-semibold text-gray-800 dark:text-zinc-200">{{ item.name }}</span>
                  <span class="text-[10px] text-gray-400">{{ item.progress_percent || 0 }}%</span>
                </div>
                <p class="mt-1 text-[10px] text-gray-400">{{ item.reason }}</p>
              </div>
            </div>
          </div>

          <div class="xl:col-span-7 minimal-card bg-white dark:bg-zinc-900 p-6">
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 mb-4">近期学习路径</h3>
            <div class="space-y-3">
              <div
                v-for="path in overview.recent_paths"
                :key="path.id"
                class="p-3 rounded-lg border border-gray-100 dark:border-zinc-800 flex items-center justify-between gap-4"
              >
                <div class="min-w-0">
                  <p class="text-xs font-semibold text-gray-800 dark:text-zinc-200 truncate">{{ path.title }}</p>
                  <p class="mt-1 text-[10px] text-gray-400 truncate">{{ path.goal }}</p>
                </div>
                <span class="text-[10px] px-2 py-1 rounded bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">
                  {{ path.avg_progress }}%
                </span>
              </div>
              <div v-if="overview.recent_paths.length === 0" class="py-8 text-center text-xs text-gray-400">
                暂无学习路径任务。
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="h-full minimal-card bg-white dark:bg-zinc-900 flex flex-col items-center justify-center text-center text-gray-400">
        <Users class="w-10 h-10 mb-3 text-gray-300" />
        <p class="text-sm font-semibold">暂无可查看的班级概况</p>
        <p class="mt-1 text-xs">创建班级后即可沉淀班级级 Memory 看板。</p>
      </div>
    </section>

    <el-dialog v-model="createDialogVisible" title="创建班级" width="520px">
      <div class="space-y-4">
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">班级名称</span>
          <input v-model="classForm.name" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" placeholder="例如：2026 AI 伴学实验班" />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="space-y-1">
            <span class="text-xs text-gray-500">年级</span>
            <input v-model="classForm.grade" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" />
          </label>
          <label class="space-y-1">
            <span class="text-xs text-gray-500">学科</span>
            <input v-model="classForm.subject" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs" />
          </label>
        </div>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">说明</span>
          <textarea v-model="classForm.description" rows="3" class="w-full px-3 py-2 rounded border border-gray-200 dark:border-zinc-800 bg-transparent text-xs resize-none"></textarea>
        </label>
        <label class="space-y-1 block">
          <span class="text-xs text-gray-500">班级学生</span>
          <el-select v-model="classForm.student_ids" multiple class="w-full" placeholder="选择学生">
            <el-option v-for="student in students" :key="student.id" :label="optionLabelOf(student)" :value="student.id" />
          </el-select>
        </label>
      </div>
      <template #footer>
        <button @click="createDialogVisible = false" class="px-4 py-1.5 rounded border border-gray-200 dark:border-zinc-800 text-xs mr-2">取消</button>
        <button @click="createClass" class="px-4 py-1.5 rounded bg-gray-900 text-white dark:bg-zinc-100 dark:text-zinc-900 text-xs">创建</button>
      </template>
    </el-dialog>
  </div>
</template>
