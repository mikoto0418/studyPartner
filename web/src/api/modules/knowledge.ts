import request from '../request'

export interface KnowledgeDocumentOut {
  id: string
  file_id: string
  uploader_id: string
  title: string
  description?: string
  category?: string
  tags?: string[]
  visibility: 'public' | 'teachers_only' | 'private'
  process_status: 'pending' | 'parsing' | 'chunking' | 'embedding' | 'completed' | 'failed'
  chunk_count: number
  summary?: string
  process_error?: string
  processed_at?: string
  created_at: string
  updated_at: string
}

export interface FileOut {
  id: string
  uploader_id: string
  original_name: string
  storage_path: string
  mime_type: string
  file_size: number
  source: string
  created_at: string
}

export interface TeacherAssignedFileOut {
  file: FileOut
  task_id: string
  task_title: string
  task_description?: string
  due_date?: string
  priority?: string
  status?: string
}

export interface CitationItem {
  source_index: number
  document_id: string
  document_title: string
  score: number
}

export interface RAGAnswerOut {
  answer: string
  citations: CitationItem[]
}

export const knowledgeApi = {
  uploadFile(file: File, source = 'upload') {
    const formData = new FormData()
    formData.append('file', file)
    return request.post(`/files/upload?source=${source}`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  createDocument(data: {
    file_id: string
    title: string
    description?: string
    category?: string
    tags?: string[]
    visibility?: string
  }) {
    return request.post('/knowledge/documents', data)
  },

  listDocuments(params?: {
    page?: number
    page_size?: number
    category?: string
    visibility?: string
    keyword?: string
  }) {
    return request.get('/knowledge/documents', { params })
  },

  getDocumentDetails(id: string) {
    return request.get(`/knowledge/documents/${id}`)
  },

  updateDocument(id: string, data: {
    title?: string
    description?: string
    category?: string
    tags?: string[]
    visibility?: string
  }) {
    return request.patch(`/knowledge/documents/${id}`, data)
  },

  deleteDocument(id: string) {
    return request.delete(`/knowledge/documents/${id}`)
  },

  listTeacherFiles() {
    return request.get('/knowledge/teacher-files')
  },

  getFileDownloadUrl(fileId: string) {
    return request.get(`/files/${fileId}/download`)
  },

  searchKnowledge(query: string, limit = 5) {
    return request.post(`/knowledge/search?limit=${limit}`, { query })
  },

  knowledgeQA(query: string) {
    return request.post('/knowledge/qa', { query })
  }
}
