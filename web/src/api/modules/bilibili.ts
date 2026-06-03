import request from '../request'

export interface BilibiliResourceOut {
  id: string
  creator_id: string
  bvid: string
  title: string
  description?: string
  cover_url?: string
  author_name?: string
  total_episodes: number
  total_duration?: number
  category?: string
  episodes_info?: any[]
  is_shared: boolean
  created_at: string
  updated_at: string
}

export const bilibiliApi = {
  addResource(data: {
    bvid: string
    title: string
    description?: string
    cover_url?: string
    author_name?: string
    total_episodes?: number
    total_duration?: number
    category?: string
    episodes_info?: any[]
    is_shared?: boolean
  }) {
    return request.post('/bilibili/', data)
  },

  listResources(params?: { keyword?: string }) {
    return request.get('/bilibili/', { params })
  },

  deleteResource(id: string) {
    return request.delete(`/bilibili/${id}`)
  },

  logWatchEvent(data: {
    resource_id: string
    event_type: 'open' | 'heartbeat' | 'close' | 'manual_complete'
    episode_number?: number
    watch_duration?: number
    is_completed?: boolean
  }) {
    return request.post('/bilibili/log', data)
  }
}
