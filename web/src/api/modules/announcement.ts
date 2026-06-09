import request from '../request'

export interface AnnouncementData {
  title: string
  content: string
  status?: 'draft' | 'published' | 'expired' | 'withdrawn'
  target_type: 'all' | 'all_students' | 'all_teachers' | 'specific_users'
  is_pinned?: boolean
  publish_at?: string
  expire_at?: string
  receiver_ids?: string[]
}

export interface Announcement {
  id: string
  title: string
  content: string
  status: string
  target_type: string
  is_pinned: boolean
  publish_at?: string
  expire_at?: string
  creator_id: string
  created_at: string
  updated_at: string
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
