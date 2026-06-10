import request from '../request'

export interface ClassMemberOut {
  id: string
  user_id: string
  username?: string
  nickname?: string
  display_name?: string
  status: string
  joined_at?: string
}

export interface ClassOut {
  id: string
  teacher_id: string
  name: string
  description?: string
  grade?: string
  subject?: string
  status: string
  created_at: string
  member_count: number
  members: ClassMemberOut[]
}

export interface LearningPathResource {
  id?: string
  task_id?: string
  node_id?: string
  resource_type: 'bilibili' | 'file' | 'link' | 'text' | string
  title?: string
  url?: string
  bv_id?: string
  file_id?: string
  metadata?: Record<string, any>
}

export interface LearningPathNode {
  id?: string
  task_id?: string
  stage_id?: string
  key?: string
  title: string
  description?: string
  node_type: 'learning' | 'video' | 'reading' | 'practice' | 'submission' | 'checkpoint' | string
  order_index: number
  estimated_minutes: number
  required: boolean
  config?: Record<string, any>
  resources: LearningPathResource[]
  progress?: {
    id: string
    status: string
    score?: number
    started_at?: string
    submitted_at?: string
    completed_at?: string
  }
}

export interface LearningPathStage {
  id?: string
  task_id?: string
  title: string
  description?: string
  order_index: number
}

export interface LearningPathEdge {
  id?: string
  task_id?: string
  source_node_id?: string
  target_node_id?: string
  source_key: string
  target_key: string
}

export interface LearningPathTaskOut {
  id: string
  creator_id: string
  class_id?: string
  title: string
  goal: string
  planning_text?: string
  description?: string
  status: string
  due_date?: string
  published_at?: string
  created_at: string
  updated_at: string
  assignee_count: number
  avg_progress: number
}

export interface LearningPathPlanOut {
  stages: LearningPathStage[]
  nodes: LearningPathNode[]
  edges: LearningPathEdge[]
  resources: LearningPathResource[]
  summary: string
}

export interface LearningPathDetailOut {
  task: LearningPathTaskOut
  stages: LearningPathStage[]
  nodes: LearningPathNode[]
  edges: LearningPathEdge[]
  assignees: Array<Record<string, any>>
  submissions: Array<Record<string, any>>
}

export interface ClassOverviewOut {
  class_info: ClassOut
  metrics: Record<string, any>
  trend: Array<Record<string, any>>
  memory_summary: Record<string, any>
  insights: LearningInsightOut[]
  attention_students: Array<Record<string, any>>
  recent_paths: LearningPathTaskOut[]
}

export interface InsightEvidenceOut {
  source_type: string
  source_id?: string
  student_id?: string
  student_name?: string
  content: string
  occurred_at?: string
}

export interface InsightActionOut {
  action_type: string
  label: string
  payload: Record<string, any>
}

export interface LearningInsightOut {
  id: string
  scope: string
  class_id?: string
  student_id?: string
  teacher_id?: string
  title: string
  insight_type: string
  severity: 'low' | 'medium' | 'high' | string
  summary: string
  affected_student_ids: string[]
  evidence: InsightEvidenceOut[]
  suggested_actions: InsightActionOut[]
  status: 'new' | 'acknowledged' | 'resolved' | 'dismissed' | string
  source: string
  source_fingerprint?: string
  generated_at?: string
  created_at: string
  updated_at: string
}

export interface StudentGrowthOverviewOut {
  student_id: string
  profile: Record<string, any>
  metrics: Record<string, any>
  trend: Array<Record<string, any>>
  learning_paths: LearningPathTaskOut[]
  memory_cards: Array<Record<string, any>>
  parent_summary: string
}

export const learningPathApi = {
  generatePlan(data: { title?: string; goal: string; planning_text: string }) {
    return request.post('/learning-paths/generate', data)
  },

  createPath(data: {
    title: string
    goal: string
    planning_text?: string
    description?: string
    class_id?: string
    assignee_ids?: string[]
    due_date?: string
    publish?: boolean
    stages?: LearningPathStage[]
    nodes?: LearningPathNode[]
    edges?: LearningPathEdge[]
  }) {
    return request.post('/learning-paths/', data)
  },

  updatePath(taskId: string, data: Partial<{
    title: string
    goal: string
    planning_text: string
    description: string
    status: string
    due_date: string
    stages: LearningPathStage[]
    nodes: LearningPathNode[]
    edges: LearningPathEdge[]
  }>) {
    return request.put(`/learning-paths/${taskId}`, data)
  },

  listTeacherPaths() {
    return request.get('/learning-paths/')
  },

  listStudentPaths() {
    return request.get('/learning-paths/student')
  },

  getPathDetail(taskId: string) {
    return request.get(`/learning-paths/${taskId}`)
  },

  submitNode(taskId: string, nodeId: string, data: { content?: string; attachment_ids?: string[]; mark_complete?: boolean }) {
    return request.post(`/learning-paths/${taskId}/nodes/${nodeId}/submit`, data)
  },

  reviewSubmission(submissionId: string, data: {
    review_status: 'approved' | 'rejected' | 'revise'
    score?: number
    feedback?: string
    follow_up?: string
    reopen_until?: string
  }) {
    return request.post(`/learning-paths/submissions/${submissionId}/review`, data)
  },

  createClass(data: { name: string; description?: string; grade?: string; subject?: string; student_ids?: string[] }) {
    return request.post('/learning-paths/classes', data)
  },

  listClasses() {
    return request.get('/learning-paths/classes/list')
  },

  getClassOverview(classId: string) {
    return request.get(`/learning-paths/classes/${classId}/overview`)
  },

  updateInsightStatus(insightId: string, status: 'new' | 'acknowledged' | 'resolved' | 'dismissed') {
    return request.patch(`/learning-paths/insights/${insightId}/status`, { status })
  },

  getStudentGrowth(studentId: string) {
    return request.get(`/learning-paths/growth/${studentId}`)
  }
}
