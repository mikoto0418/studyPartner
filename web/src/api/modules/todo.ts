import request from '../request'

export interface TodoData {
  title: string
  description?: string
  priority?: string
  status?: string
  category?: string
  due_date?: string
  sort_order?: number
}

export const todoApi = {
  listTodos(params?: { status?: string; priority?: string; category?: string }) {
    return request.get('/todos/', { params })
  },
  
  createTodo(data: TodoData) {
    return request.post('/todos/', data)
  },
  
  updateTodo(id: string, data: Partial<TodoData>) {
    return request.put(`/todos/${id}`, data)
  },
  
  deleteTodo(id: string) {
    return request.delete(`/todos/${id}`)
  }
}
