import request from '../request'

export interface NoteData {
  title?: string
  content: string
  color?: string
  category?: string
  is_pinned?: boolean
  sort_order?: number
}

export const noteApi = {
  listNotes(params?: { category?: string }) {
    return request.get('/notes/', { params })
  },
  
  createNote(data: NoteData) {
    return request.post('/notes/', data)
  },
  
  updateNote(id: string, data: Partial<NoteData>) {
    return request.put(`/notes/${id}`, data)
  },
  
  deleteNote(id: string) {
    return request.delete(`/notes/${id}`)
  }
}
