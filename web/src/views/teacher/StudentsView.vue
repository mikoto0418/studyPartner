<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { User, Calendar, Flame, BookOpen, ChevronRight, Brain, UserCheck } from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import { userApi } from '../../api/modules/user'
import type { UserOut } from '../../api/modules/user'
import { heatmapApi } from '../../api/modules/heatmap'
import { reviewsApi } from '../../api/modules/reviews'
import type { DailyReviewListOut, DailyReviewOut } from '../../api/modules/reviews'

// States
const students = ref<UserOut[]>([])
const selectedStudent = ref<UserOut | null>(null)
const loadingStudents = ref(false)

// Heatmap States
const heatmapWeeks = ref<any[]>([])
const loadingHeatmap = ref(false)

// Review States
const reviews = ref<DailyReviewListOut[]>([])
const loadingReviews = ref(false)
const selectedReview = ref<DailyReviewOut | null>(null)
const loadingReviewDetail = ref(false)

const displayNameOf = (student?: UserOut | null) => student?.display_name || student?.nickname?.trim() || '未设置姓名'
const avatarTextOf = (student?: UserOut | null) => (student?.display_name || student?.nickname?.trim() || '未').charAt(0).toUpperCase()

// Load student roster (role_code = student)
const loadStudents = async () => {
  loadingStudents.value = true
  try {
    const res = await userApi.listUsers({ role_code: 'student', page_size: 100 })
    students.value = res.data?.items || []
    if (students.value.length > 0 && !selectedStudent.value) {
      selectStudent(students.value[0])
    }
  } catch (error) {
    console.error("Failed to load students list", error)
    ElMessage.error("获取学生列表失败")
  } finally {
    loadingStudents.value = false
  }
}

// Select a student
const selectStudent = (student: UserOut) => {
  selectedStudent.value = student
  selectedReview.value = null
  loadStudentHeatmap(student.id)
  loadStudentReviews(student.id)
}

// Calculate Heatmap points for a specific student
const loadStudentHeatmap = async (studentId: string) => {
  loadingHeatmap.value = true
  try {
    const res = await heatmapApi.getHeatmapData({ student_id: studentId })
    const data = res.data || []
    
    const scoreMap = new Map<string, number>()
    data.forEach((p: any) => {
      scoreMap.set(p.date, p.count)
    })

    const today = new Date()
    const startDate = new Date()
    startDate.setDate(today.getDate() - 364)

    const startDayOfWeek = startDate.getDay() 
    const calendarStartDate = new Date(startDate)
    calendarStartDate.setDate(startDate.getDate() - startDayOfWeek)

    const endDayOfWeek = today.getDay()
    const calendarEndDate = new Date(today)
    calendarEndDate.setDate(today.getDate() + (6 - endDayOfWeek))

    const weeks: any[][] = []
    let currentWeek: any[] = []
    
    let currentCursor = new Date(calendarStartDate)
    while (currentCursor <= calendarEndDate) {
      const dateStr = currentCursor.toISOString().split('T')[0]
      const count = scoreMap.has(dateStr) ? scoreMap.get(dateStr)! : 0
      
      let level = 0
      if (count > 0 && count <= 3) level = 1
      else if (count > 3 && count <= 8) level = 2
      else if (count > 8 && count <= 15) level = 3
      else if (count > 15) level = 4

      const formattedDate = currentCursor.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', year: 'numeric' })
      const weekday = currentCursor.getDay()

      currentWeek.push({
        date: dateStr,
        formattedDate,
        count,
        level,
        weekday,
        isPadding: currentCursor < startDate || currentCursor > today
      })

      if (currentWeek.length === 7) {
        weeks.push(currentWeek)
        currentWeek = []
      }

      currentCursor.setDate(currentCursor.getDate() + 1)
    }

    heatmapWeeks.value = weeks
  } catch (error) {
    console.error("Failed to load student heatmap", error)
  } finally {
    loadingHeatmap.value = false
  }
}

// Get heatmap colors
const getHeatmapColor = (level: number) => {
  switch (level) {
    case 1: return 'bg-blue-100 dark:bg-blue-950/20 border border-blue-200/30 dark:border-blue-900/20'
    case 2: return 'bg-blue-300 dark:bg-blue-800/40 border border-blue-400/30 dark:border-blue-700/20'
    case 3: return 'bg-blue-500 dark:bg-blue-600 border border-blue-500/30'
    case 4: return 'bg-blue-700 dark:bg-blue-400 border border-blue-700/30'
    default: return 'bg-gray-100 dark:bg-zinc-800 border border-transparent'
  }
}

// Load review lists for the student
const loadStudentReviews = async (studentId: string) => {
  loadingReviews.value = true
  try {
    const res = await reviewsApi.listReviews({ student_id: studentId, page_size: 15 })
    reviews.value = res.data?.items || []
  } catch (err) {
    console.error("Failed to load reviews list", err)
  } finally {
    loadingReviews.value = false
  }
}

// View specific review details
const viewReviewDetails = async (reviewListItem: DailyReviewListOut) => {
  loadingReviewDetail.value = true
  selectedReview.value = null
  try {
    const res = await reviewsApi.getReview(reviewListItem.date, { student_id: selectedStudent.value!.id })
    selectedReview.value = res.data
  } catch (err) {
    ElMessage.error("获取复盘详情失败")
  } finally {
    loadingReviewDetail.value = false
  }
}

onMounted(() => {
  loadStudents()
})
</script>

<template>
  <div class="h-[calc(100vh-8rem)] flex items-stretch gap-6 -m-4 p-4 overflow-hidden">
    <!-- Left Roster column (4 cols equivalent width) -->
    <div class="w-80 minimal-card p-5 flex flex-col h-full bg-white dark:bg-zinc-900 flex-shrink-0">
      <div class="pb-4 border-b border-gray-100 dark:border-zinc-800 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
          <UserCheck class="w-4 h-4 text-blue-600 dark:text-blue-500" />
          <span>我的指导学生</span>
        </h3>
        <span class="text-[10px] bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full font-bold">
          {{ students.length }} 人
        </span>
      </div>

      <!-- Search list -->
      <div class="flex-1 overflow-y-auto mt-4 space-y-2 pr-1">
        <div
          v-for="st in students"
          :key="st.id"
          @click="selectStudent(st)"
          class="p-3 rounded-lg border text-xs transition-all cursor-pointer flex items-center justify-between"
          :class="
            selectedStudent && selectedStudent.id === st.id
              ? 'bg-blue-50/50 border-blue-200 text-blue-700 font-semibold dark:bg-blue-950/20 dark:border-blue-900/50 dark:text-blue-400'
              : 'bg-white hover:bg-gray-50 border-gray-100 dark:bg-zinc-900 dark:border-zinc-800/50 dark:hover:bg-zinc-800 text-gray-600 dark:text-zinc-300'
          "
        >
          <div class="flex items-center space-x-3 truncate">
            <div class="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-950/30 flex items-center justify-center text-blue-600 font-bold uppercase text-xs">
              {{ avatarTextOf(st) }}
            </div>
            <div class="truncate">
              <span class="font-medium text-gray-800 dark:text-zinc-100 block">{{ displayNameOf(st) }}</span>
              <span class="text-[9px] text-gray-400 font-mono block">账号: {{ st.username }} · 学号: {{ st.student_profile?.student_id || '暂无学号' }}</span>
            </div>
          </div>
          <ChevronRight class="w-4 h-4 text-gray-400" />
        </div>

        <div v-if="students.length === 0 && !loadingStudents" class="py-12 text-center text-gray-400">
          暂无关联的指导学生。
        </div>
      </div>
    </div>

    <!-- Right Detail Column -->
    <div class="flex-1 flex flex-col h-full overflow-hidden">
      <div v-if="selectedStudent" class="h-full flex flex-col gap-6 overflow-y-auto pr-2">
        <!-- 1. Profile header -->
        <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 flex-shrink-0">
          <div class="flex items-center space-x-4">
            <div class="w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-950/40 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold text-lg">
              {{ avatarTextOf(selectedStudent) }}
            </div>
            <div>
              <h3 class="text-sm font-bold text-gray-900 dark:text-zinc-50">{{ displayNameOf(selectedStudent) }}</h3>
              <p class="text-xs text-gray-400 dark:text-zinc-500">
                账号: {{ selectedStudent.username }} &bull; 邮箱: {{ selectedStudent.email }} &bull;
                研究方向: {{ selectedStudent.student_profile?.research_direction || '未设定' }}
              </p>
            </div>
          </div>

          <div class="grid grid-cols-2 md:flex gap-4 text-center md:text-left">
            <div class="px-4 py-2 bg-gray-50 dark:bg-zinc-950 rounded-lg border border-gray-100 dark:border-zinc-800">
              <span class="text-[9px] text-gray-400 block font-medium">年级</span>
              <span class="text-xs font-semibold text-gray-800 dark:text-zinc-200">{{ selectedStudent.student_profile?.grade || '未完善' }}</span>
            </div>
            <div class="px-4 py-2 bg-gray-50 dark:bg-zinc-950 rounded-lg border border-gray-100 dark:border-zinc-800">
              <span class="text-[9px] text-gray-400 block font-medium">所学专业</span>
              <span class="text-xs font-semibold text-gray-800 dark:text-zinc-200">{{ selectedStudent.student_profile?.major || '未完善' }}</span>
            </div>
          </div>
        </div>

        <!-- 2. Heatmap panel -->
        <div class="minimal-card p-6 bg-white dark:bg-zinc-900 flex-shrink-0">
          <div class="flex items-center justify-between mb-4">
            <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 flex items-center space-x-1.5">
              <Flame class="w-4 h-4 text-orange-500 animate-pulse" />
              <span>365 天学情行为活跃度热力图</span>
            </h4>
            <span class="text-[9px] text-gray-400">督学模式（鼠标悬停查看每日积分细节）</span>
          </div>

          <!-- Heatmap grid -->
          <div class="flex flex-col space-y-2 overflow-x-auto" v-loading="loadingHeatmap">
            <div class="flex space-x-1 flex-shrink-0">
              <div
                v-for="(week, wIdx) in heatmapWeeks"
                :key="wIdx"
                class="flex flex-col space-y-1"
              >
                <el-tooltip
                  v-for="day in week"
                  :key="day.date"
                  :content="day.isPadding ? '范围外无数据' : `${day.formattedDate} : 活跃度积分 ${day.count}`"
                  placement="top"
                  :show-after="100"
                >
                  <div
                    class="w-3.5 h-3.5 rounded-sm transition-all cursor-pointer hover:ring-2 hover:ring-blue-500/50"
                    :class="[getHeatmapColor(day.level), day.isPadding ? 'opacity-30' : '']"
                  ></div>
                </el-tooltip>
              </div>
            </div>
            <div class="flex items-center space-x-2 text-[10px] text-gray-400 dark:text-zinc-500 pt-2 justify-end">
              <span>低活跃</span>
              <div class="w-2.5 h-2.5 rounded-sm bg-gray-100 dark:bg-zinc-800"></div>
              <div class="w-2.5 h-2.5 rounded-sm bg-blue-100/40 border border-blue-200/30"></div>
              <div class="w-2.5 h-2.5 rounded-sm bg-blue-300 dark:bg-blue-800/40 border border-blue-400/30"></div>
              <div class="w-2.5 h-2.5 rounded-sm bg-blue-500 dark:bg-blue-600"></div>
              <div class="w-2.5 h-2.5 rounded-sm bg-blue-700 dark:bg-blue-400"></div>
              <span>高活跃</span>
            </div>
          </div>
        </div>

        <!-- 3. Bottom Columns: Reviews logs & detailed report -->
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch flex-1 min-h-[350px]">
          <!-- Review list on left -->
          <div class="lg:col-span-5 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-[400px]">
            <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 mb-3 flex items-center space-x-1.5 flex-shrink-0">
              <Calendar class="w-4 h-4 text-blue-600" />
              <span>历史每日复盘日志</span>
            </h4>
            <div class="flex-1 overflow-y-auto space-y-2 pr-1" v-loading="loadingReviews">
              <div
                v-for="rv in reviews"
                :key="rv.id"
                @click="viewReviewDetails(rv)"
                class="p-3 rounded-lg border text-xs hover:border-blue-500/50 hover:bg-gray-50/50 dark:hover:bg-zinc-800/30 cursor-pointer flex items-center justify-between transition-all"
              >
                <div>
                  <span class="font-bold text-gray-800 dark:text-zinc-200 block">{{ rv.date }}</span>
                  <span class="text-[10px] text-gray-400 block line-clamp-1 mt-1">{{ rv.summary_preview }}</span>
                </div>
                <div class="flex items-center space-x-1.5 flex-shrink-0">
                  <span class="text-[9px] px-1.5 py-0.5 rounded font-mono bg-blue-50 dark:bg-blue-950/20 text-blue-600 dark:text-blue-400">
                    {{ rv.study_time_minutes }}分钟
                  </span>
                  <ChevronRight class="w-3.5 h-3.5 text-gray-400" />
                </div>
              </div>

              <div v-if="reviews.length === 0" class="h-full flex items-center justify-center text-xs text-gray-400 py-12">
                该学生暂无每日复盘报告。
              </div>
            </div>
          </div>

          <!-- Review detail container on right -->
          <div class="lg:col-span-7 minimal-card p-6 bg-white dark:bg-zinc-900 flex flex-col h-[400px]">
            <h4 class="text-xs font-bold text-gray-900 dark:text-zinc-50 mb-3 flex items-center space-x-1.5 flex-shrink-0">
              <Brain class="w-4 h-4 text-indigo-500" />
              <span>学情复盘与记忆分析</span>
            </h4>

            <div class="flex-1 overflow-y-auto space-y-4 pr-1" v-loading="loadingReviewDetail">
              <div v-if="selectedReview" class="space-y-4 text-xs">
                <!-- Header Stats -->
                <div class="grid grid-cols-2 gap-4 pb-3 border-b border-gray-100 dark:border-zinc-800">
                  <div>
                    <span class="text-[9px] text-gray-400 block font-medium">复盘日期</span>
                    <span class="font-bold text-gray-800 dark:text-zinc-200">{{ selectedReview.date }}</span>
                  </div>
                  <div>
                    <span class="text-[9px] text-gray-400 block font-medium">学习时长统计</span>
                    <span class="font-bold text-gray-800 dark:text-zinc-200">{{ selectedReview.study_time_minutes }} 分钟</span>
                  </div>
                </div>

                <div class="space-y-1.5">
                  <span class="text-[10px] text-emerald-600 dark:text-emerald-400 font-bold block">★ 学习亮点</span>
                  <ul class="list-disc pl-4 space-y-1 text-gray-600 dark:text-zinc-300">
                    <li v-for="(h, idx) in selectedReview.highlights" :key="idx">{{ h }}</li>
                  </ul>
                </div>

                <div class="space-y-1.5">
                  <span class="text-[10px] text-amber-600 dark:text-amber-400 font-bold block">▲ 关注与薄弱项</span>
                  <ul class="list-disc pl-4 space-y-1 text-gray-600 dark:text-zinc-300">
                    <li v-for="(c, idx) in selectedReview.concerns" :key="idx">{{ c }}</li>
                  </ul>
                </div>

                <div class="space-y-1.5">
                  <span class="text-[10px] text-blue-600 dark:text-blue-400 font-bold block">✔ AI 伴学诊断与建议</span>
                  <ul class="list-disc pl-4 space-y-1 text-gray-600 dark:text-zinc-300">
                    <li v-for="(s, idx) in selectedReview.suggestions" :key="idx">{{ s }}</li>
                  </ul>
                </div>

                <div v-if="selectedReview.new_memories && selectedReview.new_memories.length > 0" class="space-y-1.5 p-3 bg-indigo-50/30 dark:bg-indigo-950/10 rounded-lg border border-indigo-100/30 dark:border-indigo-900/20">
                  <span class="text-[10px] text-indigo-600 dark:text-indigo-400 font-bold block flex items-center space-x-1">
                    <Brain class="w-3.5 h-3.5" />
                    <span>本阶段提取存入的 AI 长期记忆</span>
                  </span>
                  <div class="space-y-1 text-[10px] text-gray-500 dark:text-zinc-400 font-mono">
                    <div v-for="(m, idx) in selectedReview.new_memories" :key="idx" class="flex items-center space-x-1.5">
                      <span class="w-1.5 h-1.5 rounded-full bg-indigo-400 flex-shrink-0"></span>
                      <span>{{ m }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Default Placeholder -->
              <div v-else class="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-2 py-16">
                <BookOpen class="w-8 h-8 text-gray-200 dark:text-zinc-700" />
                <p>请点击左侧列表的复盘日志，查看当天的详细学情与记忆诊断。</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="h-full flex flex-col items-center justify-center text-center text-gray-400 space-y-2 py-16 minimal-card bg-white dark:bg-zinc-900">
        <User class="w-12 h-12 text-gray-200 dark:text-zinc-800" />
        <h4 class="text-xs font-semibold">未选中学生</h4>
        <p class="text-[10px] text-gray-400">请在左侧列表中点击选择一位您所指导的学生。</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}
.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.08);
  border-radius: 4px;
}
.dark .overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.08);
}
</style>
