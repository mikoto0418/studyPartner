<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { BarChart3, Clock, FileText, Plus, RefreshCw, ShieldAlert, Target, TrendingUp, Users } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'
import { learningPathApi } from '../../api/modules/learning_path'
import type { ClassOut } from '../../api/modules/learning_path'
import type { UserOut } from '../../api/modules/user'
import { assessmentApi, type ClassExamAnalytics } from '../../api/modules/assessment'
import BaseChart from '../../components/common/BaseChart.vue'
import StudentPickerDialog from '../../components/common/StudentPickerDialog.vue'

const classes = ref<ClassOut[]>([])
const selectedClassId = ref('')
const analytics = ref<ClassExamAnalytics | null>(null)
const loading = ref(false)
const createDialogVisible = ref(false)
const classStudentPickerVisible = ref(false)
const selectedClassStudents = ref<UserOut[]>([])

const classForm = ref({
  name: '',
  description: '',
  grade: '',
  subject: '',
  student_ids: [] as string[]
})

const displayNameOf = (student: UserOut) => student.display_name || student.nickname?.trim() || '未设置姓名'
const selectedClassStudentNames = computed(() => selectedClassStudents.value.map(displayNameOf).join('、'))

const loadData = async () => {
  loading.value = true
  try {
    const res = await learningPathApi.listClasses()
    classes.value = res.data || []
    if (!selectedClassId.value && classes.value.length) selectedClassId.value = classes.value[0].id
    if (selectedClassId.value) await loadAnalytics(selectedClassId.value)
  } catch (error) {
    console.warn('Failed to load classes', error)
  } finally {
    loading.value = false
  }
}

const loadAnalytics = async (classId: string) => {
  selectedClassId.value = classId
  analytics.value = null
  try {
    const res = await assessmentApi.getClassExamAnalytics(classId)
    analytics.value = res.data
  } catch {
    ElMessage.error('获取班级考试概况失败')
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
    selectedClassStudents.value = []
    await loadAnalytics(res.data.id)
    ElMessage.success('班级已创建')
  } catch {
    ElMessage.error('创建班级失败')
  }
}

const handleClassStudentsConfirm = (users: UserOut[]) => {
  selectedClassStudents.value = users
}

const summary = computed(() => analytics.value?.summary)
const hasData = computed(() => (analytics.value?.summary.paper_count || 0) > 0)

const pct = (v: number | null | undefined) => (v == null ? '—' : v)

const metricCards = computed(() => {
  const s = summary.value
  if (!s) return []
  return [
    { label: '发布试卷', value: s.paper_count, unit: '份', icon: FileText, tone: 'blue' },
    { label: '平均得分率', value: pct(s.avg_score_rate), unit: s.avg_score_rate == null ? '' : '%', icon: TrendingUp, tone: 'emerald' },
    { label: '及格率', value: pct(s.pass_rate), unit: s.pass_rate == null ? '' : '%', icon: Target, tone: 'amber' },
    { label: '已交卷', value: s.finished_total, unit: `/ ${s.assigned_total}`, icon: Users, tone: 'indigo' },
    { label: '可疑作答', value: s.suspicious_attempts, unit: '人次', icon: ShieldAlert, tone: 'red' },
    { label: '待批改', value: s.pending_review_total, unit: '人次', icon: Clock, tone: 'violet' }
  ]
})

const toneClass: Record<string, string> = {
  blue: 'bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400',
  emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-400',
  amber: 'bg-amber-50 text-amber-600 dark:bg-amber-950/40 dark:text-amber-400',
  indigo: 'bg-indigo-50 text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400',
  red: 'bg-red-50 text-red-600 dark:bg-red-950/40 dark:text-red-400',
  violet: 'bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-400'
}

const paperRateOption = computed<EChartsOption>(() => {
  const rows = (analytics.value?.papers || []).filter((p) => p.avg_score_rate != null)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 45, right: 20, top: 30, bottom: 70 },
    xAxis: { type: 'category', data: rows.map((p) => p.title), axisLabel: { rotate: 30, fontSize: 10, interval: 0 } },
    yAxis: { type: 'value', name: '平均得分率 %', max: 100 },
    series: [
      {
        type: 'bar',
        data: rows.map((p) => p.avg_score_rate),
        barWidth: '45%',
        itemStyle: { color: '#3b82f6', borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', fontSize: 10 }
      }
    ]
  }
})

const studentRateOption = computed<EChartsOption>(() => {
  const rows = (analytics.value?.students || []).filter((s) => s.avg_score_rate != null)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 45, right: 20, top: 30, bottom: 70 },
    xAxis: { type: 'category', data: rows.map((s) => s.name), axisLabel: { rotate: 30, fontSize: 10, interval: 0 } },
    yAxis: { type: 'value', name: '平均得分率 %', max: 100 },
    series: [
      {
        type: 'bar',
        data: rows.map((s) => s.avg_score_rate),
        barWidth: '45%',
        // 低于 60% 标红，一眼看出需要关注的学生
        itemStyle: { color: (p: any) => (p.value < 60 ? '#ef4444' : '#10b981'), borderRadius: [4, 4, 0, 0] },
        label: { show: true, position: 'top', fontSize: 10 }
      }
    ]
  }
})

onMounted(loadData)
</script>

<template>
  <div class="-m-4 flex min-h-[calc(100vh-8rem)] gap-6 bg-gray-50 p-4 dark:bg-zinc-950 md:-m-8 md:p-8">
    <aside class="minimal-card flex w-80 flex-shrink-0 flex-col bg-white p-5 dark:bg-zinc-900">
      <div class="flex items-center justify-between border-b border-gray-100 pb-4 dark:border-zinc-800">
        <div>
          <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">班级考试看板</h3>
          <p class="mt-1 text-[10px] text-gray-400">以班级为单位查看考试概况</p>
        </div>
        <button
          title="创建班级"
          class="rounded bg-gray-900 p-2 text-white dark:bg-zinc-100 dark:text-zinc-900"
          @click="createDialogVisible = true"
        >
          <Plus class="h-4 w-4" />
        </button>
      </div>

      <div v-loading="loading" class="mt-4 flex-1 space-y-2 overflow-y-auto">
        <button
          v-for="item in classes"
          :key="item.id"
          class="w-full rounded-lg border p-3 text-left transition-all"
          :class="selectedClassId === item.id
            ? 'border-blue-200 bg-blue-50/70 text-blue-800 dark:border-blue-900 dark:bg-blue-950/20 dark:text-blue-300'
            : 'border-gray-100 bg-white hover:bg-gray-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60'"
          @click="loadAnalytics(item.id)"
        >
          <div class="flex items-center justify-between gap-3">
            <span class="truncate text-xs font-semibold">{{ item.name }}</span>
            <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[9px] text-gray-500 dark:bg-zinc-800">{{ item.member_count }} 人</span>
          </div>
          <p class="mt-1 line-clamp-2 text-[10px] text-gray-400">{{ item.description || item.subject || '暂无班级描述' }}</p>
        </button>

        <div v-if="classes.length === 0 && !loading" class="py-12 text-center text-xs text-gray-400">
          暂无班级，请先创建。
        </div>
      </div>
    </aside>

    <section class="flex-1 overflow-y-auto pr-2">
      <div v-if="analytics" class="space-y-6">
        <div class="minimal-card flex flex-wrap items-center justify-between gap-4 bg-white p-5 dark:bg-zinc-900">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-md bg-blue-50 text-blue-600 dark:bg-blue-950/40 dark:text-blue-400">
              <Users class="h-5 w-5" />
            </div>
            <div>
              <h2 class="text-base font-bold text-gray-900 dark:text-zinc-50">{{ analytics.class_info.name }}</h2>
              <p class="mt-0.5 text-xs text-gray-400 dark:text-zinc-500">
                {{ analytics.class_info.student_count }} 名学生 · {{ analytics.summary.paper_count }} 份试卷发布给本班
              </p>
            </div>
          </div>
          <button
            class="inline-flex items-center gap-1.5 rounded border border-gray-200 px-3 py-1.5 text-xs text-gray-500 dark:border-zinc-800"
            @click="selectedClassId && loadAnalytics(selectedClassId)"
          >
            <RefreshCw class="h-3.5 w-3.5" />
            <span>刷新</span>
          </button>
        </div>

        <div class="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
          <div v-for="card in metricCards" :key="card.label" class="minimal-card bg-white p-4 dark:bg-zinc-900">
            <div class="flex items-center gap-2">
              <span class="flex h-7 w-7 items-center justify-center rounded-md" :class="toneClass[card.tone]">
                <component :is="card.icon" class="h-3.5 w-3.5" />
              </span>
              <span class="text-[11px] text-gray-400 dark:text-zinc-500">{{ card.label }}</span>
            </div>
            <div class="mt-3 flex items-baseline gap-1">
              <span class="text-xl font-bold text-gray-900 dark:text-zinc-50">{{ card.value }}</span>
              <span class="text-[11px] text-gray-400 dark:text-zinc-500">{{ card.unit }}</span>
            </div>
          </div>
        </div>

        <section v-if="!hasData" class="minimal-card bg-white p-12 text-center dark:bg-zinc-900">
          <p class="text-sm text-gray-500 dark:text-zinc-400">这个班还没有收到任何试卷。</p>
          <p class="mt-2 text-xs text-gray-400 dark:text-zinc-500">在发题工作台把试卷发布给本班后，班级考试数据会汇总到这里。</p>
        </section>

        <template v-else>
          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-zinc-50">
              <BarChart3 class="h-4 w-4 text-blue-600" />
              各试卷平均得分率
            </h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">横向对比本班在各次考试中的整体表现。</p>
            <BaseChart
              :option="paperRateOption"
              height="320px"
              :is-empty="!(analytics.papers || []).some((p) => p.avg_score_rate != null)"
              empty-text="暂无已批改的试卷成绩"
            />
          </section>

          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-gray-900 dark:text-zinc-50">
              <TrendingUp class="h-4 w-4 text-emerald-600" />
              学生平均得分率
            </h3>
            <p class="mb-3 text-[11px] text-gray-400 dark:text-zinc-500">按跨卷平均得分率排序，低于 60% 标红。</p>
            <BaseChart
              :option="studentRateOption"
              height="320px"
              :is-empty="!(analytics.students || []).some((s) => s.avg_score_rate != null)"
              empty-text="暂无学生成绩"
            />
          </section>

          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-4 text-sm font-semibold text-gray-900 dark:text-zinc-50">逐卷完成情况</h3>
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-gray-100 text-left text-gray-400 dark:border-zinc-800 dark:text-zinc-500">
                    <th class="py-2 pr-4 font-medium">试卷</th>
                    <th class="py-2 pr-4 font-medium">已交 / 应做</th>
                    <th class="py-2 pr-4 font-medium">平均得分率</th>
                    <th class="py-2 pr-4 font-medium">及格率</th>
                    <th class="py-2 pr-4 font-medium">平均用时</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="p in analytics.papers"
                    :key="p.paper_id"
                    class="border-b border-gray-50 text-gray-700 dark:border-zinc-800/50 dark:text-zinc-300"
                  >
                    <td class="py-2 pr-4 font-semibold">{{ p.title }}</td>
                    <td class="py-2 pr-4">{{ p.finished }} / {{ p.assigned }}</td>
                    <td class="py-2 pr-4">
                      <span v-if="p.avg_score_rate != null">{{ p.avg_score_rate }}%</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                    <td class="py-2 pr-4">
                      <span v-if="p.pass_rate != null">{{ p.pass_rate }}%</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                    <td class="py-2 pr-4">
                      <span v-if="p.avg_duration_seconds != null">{{ Math.round(p.avg_duration_seconds / 60) }} 分</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="minimal-card bg-white p-5 dark:bg-zinc-900">
            <h3 class="mb-4 text-sm font-semibold text-gray-900 dark:text-zinc-50">学生明细</h3>
            <div class="overflow-x-auto">
              <table class="w-full text-xs">
                <thead>
                  <tr class="border-b border-gray-100 text-left text-gray-400 dark:border-zinc-800 dark:text-zinc-500">
                    <th class="py-2 pr-4 font-medium">学生</th>
                    <th class="py-2 pr-4 font-medium">已作答</th>
                    <th class="py-2 pr-4 font-medium">平均得分率</th>
                    <th class="py-2 pr-4 font-medium">违规事件</th>
                    <th class="py-2 pr-4 font-medium">待批改</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="s in analytics.students"
                    :key="s.student_id"
                    class="border-b border-gray-50 text-gray-700 dark:border-zinc-800/50 dark:text-zinc-300"
                  >
                    <td class="py-2 pr-4 font-semibold">{{ s.name }}</td>
                    <td class="py-2 pr-4">{{ s.attempted }}</td>
                    <td class="py-2 pr-4">
                      <span v-if="s.avg_score_rate != null" :class="s.avg_score_rate < 60 ? 'text-red-500 font-semibold' : ''">
                        {{ s.avg_score_rate }}%
                      </span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">—</span>
                    </td>
                    <td class="py-2 pr-4">
                      <span v-if="s.flag_count > 0" class="font-semibold text-amber-600 dark:text-amber-400">{{ s.flag_count }}</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">0</span>
                    </td>
                    <td class="py-2 pr-4">
                      <span v-if="s.pending_review > 0" class="font-semibold text-violet-600 dark:text-violet-400">{{ s.pending_review }}</span>
                      <span v-else class="text-gray-300 dark:text-zinc-600">0</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </template>
      </div>

      <div v-else class="minimal-card flex h-full flex-col items-center justify-center bg-white text-center text-gray-400 dark:bg-zinc-900">
        <Users class="mb-3 h-10 w-10 text-gray-300" />
        <p class="text-sm font-semibold">暂无可查看的班级</p>
        <p class="mt-1 text-xs">创建班级后即可查看班级考试概况。</p>
      </div>
    </section>

    <el-dialog v-model="createDialogVisible" title="创建班级" width="520px">
      <div class="space-y-4">
        <label class="block space-y-1">
          <span class="text-xs text-gray-500">班级名称</span>
          <input v-model="classForm.name" class="w-full rounded border border-gray-200 px-3 py-2 text-xs dark:border-zinc-800" placeholder="例如：2026 AI 伴学实验班" />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label class="space-y-1">
            <span class="text-xs text-gray-500">年级</span>
            <input v-model="classForm.grade" class="w-full rounded border border-gray-200 px-3 py-2 text-xs dark:border-zinc-800" />
          </label>
          <label class="space-y-1">
            <span class="text-xs text-gray-500">学科</span>
            <input v-model="classForm.subject" class="w-full rounded border border-gray-200 px-3 py-2 text-xs dark:border-zinc-800" />
          </label>
        </div>
        <label class="block space-y-1">
          <span class="text-xs text-gray-500">说明</span>
          <textarea v-model="classForm.description" rows="3" class="w-full resize-none rounded border border-gray-200 px-3 py-2 text-xs dark:border-zinc-800"></textarea>
        </label>
        <label class="block space-y-1">
          <span class="text-xs text-gray-500">班级学生</span>
          <button
            type="button"
            class="flex min-h-10 w-full items-center justify-between gap-3 rounded border border-gray-200 px-3 py-2 text-left text-xs dark:border-zinc-800"
            @click="classStudentPickerVisible = true"
          >
            <span class="min-w-0 truncate text-gray-600 dark:text-zinc-300">
              {{ classForm.student_ids.length ? selectedClassStudentNames : '选择学生' }}
            </span>
            <span class="shrink-0 rounded bg-blue-50 px-2 py-1 text-[10px] text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
              {{ classForm.student_ids.length }} 人
            </span>
          </button>
        </label>
      </div>
      <template #footer>
        <button class="mr-2 rounded border border-gray-200 px-4 py-1.5 text-xs dark:border-zinc-800" @click="createDialogVisible = false">取消</button>
        <button class="rounded bg-gray-900 px-4 py-1.5 text-xs text-white dark:bg-zinc-100 dark:text-zinc-900" @click="createClass">创建</button>
      </template>
    </el-dialog>

    <StudentPickerDialog
      v-model:visible="classStudentPickerVisible"
      v-model="classForm.student_ids"
      title="选择班级学生"
      @confirm="handleClassStudentsConfirm"
    />
  </div>
</template>
