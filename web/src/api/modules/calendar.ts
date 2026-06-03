import request from '../request'

export interface CalendarEventData {
  title: string
  description?: string
  event_type?: string
  status?: string
  start_time: string
  end_time: string
  all_day?: boolean
  color?: string
  related_task_id?: string
  related_countdown_id?: string
  user_id?: string
}

export interface CalendarEventOut {
  id: string
  title: string
  description?: string
  event_type: string
  status: string
  start_time: string
  end_time: string
  all_day: boolean
  color?: string
  related_task_id?: string
  related_countdown_id?: string
  user_id: string
  created_by: string
  created_at: string
  updated_at: string
}

export const calendarApi = {
  listEvents(params: { start_time: string; end_time: string }) {
    return request.get('/calendar/', { params })
  },

  createEvent(data: CalendarEventData) {
    return request.post('/calendar/', data)
  },

  updateEvent(id: string, data: Partial<CalendarEventData>) {
    return request.put(`/calendar/${id}`, data)
  },

  deleteEvent(id: string) {
    return request.delete(`/calendar/${id}`)
  }
}
