<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { BookOpenCheck, Edit, Plus, Trash2 } from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { calendarApi } from '../../api/modules/calendar'
import type { CalendarEventData, CalendarEventOut } from '../../api/modules/calendar'

const events = ref<CalendarEventOut[]>([])
const loading = ref(false)
const isDialogOpen = ref(false)
const isDetailOpen = ref(false)
const selectedEvent = ref<CalendarEventOut | null>(null)
const currentRange = ref({ start: '', end: '' })

const eventForm = ref({
  id: '',
  title: '',
  description: '',
  event_type: 'personal',
  status: 'planned',
  start_time: '',
  end_time: '',
  all_day: false,
  color: '#3b82f6',
})

const eventTypes = [
  { label: '个人日程', value: 'personal' },
  { label: '学习任务', value: 'task' },
  { label: '倒数纪念', value: 'countdown' },
]

const eventStatuses = [
  { label: '计划中', value: 'planned' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
]

const colors = [
  { name: '蓝', value: '#3b82f6' },
  { name: '绿', value: '#10b981' },
  { name: '橙', value: '#f59e0b' },
  { name: '灰', value: '#6b7280' },
]

const teacherTaskCount = computed(() => events.value.filter(isTeacherTask).length)
const upcomingEvents = computed(() =>
  [...events.value].sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime()),
)

function isTeacherTask(event?: CalendarEventOut | null) {
  return event?.event_type === 'teacher_assigned'
}

function eventTypeLabel(type: string) {
  const labels: Record<string, string> = {
    personal: '个人日程',
    task: '学习任务',
    countdown: '倒数纪念',
    teacher_assigned: '导师任务',
  }
  return labels[type] || '日程'
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    planned: '计划中',
    in_progress: '进行中',
    submitted: '已提交',
    completed: '已完成',
    rejected: '需修改',
    cancelled: '已取消',
  }
  return labels[status] || status
}

function typeBadgeClass(type: string) {
  if (type === 'teacher_assigned') {
    return 'bg-indigo-50 text-indigo-700 border-indigo-100 dark:bg-indigo-950/30 dark:text-indigo-300 dark:border-indigo-900/40'
  }
  if (type === 'task') {
    return 'bg-amber-50 text-amber-700 border-amber-100 dark:bg-amber-950/30 dark:text-amber-300 dark:border-amber-900/40'
  }
  if (type === 'countdown') {
    return 'bg-emerald-50 text-emerald-700 border-emerald-100 dark:bg-emerald-950/30 dark:text-emerald-300 dark:border-emerald-900/40'
  }
  return 'bg-blue-50 text-blue-700 border-blue-100 dark:bg-blue-950/30 dark:text-blue-300 dark:border-blue-900/40'
}

function statusBadgeClass(status: string) {
  if (status === 'completed') return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/20 dark:text-emerald-300'
  if (status === 'submitted') return 'bg-cyan-50 text-cyan-700 dark:bg-cyan-950/20 dark:text-cyan-300'
  if (status === 'rejected' || status === 'cancelled') return 'bg-red-50 text-red-700 dark:bg-red-950/20 dark:text-red-300'
  if (status === 'in_progress') return 'bg-blue-50 text-blue-700 dark:bg-blue-950/20 dark:text-blue-300'
  return 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300'
}

function toLocalInputValue(dateStr: string) {
  const d = new Date(dateStr)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}

function formatDate(isoStr: string) {
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function resetCreateForm(start?: string, end?: string, allDay = false) {
  const now = new Date()
  const defaultStart = start ? toLocalInputValue(start) : toLocalInputValue(now.toISOString())
  const defaultEnd = end ? toLocalInputValue(end) : toLocalInputValue(new Date(now.getTime() + 3600000).toISOString())
  eventForm.value = {
    id: '',
    title: '',
    description: '',
    event_type: 'personal',
    status: 'planned',
    start_time: defaultStart,
    end_time: defaultEnd,
    all_day: allDay,
    color: '#3b82f6',
  }
}

async function fetchEvents() {
  if (!currentRange.value.start || !currentRange.value.end) return
  loading.value = true
  try {
    const res = await calendarApi.listEvents({
      start_time: currentRange.value.start,
      end_time: currentRange.value.end,
    })
    events.value = res.data || []
  } catch (error) {
    events.value = []
  } finally {
    loading.value = false
  }
}

async function persistMove(eventId: string, start: Date | null, end: Date | null, allDay: boolean, revert: () => void) {
  const matched = events.value.find((item) => item.id === eventId)
  if (!matched || isTeacherTask(matched) || !start) {
    revert()
    return
  }

  const payload: Partial<CalendarEventData> = {
    start_time: start.toISOString(),
    end_time: (end || start).toISOString(),
    all_day: allDay,
  }

  try {
    await calendarApi.updateEvent(eventId, payload)
    ElMessage.success('日程时间已更新')
    fetchEvents()
  } catch (error) {
    revert()
    ElMessage.error('更新时间失败')
  }
}

const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  locale: 'zh-cn',
  firstDay: 1,
  editable: true,
  selectable: true,
  eventDurationEditable: true,
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay',
  },
  buttonText: {
    today: '今天',
    month: '月',
    week: '周',
    day: '日',
  },
  events: events.value.map((event) => ({
    id: event.id,
    title: isTeacherTask(event) ? `导师任务 · ${event.title}` : event.title,
    start: event.start_time,
    end: event.end_time,
    allDay: event.all_day,
    color: event.color || (isTeacherTask(event) ? '#4f46e5' : '#3b82f6'),
    editable: !isTeacherTask(event),
    classNames: [isTeacherTask(event) ? 'fc-event-teacher-task' : 'fc-event-personal-task'],
    extendedProps: {
      description: event.description,
      event_type: event.event_type,
      status: event.status,
    },
  })),
  loading: (active: boolean) => {
    loading.value = active
  },
  datesSet: (info: { startStr: string; endStr: string }) => {
    currentRange.value = { start: info.startStr, end: info.endStr }
    fetchEvents()
  },
  select: (info: { startStr: string; endStr: string; allDay: boolean }) => {
    resetCreateForm(info.startStr, info.endStr, info.allDay)
    isDialogOpen.value = true
  },
  eventClick: (info: { event: { id: string } }) => {
    const matched = events.value.find((item) => item.id === info.event.id)
    if (matched) {
      selectedEvent.value = matched
      isDetailOpen.value = true
    }
  },
  eventDrop: (info: any) => {
    persistMove(info.event.id, info.event.start, info.event.end, info.event.allDay, info.revert)
  },
  eventResize: (info: any) => {
    persistMove(info.event.id, info.event.start, info.event.end, info.event.allDay, info.revert)
  },
}))

async function handleSaveEvent() {
  if (!eventForm.value.title.trim()) {
    ElMessage.warning('请输入日程标题')
    return
  }

  const payload: CalendarEventData = {
    title: eventForm.value.title.trim(),
    description: eventForm.value.description.trim() || undefined,
    event_type: eventForm.value.event_type,
    status: eventForm.value.status,
    start_time: new Date(eventForm.value.start_time).toISOString(),
    end_time: new Date(eventForm.value.end_time).toISOString(),
    all_day: eventForm.value.all_day,
    color: eventForm.value.color,
  }

  try {
    if (eventForm.value.id) {
      await calendarApi.updateEvent(eventForm.value.id, payload)
      ElMessage.success('日程已更新')
    } else {
      await calendarApi.createEvent(payload)
      ElMessage.success('日程已创建')
    }
    isDialogOpen.value = false
    fetchEvents()
  } catch (error) {
    ElMessage.error('保存日程失败')
  }
}

function handleEditSelected() {
  if (!selectedEvent.value) return
  if (isTeacherTask(selectedEvent.value)) {
    ElMessage.info('导师任务来自老师布置，学生端仅展示')
    return
  }

  const event = selectedEvent.value
  eventForm.value = {
    id: event.id,
    title: event.title,
    description: event.description || '',
    event_type: event.event_type,
    status: event.status,
    start_time: toLocalInputValue(event.start_time),
    end_time: toLocalInputValue(event.end_time),
    all_day: event.all_day,
    color: event.color || '#3b82f6',
  }
  isDetailOpen.value = false
  isDialogOpen.value = true
}

async function handleDeleteSelected() {
  if (!selectedEvent.value) return
  if (isTeacherTask(selectedEvent.value)) {
    ElMessage.info('导师任务不能在学生端删除')
    return
  }

  try {
    await ElMessageBox.confirm('确定删除该日程吗？', '提示', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await calendarApi.deleteEvent(selectedEvent.value.id)
    ElMessage.success('日程已删除')
    isDetailOpen.value = false
    selectedEvent.value = null
    fetchEvents()
  } catch (error) {
    // user cancelled or request failed, both can stay quiet here
  }
}

onMounted(() => {
  const now = new Date()
  currentRange.value = {
    start: new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
    end: new Date(now.getFullYear(), now.getMonth() + 1, 1).toISOString(),
  }
  fetchEvents()
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 h-[calc(100vh-8rem)]">
    <section class="lg:col-span-9 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-lg p-5 flex flex-col min-h-0 shadow-sm">
      <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">月历计划</h2>
          <p class="mt-1 text-[11px] text-gray-400 dark:text-zinc-500">
            个人日程可编辑，导师任务从老师布置任务自动同步。
          </p>
        </div>
        <div class="flex items-center gap-2 text-[11px]">
          <span class="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 font-medium text-indigo-700 dark:border-indigo-900/40 dark:bg-indigo-950/30 dark:text-indigo-300">
            导师任务 {{ teacherTaskCount }}
          </span>
          <button
            @click="() => { resetCreateForm(); isDialogOpen = true }"
            class="inline-flex items-center gap-1.5 rounded-md bg-gray-900 px-3 py-1.5 font-medium text-white transition hover:bg-gray-800 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200"
          >
            <Plus class="h-3.5 w-3.5" />
            <span>新建日程</span>
          </button>
        </div>
      </div>

      <div class="relative flex-1 min-h-0" v-loading="loading">
        <FullCalendar :options="calendarOptions" class="h-full fc-theme-minimalist" />
      </div>
    </section>

    <aside class="lg:col-span-3 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-lg p-5 flex flex-col min-h-0 shadow-sm">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-xs font-semibold text-gray-900 dark:text-zinc-50">近期安排</h3>
        <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-zinc-800 dark:text-zinc-400">
          {{ upcomingEvents.length }}
        </span>
      </div>

      <div class="flex-1 space-y-3 overflow-y-auto pr-1">
        <button
          v-for="item in upcomingEvents"
          :key="item.id"
          @click="() => { selectedEvent = item; isDetailOpen = true }"
          class="group relative w-full overflow-hidden rounded-lg border bg-gray-50/50 p-3 text-left transition hover:bg-white hover:shadow-sm dark:bg-zinc-950/20 dark:hover:bg-zinc-900/70"
          :class="isTeacherTask(item) ? 'border-indigo-100 dark:border-indigo-900/40' : 'border-gray-100 dark:border-zinc-800'"
        >
          <span class="absolute inset-y-0 left-0 w-1" :style="{ backgroundColor: item.color || (isTeacherTask(item) ? '#4f46e5' : '#3b82f6') }"></span>
          <div class="ml-2 space-y-2">
            <div class="flex items-start justify-between gap-2">
              <h4 class="line-clamp-2 text-xs font-semibold text-gray-900 dark:text-zinc-100">{{ item.title }}</h4>
              <span class="shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-semibold" :class="typeBadgeClass(item.event_type)">
                {{ eventTypeLabel(item.event_type) }}
              </span>
            </div>
            <p v-if="item.description" class="line-clamp-1 text-[10px] text-gray-400 dark:text-zinc-500">{{ item.description }}</p>
            <div class="flex items-center justify-between text-[10px] text-gray-400 dark:text-zinc-500">
              <span>{{ formatDate(item.start_time) }}</span>
              <span class="rounded px-1.5 py-0.5 font-medium" :class="statusBadgeClass(item.status)">
                {{ statusLabel(item.status) }}
              </span>
            </div>
          </div>
        </button>

        <div v-if="upcomingEvents.length === 0" class="flex h-48 flex-col items-center justify-center text-center text-gray-400 dark:text-zinc-500">
          <BookOpenCheck class="mb-2 h-8 w-8 text-gray-200 dark:text-zinc-800" />
          <p class="text-xs">本月暂无日程</p>
        </div>
      </div>
    </aside>

    <el-dialog v-model="isDialogOpen" :title="eventForm.id ? '编辑日程' : '创建日程'" width="460px" class="minimal-dialog" destroy-on-close>
      <div class="space-y-4 text-xs">
        <div>
          <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">标题</label>
          <input
            v-model="eventForm.title"
            type="text"
            placeholder="输入日程名称"
            class="w-full rounded border border-gray-200 bg-transparent px-3 py-2 text-xs outline-none transition focus:border-gray-900 dark:border-zinc-800 dark:focus:border-zinc-100"
          />
        </div>

        <div>
          <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">详情</label>
          <textarea
            v-model="eventForm.description"
            rows="3"
            placeholder="备忘、说明或计划内容"
            class="w-full resize-none rounded border border-gray-200 bg-transparent px-3 py-2 text-xs outline-none transition focus:border-gray-900 dark:border-zinc-800 dark:focus:border-zinc-100"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">类型</label>
            <select v-model="eventForm.event_type" class="w-full rounded border border-gray-200 bg-white px-3 py-2 text-xs outline-none focus:border-gray-900 dark:border-zinc-800 dark:bg-zinc-900 dark:focus:border-zinc-100">
              <option v-for="item in eventTypes" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">状态</label>
            <select v-model="eventForm.status" class="w-full rounded border border-gray-200 bg-white px-3 py-2 text-xs outline-none focus:border-gray-900 dark:border-zinc-800 dark:bg-zinc-900 dark:focus:border-zinc-100">
              <option v-for="item in eventStatuses" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">开始时间</label>
            <input v-model="eventForm.start_time" type="datetime-local" class="w-full rounded border border-gray-200 bg-transparent px-3 py-2 text-xs outline-none focus:border-gray-900 dark:border-zinc-800 dark:focus:border-zinc-100" />
          </div>
          <div>
            <label class="mb-1 block text-[11px] font-medium text-gray-500 dark:text-zinc-400">结束时间</label>
            <input v-model="eventForm.end_time" type="datetime-local" class="w-full rounded border border-gray-200 bg-transparent px-3 py-2 text-xs outline-none focus:border-gray-900 dark:border-zinc-800 dark:focus:border-zinc-100" />
          </div>
        </div>

        <div class="flex items-center justify-between">
          <label class="flex items-center gap-2 text-gray-600 dark:text-zinc-400">
            <input v-model="eventForm.all_day" type="checkbox" class="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
            <span>全天日程</span>
          </label>
          <div class="flex items-center gap-2">
            <span class="text-[11px] text-gray-400">颜色</span>
            <button
              v-for="color in colors"
              :key="color.value"
              :title="color.name"
              @click="eventForm.color = color.value"
              class="h-5 w-5 rounded-full border transition"
              :class="eventForm.color === color.value ? 'scale-110 border-gray-900 dark:border-zinc-100' : 'border-transparent'"
              :style="{ backgroundColor: color.value }"
            ></button>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <button @click="isDialogOpen = false" class="rounded border border-gray-200 px-4 py-1.5 text-xs text-gray-500 transition hover:bg-gray-50 dark:border-zinc-800 dark:hover:bg-zinc-800">取消</button>
          <button @click="handleSaveEvent" class="rounded bg-gray-900 px-4 py-1.5 text-xs font-medium text-white transition hover:bg-gray-800 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200">保存</button>
        </div>
      </template>
    </el-dialog>

    <el-dialog v-model="isDetailOpen" title="日程详情" width="420px" class="minimal-dialog">
      <div v-if="selectedEvent" class="space-y-4 text-xs">
        <div class="space-y-2">
          <div class="flex items-start gap-2">
            <span class="mt-1 h-2.5 w-2.5 shrink-0 rounded-full" :style="{ backgroundColor: selectedEvent.color || '#3b82f6' }"></span>
            <h3 class="text-sm font-semibold leading-relaxed text-gray-900 dark:text-zinc-50">{{ selectedEvent.title }}</h3>
          </div>
          <div class="flex flex-wrap gap-2">
            <span class="rounded border px-2 py-0.5 text-[10px] font-semibold" :class="typeBadgeClass(selectedEvent.event_type)">
              {{ eventTypeLabel(selectedEvent.event_type) }}
            </span>
            <span class="rounded px-2 py-0.5 text-[10px] font-semibold" :class="statusBadgeClass(selectedEvent.status)">
              {{ statusLabel(selectedEvent.status) }}
            </span>
          </div>
        </div>

        <div v-if="isTeacherTask(selectedEvent)" class="rounded-lg border border-indigo-100 bg-indigo-50/60 p-3 text-[11px] leading-relaxed text-indigo-700 dark:border-indigo-900/40 dark:bg-indigo-950/20 dark:text-indigo-300">
          该事项来自老师布置任务，学生端会同步展示但不可编辑或删除。
        </div>

        <p v-if="selectedEvent.description" class="whitespace-pre-wrap rounded-lg border border-gray-100 bg-gray-50 p-3 leading-relaxed text-gray-600 dark:border-zinc-800 dark:bg-zinc-950/30 dark:text-zinc-300">
          {{ selectedEvent.description }}
        </p>

        <div class="space-y-2 text-gray-500 dark:text-zinc-400">
          <div class="flex justify-between gap-4">
            <span>开始</span>
            <span class="font-medium text-gray-800 dark:text-zinc-200">{{ formatDate(selectedEvent.start_time) }}</span>
          </div>
          <div class="flex justify-between gap-4">
            <span>结束</span>
            <span class="font-medium text-gray-800 dark:text-zinc-200">{{ formatDate(selectedEvent.end_time) }}</span>
          </div>
          <div v-if="selectedEvent.all_day" class="flex justify-between gap-4">
            <span>全天</span>
            <span class="font-medium text-gray-800 dark:text-zinc-200">是</span>
          </div>
        </div>

        <div v-if="!isTeacherTask(selectedEvent)" class="flex justify-end gap-2 border-t border-gray-100 pt-4 dark:border-zinc-800">
          <button @click="handleDeleteSelected" class="inline-flex items-center gap-1 rounded border border-red-200 px-3 py-1.5 text-xs text-red-600 transition hover:bg-red-50 dark:border-red-900/50 dark:hover:bg-red-950/20">
            <Trash2 class="h-3.5 w-3.5" />
            <span>删除</span>
          </button>
          <button @click="handleEditSelected" class="inline-flex items-center gap-1 rounded border border-gray-200 px-3 py-1.5 text-xs text-gray-700 transition hover:bg-gray-50 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-800">
            <Edit class="h-3.5 w-3.5" />
            <span>修改</span>
          </button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style>
.fc {
  --fc-border-color: #e4e4e7;
  --fc-button-bg-color: transparent;
  --fc-button-border-color: #e4e4e7;
  --fc-button-hover-bg-color: #f4f4f5;
  --fc-button-hover-border-color: #e4e4e7;
  --fc-button-active-bg-color: #e4e4e7;
  --fc-button-active-border-color: #d4d4d8;
  --fc-today-bg-color: rgba(59, 130, 246, 0.05);
  font-family: inherit;
  font-size: 0.75rem;
}

.dark .fc {
  --fc-border-color: #27272a;
  --fc-button-border-color: #27272a;
  --fc-button-hover-bg-color: #18181b;
  --fc-button-hover-border-color: #27272a;
  --fc-button-active-bg-color: #27272a;
  --fc-button-active-border-color: #3f3f46;
  --fc-today-bg-color: rgba(79, 70, 229, 0.1);
}

.fc .fc-toolbar-title {
  color: inherit;
  font-size: 0.875rem !important;
  font-weight: 650;
}

.fc .fc-button {
  border-radius: 4px !important;
  color: #3f3f46 !important;
  font-size: 0.75rem !important;
  font-weight: 500;
  padding: 0.375rem 0.75rem !important;
  text-transform: none;
}

.dark .fc .fc-button {
  color: #a1a1aa !important;
}

.fc .fc-button-primary:not(:disabled).fc-button-active,
.fc .fc-button-primary:not(:disabled):active {
  background-color: #f4f4f5 !important;
  border-color: #e4e4e7 !important;
  color: #18181b !important;
}

.dark .fc .fc-button-primary:not(:disabled).fc-button-active,
.dark .fc .fc-button-primary:not(:disabled):active {
  background-color: #27272a !important;
  border-color: #3f3f46 !important;
  color: #f4f4f5 !important;
}

.fc-theme-minimalist .fc-col-header-cell-cushion {
  color: #71717a;
  font-weight: 600;
  padding: 8px 4px !important;
}

.fc .fc-daygrid-day-number {
  color: #71717a;
  font-weight: 500;
  padding: 4px 6px !important;
}

.fc-event {
  border: none !important;
  border-radius: 4px !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  cursor: pointer;
  font-weight: 600;
  padding: 1px 4px !important;
}

.fc-event-teacher-task {
  border-left: 3px solid #312e81 !important;
}
</style>
