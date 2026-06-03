<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import { calendarApi } from '../../api/modules/calendar'
import type { CalendarEventOut, CalendarEventData } from '../../api/modules/calendar'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Trash2, Edit } from 'lucide-vue-next'

// Data refs
const events = ref<CalendarEventOut[]>([])
const isDialogOpen = ref(false)
const isDetailOpen = ref(false)
const selectedEvent = ref<CalendarEventOut | null>(null)

// Form state
const eventForm = ref({
  id: '',
  title: '',
  description: '',
  event_type: 'personal',
  status: 'planned',
  start_time: '',
  end_time: '',
  all_day: false,
  color: '#3b82f6' // Default blue
})

// Options
const eventTypes = [
  { label: '个人日程', value: 'personal' },
  { label: '学习任务', value: 'task' },
  { label: '倒数纪念', value: 'countdown' }
]

const eventStatuses = [
  { label: '计划中', value: 'planned' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' }
]

const colors = [
  { name: '天空蓝', value: '#3b82f6' },
  { name: '薄荷绿', value: '#10b981' },
  { name: '温暖黄', value: '#f59e0b' },
  { name: '优雅灰', value: '#6b7280' }
]

// Current range loaded to prevent duplicate fetches
const currentRange = ref({ start: '', end: '' })

// FullCalendar Options
const calendarOptions = computed(() => ({
  plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
  initialView: 'dayGridMonth',
  headerToolbar: {
    left: 'prev,next today',
    center: 'title',
    right: 'dayGridMonth,timeGridWeek,timeGridDay'
  },
  buttonText: {
    today: '今天',
    month: '月',
    week: '周',
    day: '日'
  },
  locale: 'zh-cn',
  firstDay: 1,
  editable: true,
  selectable: true,
  events: events.value.map(e => ({
    id: e.id,
    title: e.title,
    start: e.start_time,
    end: e.end_time,
    allDay: e.all_day,
    color: e.color || '#3b82f6',
    extendedProps: {
      description: e.description,
      event_type: e.event_type,
      status: e.status
    }
  })),
  datesSet: (info: { startStr: string; endStr: string }) => {
    currentRange.value = {
      start: info.startStr,
      end: info.endStr
    }
    fetchEvents()
  },
  select: (info: { startStr: string; endStr: string; allDay: boolean }) => {
    // Format to local ISO without offset issues
    const formatLocal = (dateStr: string) => {
      const d = new Date(dateStr)
      return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
    }

    eventForm.value = {
      id: '',
      title: '',
      description: '',
      event_type: 'personal',
      status: 'planned',
      start_time: formatLocal(info.startStr),
      end_time: formatLocal(info.endStr),
      all_day: info.allDay,
      color: '#3b82f6'
    }
    isDialogOpen.value = true
  },
  eventClick: (info: { event: { id: string } }) => {
    const matched = events.value.find(e => e.id === info.event.id)
    if (matched) {
      selectedEvent.value = matched
      isDetailOpen.value = true
    }
  }
}))

// Fetch calendar events
const fetchEvents = async () => {
  if (!currentRange.value.start || !currentRange.value.end) return
  try {
    const res = await calendarApi.listEvents({
      start_time: currentRange.value.start,
      end_time: currentRange.value.end
    })
    events.value = res.data || []
  } catch (error) {
    console.warn("Failed to fetch events from backend. Using mock data.")
    // Mock database entries
    events.value = [
      {
        id: '1',
        title: '编译原理大作业提交',
        description: '提交第一阶段AST抽象语法树构建代码',
        event_type: 'task',
        status: 'planned',
        start_time: new Date(Date.now() + 86400000 * 2).toISOString(),
        end_time: new Date(Date.now() + 86400000 * 2 + 3600000 * 2).toISOString(),
        all_day: false,
        color: '#f59e0b',
        user_id: 'user-uuid',
        created_by: 'user-uuid',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      },
      {
        id: '2',
        title: '每日英语听力训练',
        description: '听写一期 BBC Learning English',
        event_type: 'personal',
        status: 'completed',
        start_time: new Date().toISOString().split('T')[0] + 'T09:00:00',
        end_time: new Date().toISOString().split('T')[0] + 'T10:00:00',
        all_day: false,
        color: '#10b981',
        user_id: 'user-uuid',
        created_by: 'user-uuid',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
    ]
  }
}

// Save event (create/update)
const handleSaveEvent = async () => {
  if (!eventForm.value.title.trim()) {
    ElMessage.warning('请输入日程标题')
    return
  }

  const payload: CalendarEventData = {
    title: eventForm.value.title,
    description: eventForm.value.description,
    event_type: eventForm.value.event_type,
    status: eventForm.value.status,
    start_time: new Date(eventForm.value.start_time).toISOString(),
    end_time: new Date(eventForm.value.end_time).toISOString(),
    all_day: eventForm.value.all_day,
    color: eventForm.value.color
  }

  try {
    if (eventForm.value.id) {
      await calendarApi.updateEvent(eventForm.value.id, payload)
      ElMessage.success('更新日程成功')
    } else {
      await calendarApi.createEvent(payload)
      ElMessage.success('创建日程成功')
    }
    isDialogOpen.value = false
    fetchEvents()
  } catch (error) {
    // Optimistic fallback for mock preview
    if (!eventForm.value.id) {
      const mockEvent: CalendarEventOut = {
        id: Date.now().toString(),
        title: eventForm.value.title,
        description: eventForm.value.description,
        event_type: eventForm.value.event_type,
        status: eventForm.value.status,
        start_time: payload.start_time,
        end_time: payload.end_time,
        all_day: eventForm.value.all_day,
        color: eventForm.value.color,
        user_id: 'mock',
        created_by: 'mock',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      }
      events.value.push(mockEvent)
    } else {
      const matched = events.value.find(e => e.id === eventForm.value.id)
      if (matched) {
        Object.assign(matched, {
          title: eventForm.value.title,
          description: eventForm.value.description,
          event_type: eventForm.value.event_type,
          status: eventForm.value.status,
          start_time: payload.start_time,
          end_time: payload.end_time,
          all_day: eventForm.value.all_day,
          color: eventForm.value.color
        })
      }
    }
    isDialogOpen.value = false
    ElMessage.success('日程保存成功 (本地缓存)')
  }
}

// Edit existing event
const handleEditSelected = () => {
  if (!selectedEvent.value) return
  const e = selectedEvent.value
  
  const formatLocal = (dateStr: string) => {
    const d = new Date(dateStr)
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }

  eventForm.value = {
    id: e.id,
    title: e.title,
    description: e.description || '',
    event_type: e.event_type,
    status: e.status,
    start_time: formatLocal(e.start_time),
    end_time: formatLocal(e.end_time),
    all_day: e.all_day,
    color: e.color || '#3b82f6'
  }
  isDetailOpen.value = false
  isDialogOpen.value = true
}

// Delete event
const handleDeleteSelected = async () => {
  if (!selectedEvent.value) return
  
  try {
    await ElMessageBox.confirm('确定要删除该日程吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    try {
      await calendarApi.deleteEvent(selectedEvent.value.id)
      ElMessage.success('删除日程成功')
    } catch (e) {
      // Mock delete
      events.value = events.value.filter(item => item.id !== selectedEvent.value?.id)
      ElMessage.success('删除成功 (本地缓存)')
    }
    
    isDetailOpen.value = false
    selectedEvent.value = null
    fetchEvents()
  } catch (cancel) {
    // Cancelled delete
  }
}

// Helper formats
const formatDate = (isoStr: string) => {
  const d = new Date(isoStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  // If datesSet doesn't fire immediately, fetch default
  if (!currentRange.value.start) {
    const now = new Date()
    const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString()
    const end = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString()
    currentRange.value = { start, end }
    fetchEvents()
  }
})
</script>

<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 h-[calc(100vh-8rem)]">
    <!-- Left Calendar Section -->
    <div class="lg:col-span-9 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-lg p-6 flex flex-col min-h-0 shadow-sm">
      <div class="flex-1 min-h-0">
        <FullCalendar :options="calendarOptions" class="h-full fc-theme-minimalist" />
      </div>
    </div>

    <!-- Right Task/Notice List -->
    <div class="lg:col-span-3 flex flex-col space-y-6">
      <!-- Fast actions -->
      <button
        @click="() => {
          eventForm = { id: '', title: '', description: '', event_type: 'personal', status: 'planned', start_time: new Date().toISOString().slice(0, 16), end_time: new Date(Date.now() + 3600000).toISOString().slice(0, 16), all_day: false, color: '#3b82f6' }
          isDialogOpen = true
        }"
        class="w-full flex items-center justify-center space-x-2 py-2.5 px-4 bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-xs rounded transition-all shadow-sm"
      >
        <Plus class="w-4 h-4" />
        <span>添加日程计划</span>
      </button>

      <!-- Calendar event list card -->
      <div class="flex-1 bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-lg p-5 flex flex-col min-h-0 shadow-sm">
        <div class="flex items-center space-x-2 mb-4">
          <span class="text-xs font-semibold text-gray-500 dark:text-zinc-400">即将到来的日程</span>
          <span class="px-1.5 py-0.5 text-[10px] font-medium bg-gray-100 dark:bg-zinc-800 rounded text-gray-600 dark:text-zinc-400">
            {{ events.length }}
          </span>
        </div>

        <div class="flex-1 overflow-y-auto space-y-3 pr-1">
          <div
            v-for="item in events"
            :key="item.id"
            @click="() => { selectedEvent = item; isDetailOpen = true }"
            class="p-3 border border-gray-100 dark:border-zinc-800 hover:border-gray-200 dark:hover:border-zinc-700 rounded cursor-pointer transition-all bg-gray-50/50 dark:bg-zinc-900/50 hover:bg-white dark:hover:bg-zinc-800/40 relative overflow-hidden group"
          >
            <!-- Colored tag strip -->
            <div class="absolute left-0 top-0 bottom-0 w-1" :style="{ backgroundColor: item.color || '#3b82f6' }"></div>
            
            <div class="pl-2 space-y-1">
              <div class="flex justify-between items-start">
                <h4 class="text-xs font-medium text-gray-900 dark:text-zinc-100 line-clamp-1">
                  {{ item.title }}
                </h4>
                <span
                  class="text-[9px] px-1 rounded flex-shrink-0 font-medium"
                  :class="{
                    'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400': item.event_type === 'personal',
                    'bg-amber-50 text-amber-600 dark:bg-amber-950/20 dark:text-amber-400': item.event_type === 'task',
                    'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-400': item.event_type === 'countdown'
                  }"
                >
                  {{ item.event_type === 'personal' ? '个人' : item.event_type === 'task' ? '任务' : '倒数' }}
                </span>
              </div>
              
              <p v-if="item.description" class="text-[10px] text-gray-400 dark:text-zinc-500 line-clamp-1">
                {{ item.description }}
              </p>
              
              <div class="text-[9px] text-gray-400 dark:text-zinc-500 font-medium">
                {{ formatDate(item.start_time) }}
              </div>
            </div>
          </div>

          <div v-if="events.length === 0" class="h-40 flex flex-col items-center justify-center text-center space-y-2">
            <span class="text-xs text-gray-400 dark:text-zinc-500">近期无日程安排</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Update Dialog -->
    <el-dialog
      v-model="isDialogOpen"
      :title="eventForm.id ? '编辑日程' : '创建新日程'"
      width="460px"
      destroy-on-close
      class="minimal-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">日程标题</label>
          <input
            v-model="eventForm.title"
            placeholder="输入日程名称"
            type="text"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
          />
        </div>

        <div>
          <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">日程详情</label>
          <textarea
            v-model="eventForm.description"
            placeholder="日程备忘录、备注或说明"
            rows="3"
            class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors resize-none"
          ></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">分类类型</label>
            <select
              v-model="eventForm.event_type"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-white dark:bg-zinc-900 focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            >
              <option v-for="t in eventTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>

          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">状态</label>
            <select
              v-model="eventForm.status"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-white dark:bg-zinc-900 focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            >
              <option v-for="s in eventStatuses" :key="s.value" :value="s.value">{{ s.label }}</option>
            </select>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">开始时间</label>
            <input
              type="datetime-local"
              v-model="eventForm.start_time"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            />
          </div>

          <div>
            <label class="block text-[11px] font-medium text-gray-400 dark:text-zinc-500 mb-1">结束时间</label>
            <input
              type="datetime-local"
              v-model="eventForm.end_time"
              class="w-full px-3 py-2 text-xs border border-gray-200 dark:border-zinc-800 rounded bg-transparent focus:outline-none focus:border-gray-900 dark:focus:border-zinc-100 transition-colors"
            />
          </div>
        </div>

        <div class="flex justify-between items-center py-1">
          <div class="flex items-center space-x-2">
            <input
              id="all_day_toggle"
              type="checkbox"
              v-model="eventForm.all_day"
              class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label for="all_day_toggle" class="text-xs text-gray-600 dark:text-zinc-400 select-none">全天日程</label>
          </div>

          <div class="flex items-center space-x-2">
            <span class="text-[11px] text-gray-400 dark:text-zinc-500">标签颜色</span>
            <div class="flex space-x-1.5">
              <button
                v-for="color in colors"
                :key="color.value"
                @click="eventForm.color = color.value"
                class="w-4 h-4 rounded-full border transition-transform"
                :class="[
                  eventForm.color === color.value ? 'scale-110 border-gray-900 dark:border-zinc-100' : 'border-transparent'
                ]"
                :style="{ backgroundColor: color.value }"
              ></button>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end space-x-3 pt-2">
          <button
            @click="isDialogOpen = false"
            class="px-4 py-1.5 text-xs border border-gray-200 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800 rounded transition-colors"
          >
            取消
          </button>
          <button
            @click="handleSaveEvent"
            class="px-4 py-1.5 text-xs bg-gray-900 hover:bg-gray-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium rounded transition-colors"
          >
            保存
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- Detail View Dialog -->
    <el-dialog
      v-model="isDetailOpen"
      title="日程详情"
      width="400px"
      class="minimal-dialog"
    >
      <div v-if="selectedEvent" class="space-y-4">
        <div>
          <div class="flex items-center space-x-2">
            <span class="w-2.5 h-2.5 rounded-full" :style="{ backgroundColor: selectedEvent.color || '#3b82f6' }"></span>
            <h3 class="text-sm font-semibold text-gray-900 dark:text-zinc-50">{{ selectedEvent.title }}</h3>
          </div>
          <div class="mt-1 flex items-center space-x-2">
            <span
              class="text-[9px] px-1.5 py-0.5 rounded font-medium"
              :class="{
                'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400': selectedEvent.event_type === 'personal',
                'bg-amber-50 text-amber-600 dark:bg-amber-950/20 dark:text-amber-400': selectedEvent.event_type === 'task',
                'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-400': selectedEvent.event_type === 'countdown'
              }"
            >
              {{ selectedEvent.event_type === 'personal' ? '个人日程' : selectedEvent.event_type === 'task' ? '教学任务' : '倒数纪念' }}
            </span>

            <span
              class="text-[9px] px-1.5 py-0.5 rounded font-medium"
              :class="{
                'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400': selectedEvent.status === 'planned',
                'bg-blue-50 text-blue-600 dark:bg-blue-950/20 dark:text-blue-400': selectedEvent.status === 'in_progress',
                'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/20 dark:text-emerald-400': selectedEvent.status === 'completed',
                'bg-red-50 text-red-600 dark:bg-red-950/20 dark:text-red-400': selectedEvent.status === 'cancelled'
              }"
            >
              {{ selectedEvent.status === 'planned' ? '计划中' : selectedEvent.status === 'in_progress' ? '进行中' : selectedEvent.status === 'completed' ? '已完成' : '已取消' }}
            </span>
          </div>
        </div>

        <div v-if="selectedEvent.description" class="py-2 border-t border-b border-gray-100 dark:border-zinc-800">
          <p class="text-xs text-gray-600 dark:text-zinc-300 whitespace-pre-wrap">{{ selectedEvent.description }}</p>
        </div>

        <div class="space-y-1.5 text-xs text-gray-500">
          <div class="flex justify-between">
            <span>开始时间</span>
            <span class="font-medium text-gray-700 dark:text-zinc-300">{{ formatDate(selectedEvent.start_time) }}</span>
          </div>
          <div class="flex justify-between">
            <span>结束时间</span>
            <span class="font-medium text-gray-700 dark:text-zinc-300">{{ formatDate(selectedEvent.end_time) }}</span>
          </div>
          <div class="flex justify-between" v-if="selectedEvent.all_day">
            <span>全天日程</span>
            <span class="font-medium text-gray-700 dark:text-zinc-300">是</span>
          </div>
        </div>

        <div class="flex justify-end space-x-2 pt-4 border-t border-gray-100 dark:border-zinc-800">
          <button
            @click="handleDeleteSelected"
            class="flex items-center space-x-1 px-3 py-1.5 text-xs border border-red-200 text-red-600 hover:bg-red-50 rounded transition-colors"
          >
            <Trash2 class="w-3.5 h-3.5" />
            <span>删除</span>
          </button>
          
          <button
            @click="handleEditSelected"
            class="flex items-center space-x-1 px-3 py-1.5 text-xs border border-gray-200 dark:border-zinc-800 hover:bg-gray-50 dark:hover:bg-zinc-800 text-gray-700 dark:text-zinc-300 rounded transition-colors"
          >
            <Edit class="w-3.5 h-3.5" />
            <span>修改</span>
          </button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style>
/* FullCalendar Minimalist UI Styles overriding default theme variables */
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
  --fc-today-bg-color: rgba(59, 130, 246, 0.1);
}

.fc .fc-toolbar-title {
  font-size: 0.875rem !important;
  font-weight: 600;
  color: inherit;
}

.fc .fc-button {
  font-size: 0.75rem !important;
  padding: 0.375rem 0.75rem !important;
  border-radius: 4px !important;
  text-transform: none;
  font-weight: 500;
  color: #3f3f46 !important;
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
  padding: 8px 4px !important;
  font-weight: 600;
  color: #71717a;
}

.dark .fc-theme-minimalist .fc-col-header-cell-cushion {
  color: #a1a1aa;
}

.fc .fc-daygrid-day-number {
  padding: 4px 6px !important;
  font-weight: 500;
  color: #71717a;
}

.dark .fc .fc-daygrid-day-number {
  color: #a1a1aa;
}

.fc .fc-daygrid-day.fc-day-today .fc-daygrid-day-number {
  color: #2563eb;
  font-weight: 700;
}

.fc-event {
  border-radius: 3px !important;
  padding: 1px 4px !important;
  font-weight: 500;
  cursor: pointer;
  border: none !important;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
</style>
