import request from '../request'

export interface MemoryPageOut {
  id: string
  user_id: string
  slug: string
  page_type: string
  title: string
  summary?: string | null
  body?: string | null
  category: string
  tags?: string[] | null
  confidence: number
  status: string
  version: number
  source_review_id?: string | null
  last_reviewed_at?: string | null
  expires_at?: string | null
  meta?: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface MemorySourceOut {
  id: string
  page_id: string
  user_id: string
  source_type: string
  source_id?: string | null
  occurred_at?: string | null
  snippet?: string | null
  confidence: number
  meta?: Record<string, any> | null
  created_at: string
}

export interface MemoryLinkOut {
  id: string
  user_id: string
  from_page_id: string
  to_page_id: string
  relation: string
  strength: number
  created_at: string
}

export interface MemoryEventOut {
  id: string
  user_id: string
  page_id?: string | null
  action: string
  before?: Record<string, any> | null
  after?: Record<string, any> | null
  reason?: string | null
  operator: string
  review_id?: string | null
  meta?: Record<string, any> | null
  created_at: string
}

export interface MemoryReviewTaskOut {
  id: string
  user_id: string
  page_id?: string | null
  task_type: string
  payload?: Record<string, any> | null
  status: string
  created_by: string
  handled_at?: string | null
  handled_by?: string | null
  handled_reason?: string | null
  created_at: string
  updated_at: string
}

export interface MemoryGraphOut {
  nodes: Array<{ id: string; title: string; page_type: string; category: string; confidence: number; status: string }>
  edges: Array<{ id: string; source: string; target: string; relation: string; strength: number }>
}

export interface MemoryLintIssue {
  issue_type: string
  page_id: string
  title: string
  message: string
  severity: string
}

export interface MemoryWikiStats {
  total_pages: number
  active_pages: number
  source_count: number
  link_count: number
  review_task_count: number
}

export interface MemoryPageDetail extends MemoryPageOut {
  sources: MemorySourceOut[]
  outbound_links: Array<Record<string, any>>
  inbound_links: Array<Record<string, any>>
}

export const memoryWikiApi = {
  listPages(params?: {
    page?: number
    page_size?: number
    page_type?: string
    category?: string
    status?: string
    keyword?: string
    student_id?: string
  }) {
    return request.get('/memory-wiki', { params })
  },

  getStats(params?: { student_id?: string }) {
    return request.get('/memory-wiki/stats', { params })
  },

  getGraph(params?: { student_id?: string }) {
    return request.get('/memory-wiki/graph', { params })
  },

  getEvents(params?: { page?: number; page_size?: number; student_id?: string }) {
    return request.get('/memory-wiki/events', { params })
  },

  listReviewTasks(params?: { status?: string; page?: number; page_size?: number; student_id?: string }) {
    return request.get('/memory-wiki/review-tasks', { params })
  },

  approveReviewTask(taskId: string, reason?: string) {
    return request.post(`/memory-wiki/review-tasks/${taskId}/approve`, { reason })
  },

  rejectReviewTask(taskId: string, reason?: string) {
    return request.post(`/memory-wiki/review-tasks/${taskId}/reject`, { reason })
  },

  runLint(params?: { student_id?: string }) {
    return request.post('/memory-wiki/lint', null, { params })
  },

  search(params: { query?: string; top_k?: number; page_type?: string; category?: string; status?: string }, studentId?: string) {
    return request.post('/memory-wiki/search', params, { params: studentId ? { student_id: studentId } : {} })
  },

  createPage(data: Partial<MemoryPageOut>) {
    return request.post('/memory-wiki/pages', data)
  },

  getPage(pageId: string, params?: { student_id?: string }) {
    return request.get(`/memory-wiki/pages/${pageId}`, { params })
  },

  updatePage(pageId: string, data: Partial<MemoryPageOut>) {
    return request.patch(`/memory-wiki/pages/${pageId}`, data)
  },

  archivePage(pageId: string) {
    return request.post(`/memory-wiki/pages/${pageId}/archive`)
  },

  deletePage(pageId: string) {
    return request.post(`/memory-wiki/pages/${pageId}/delete`)
  },

  listSources(pageId: string, params?: { student_id?: string }) {
    return request.get(`/memory-wiki/pages/${pageId}/sources`, { params })
  },

  addSource(pageId: string, data: Partial<MemorySourceOut>) {
    return request.post(`/memory-wiki/pages/${pageId}/sources`, data)
  },

  listLinks(pageId: string, params?: { student_id?: string }) {
    return request.get(`/memory-wiki/pages/${pageId}/links`, { params })
  },

  addLink(pageId: string, data: { to_page_id: string; relation: string; strength?: number }) {
    return request.post(`/memory-wiki/pages/${pageId}/links`, data)
  },
}