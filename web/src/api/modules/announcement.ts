import request from '../request'

export interface AnnouncementData {
  title: string
  content: string
  announcement_type: string
  target_roles?: string[]
}

export interface Announcement {
  id: string
  title: string
  content: string
  announcement_type: string
  target_roles: string[]
  creator_id: string
  created_at: string
  read_at?: string
}

export const announcementApi = {
  listAnnouncements() {
    return request.get('/announcements/')
  },

  createAnnouncement(data: AnnouncementData) {
    return request.post('/announcements/', data)
  },

  markAsRead(announcementId: string) {
    return request.post(`/announcements/${announcementId}/read`)
  }
}
