import request from '../request'

export interface TaskCreateData {
  title: string
  description?: string
  priority?: string
  start_date?: string
  due_date?: string
  assignee_ids: string[]
  attachment_ids?: string[]
}

export interface TaskSubmissionData {
  content?: string
  attachment_ids?: string[]
}

export interface TaskReviewData {
  status: 'completed' | 'rejected'
  feedback?: string
}

export interface StudentTask {
  id: string
  title: string
  description?: string
  priority: string
  due_date?: string
  status: 'in_progress' | 'submitted' | 'completed' | 'rejected'
  completed_at?: string
  attachment_ids?: string[]
}

export interface TaskOut {
  id: string
  title: string
  description?: string
  priority: string
  status: string
  start_date?: string
  due_date?: string
  attachment_ids?: string[]
  creator_id: string
  created_at: string
  updated_at: string
}

export interface TaskSubmissionOut {
  id: string
  task_id: string
  assignee_id: string
  user_id: string
  content?: string
  attachment_ids?: string[]
  feedback?: string
  reviewed_by?: string
  reviewed_at?: string
  created_at: string
  username?: string
  nickname?: string
}

export interface TaskDetails {
  task: TaskOut
  assignees: {
    id: string
    user_id: string
    username: string
    nickname?: string
    status: string
    assigned_at?: string
    completed_at?: string
  }[]
  submissions: TaskSubmissionOut[]
}

export const taskApi = {
  // Student APIs
  listMyTasks() {
    return request.get('/tasks/student')
  },

  submitTask(taskId: string, data: TaskSubmissionData) {
    return request.post(`/tasks/${taskId}/submit`, data)
  },

  // Teacher/Staff APIs
  createTask(data: TaskCreateData) {
    return request.post('/tasks/', data)
  },

  reviewSubmission(submissionId: string, data: TaskReviewData) {
    return request.post(`/tasks/submissions/${submissionId}/review`, data)
  },

  listTeacherTasks() {
    return request.get('/tasks/')
  },

  getTaskDetails(taskId: string) {
    return request.get(`/tasks/${taskId}`)
  }
}
