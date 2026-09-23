import request from '../request'

export interface AssessmentPaper {
  id: string
  title: string
  description?: string | null
  source_file_id?: string | null
  parse_status: string
  parse_progress?: Record<string, any> | null
  parse_error?: string | null
  question_count: number
  total_score: number
  publish_target?: Record<string, any> | null
  publish_at?: string | null
  published_at?: string | null
  created_at: string
  updated_at: string
}

export interface AssessmentQuestion {
  id: string
  paper_id: string
  order_index: number
  question_type: string
  stem: string
  stem_images?: any[] | null
  options?: any[] | null
  answer?: any
  analysis?: string | null
  score: number
  difficulty?: number | null
  tags?: string[] | null
  source_chunk?: any
  created_at: string
  updated_at: string
}

export interface ParseStatus {
  parse_status: string
  parse_progress?: Record<string, any> | null
  parse_error?: string | null
  question_count: number
  total_score: number
}

export interface StudentPaper {
  id: string
  title: string
  description?: string | null
  question_count: number
  total_score: number
  published_at?: string | null
  due_at?: string | null
  attempt_id?: string | null
  attempt_status?: string | null
  attempt_score?: number | null
}

export interface StudentQuestion {
  id: string
  order_index: number
  question_type: string
  stem: string
  stem_images?: any[] | null
  options?: any[] | null
  score: number
}

export interface StudentAttempt {
  id: string
  paper_id: string
  status: string
  started_at?: string | null
  submitted_at?: string | null
  score?: number | null
  duration_seconds?: number | null
}

export interface StudentAnswerIn {
  question_id: string
  answer?: any
}

export interface BehaviorEventPayload {
  event_type: string
  payload?: Record<string, any>
  occurred_at?: string
}

export interface AttemptMonitor {
  id: string
  student_id: string
  student_name: string
  username: string
  status: string
  started_at?: string | null
  submitted_at?: string | null
  duration_seconds?: number | null
  score?: number | null
  suspicious: boolean
  event_count: number
  flagged_count: number
}

export interface BehaviorEventOut {
  id: string
  event_type: string
  payload?: Record<string, any> | null
  occurred_at?: string | null
}

export const assessmentApi = {
  uploadFile(file: File, source = 'assessment_upload') {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/files/upload?source=${source}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  createPaper(data: { file_id: string; title: string; description?: string }) {
    return request.post('/assessment/papers', data)
  },

  listPapers() {
    return request.get('/assessment/papers')
  },

  getPaper(id: string) {
    return request.get(`/assessment/papers/${id}`)
  },

  getParseStatus(id: string) {
    return request.get(`/assessment/papers/${id}/parse-status`)
  },

  listQuestions(id: string) {
    return request.get(`/assessment/papers/${id}/questions`)
  },

  saveQuestions(id: string, questions: any[]) {
    return request.put(`/assessment/papers/${id}/questions`, { questions })
  },

  publishPaper(
    id: string,
    data: {
      publish_target: Record<string, any>
      publish_at?: string | null
      due_at?: string | null
    }
  ) {
    return request.post(`/assessment/papers/${id}/publish`, data)
  },

  listStudentPapers() {
    return request.get('/assessment/student/papers')
  },

  getStudentQuestions(paperId: string) {
    return request.get(`/assessment/student/papers/${paperId}/questions`)
  },

  startAttempt(paperId: string) {
    return request.post(`/assessment/student/papers/${paperId}/attempts`)
  },

  saveAnswers(attemptId: string, answers: StudentAnswerIn[]) {
    return request.put(`/assessment/student/attempts/${attemptId}/answers`, { answers })
  },

  submitAttempt(attemptId: string, answers: StudentAnswerIn[]) {
    return request.post(`/assessment/student/attempts/${attemptId}/submit`, { answers })
  },

  reportBehavior(data: {
    session_id: string
    attempt_id?: string | null
    events: BehaviorEventPayload[]
  }) {
    return request.post('/assessment/student/behavior/batch', data)
  },

  listPaperAttempts(paperId: string) {
    return request.get(`/assessment/papers/${paperId}/attempts`)
  },

  listAttemptBehavior(attemptId: string) {
    return request.get(`/assessment/attempts/${attemptId}/behavior`)
  }
}