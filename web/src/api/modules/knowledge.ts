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

  deleteDocument(id: string) {
    return request.delete(`/knowledge/documents/${id}`)
  },

  searchKnowledge(query: string, limit = 5) {
    return request.post(`/knowledge/search?limit=${limit}`, { query })
  },

  knowledgeQA(query: string) {
    return request.post('/knowledge/qa', { query })
  }
}
