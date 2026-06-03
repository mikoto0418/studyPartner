import request from '../request'

export interface ConversationOut {
  id: string
  title: string
  type: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface MessageOut {
  id: string
  conversation_id: string
  role: 'system' | 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ContextOptions {
  include_memory: boolean
  include_todos: boolean
  include_tasks: boolean
  include_calendar: boolean
  include_knowledge: boolean
  knowledge_query?: string
}

export const aiChatApi = {
  createConversation(data: { title?: string; type?: string }) {
    return request.post('/ai/chat/conversations', data)
  },

  listConversations(params?: { page?: number; page_size?: number; type?: string; keyword?: string }) {
    return request.get('/ai/chat/conversations', { params })
  },

  updateConversationTitle(id: string, title: string) {
    return request.patch(`/ai/chat/conversations/${id}`, { title })
  },

  deleteConversation(id: string) {
    return request.delete(`/ai/chat/conversations/${id}`)
  },

  listMessages(id: string, params?: { page?: number; page_size?: number }) {
    return request.get(`/ai/chat/conversations/${id}/messages`, { params })
  },

  /**
   * Send a streaming message using native fetch
   */
  async sendMessageStream(
    conversationId: string,
    content: string,
    contextOptions: ContextOptions,
    onChunk: (text: string) => void,
    onDone: () => void,
    onError: (err: any) => void
  ) {
    const token = localStorage.getItem('sp_token')
    const baseUrl = import.meta.env.VITE_API_BASE_URL || '/api/v1'
    
    try {
      const response = await fetch(`${baseUrl}/ai/chat/conversations/${conversationId}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
          content,
          context_options: contextOptions
        })
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) {
        throw new Error('Response body is empty')
      }

      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        
        // Save the last partial line back to the buffer
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue

          if (trimmed.startsWith('event: ')) {
            // Can be used for event type check (message / error)
            continue
          }

          if (trimmed.startsWith('data: ')) {
            const dataStr = trimmed.slice(5).trim()
            try {
              const parsed = JSON.parse(dataStr)
              if (parsed.type === 'content') {
                onChunk(parsed.content)
              } else if (parsed.type === 'done') {
                onDone()
              } else if (parsed.type === 'error') {
                onError(new Error(parsed.message || 'Stream error'))
              }
            } catch (e) {
              console.warn('Error parsing SSE data line:', trimmed, e)
            }
          }
        }
      }
    } catch (error) {
      onError(error)
    }
  }
}
