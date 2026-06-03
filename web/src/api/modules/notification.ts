import request from '../request'

export interface NotificationOut {
  id: string
  title: string
  content: string
  notification_type: string
  link_url?: string
  user_id: string
  read_at?: string
  created_at: string
}

export const notificationApi = {
  listNotifications(params?: { unread_only?: boolean }) {
    return request.get('/notifications/', { params })
  },

  markAsRead(id: string) {
    return request.post(`/notifications/${id}/read`)
  },

  markAllAsRead() {
    return request.post('/notifications/read-all')
  }
}
