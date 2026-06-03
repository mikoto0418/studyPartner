import request from '../request'

export interface DailyReviewListOut {
  id: string
  date: string
  study_time_minutes: number
  summary_preview: string
  concern_count: number
  generated_at: string
}

export interface DailyReviewOut {
  id: string
  student_id: string
  date: string
  summary: string
  study_time_minutes: number
  metrics?: Record<string, any>
  highlights: string[]
  concerns: string[]
  suggestions: string[]
  new_memories: string[]
  generated_at: string
}

export const reviewsApi = {
  listReviews(params?: {
    student_id?: string
    start_date?: string
    end_date?: string
    page?: number
    page_size?: number
  }) {
    return request.get('/reviews', { params })
  },

  getReview(dateVal: string, params?: { student_id?: string }) {
    return request.get(`/reviews/${dateVal}`, { params })
  },

  generateReview(data: { student_id: string; date: string }) {
    return request.post('/reviews/generate', data)
  }
}
