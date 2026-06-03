import request from '../request'

export interface StudentMemoryOut {
  id: string
  memory_type: 'short_term' | 'long_term'
  category: string
  content: string
  evidence?: string
  confidence: number
  status: string
  source_review_id?: string
  created_at: string
  updated_at: string
}

export interface StudentMemoryGroupedOut {
  student_id: string
  short_term: StudentMemoryOut[]
  long_term: StudentMemoryOut[]
  last_updated_at?: string
}

export interface DailyReviewOut {
  id: string
  student_id: string
  date: string
  summary?: string
  study_time_minutes: number
  metrics?: any
  highlights: string[]
  concerns: string[]
  suggestions: string[]
  new_memories: any[]
  generated_at: string
}

export const memoryApi = {
  getStudentMemory(studentId: string, params?: { layer?: string }) {
    return request.get(`/ai/memory/${studentId}`, { params })
  },

  deleteStudentMemory(studentId: string, memoryId: string, reason?: string) {
    return request.delete(`/ai/memory/${studentId}/${memoryId}`, { data: { reason } })
  },

  getMemoryUpdateLogs(studentId: string, params?: { page?: number; page_size?: number; start_date?: string; end_date?: string }) {
    return request.get(`/ai/memory/${studentId}/update-logs`, { params })
  },

  getDailyReview(date: string, params?: { student_id?: string }) {
    return request.get(`/reviews/${date}`, { params })
  },

  listDailyReviews(params?: { page?: number; page_size?: number; student_id?: string; start_date?: string; end_date?: string }) {
    return request.get('/reviews', { params })
  },

  generateDailyReview(data: { student_id: string; date: string }) {
    return request.post('/reviews/generate', data)
  }
}
