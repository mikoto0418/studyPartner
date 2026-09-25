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
  /** 有题目未设置分值时整卷满分为未知，后端返回 null */
  total_score?: number | null
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
  /** null = 原文没标分值、教师尚未填写 */
  score?: number | null
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
  total_score?: number | null
}

export interface StudentPaper {
  id: string
  title: string
  description?: string | null
  question_count: number
  total_score?: number | null
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
  /** null = 该题尚未设置分值 */
  score?: number | null
}

export interface StudentAttempt {
  id: string
  paper_id: string
  status: string
  started_at?: string | null
  submitted_at?: string | null
  score?: number | null
  duration_seconds?: number | null
  /** 交卷时超过截止宽限期，本次提交的答案未落库 */
  answers_ignored?: boolean
}

export interface StudentAnswerIn {
  question_id: string
  answer?: any
}

export interface StudentAnswerOut {
  question_id: string
  answer?: any
}

export interface StudentAnswersOut {
  attempt_id?: string | null
  status?: string | null
  answers: StudentAnswerOut[]
}

export interface BehaviorEventPayload {
  event_type: string
  payload?: Record<string, any>
  occurred_at?: string
}

export interface AttemptAnswer {
  question_id: string
  order_index: number
  question_type: string
  stem: string
  options?: any[] | null
  reference_answer?: any
  /** null = 题目未设置分值，批改页应禁用打分输入 */
  max_score?: number | null
  answer?: any
  score: number
  graded: boolean
  is_correct?: boolean | null
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
  pending_grade_count: number
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

  reparsePaper(id: string) {
    return request.post(`/assessment/papers/${id}/reparse`)
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

  getStudentAnswers(paperId: string) {
    return request.get(`/assessment/student/papers/${paperId}/answers`)
  },

  saveAnswers(attemptId: string, answers: StudentAnswerIn[]) {
    // 违规超限时后端会强制交卷，并在 data 里回传 attempt，前端据此切到已交卷态
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
  },

  listAttemptAnswers(attemptId: string) {
    return request.get(`/assessment/attempts/${attemptId}/answers`)
  },

  gradeAttempt(attemptId: string, grades: { question_id: string; score: number }[]) {
    return request.post(`/assessment/attempts/${attemptId}/grade`, { grades })
  }
}