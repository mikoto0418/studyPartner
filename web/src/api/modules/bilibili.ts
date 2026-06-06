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

export interface BilibiliStreamInfo {
  type: 'mp4-proxy'
  src: string
}

export interface BilibiliMetaOut {
  bvid: string
  title: string
  description?: string
  cover_url?: string
  author_name?: string
  total_episodes: number
  total_duration?: number
  episodes_info?: any[]
}

export interface BilibiliWatchStatOut {
  resource_id: string
  resource_title: string
  episode_number: number
  start_time: string
  end_time: string
  watch_seconds: number
  pause_count: number
  completed: boolean
}

export const bilibiliApi = {
  getMeta(bvid: string) {
    return request.get('/bilibili/meta', { params: { bvid } })
  },

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

  getStreamInfo(params: { bvid: string; episode?: number }) {
    return request.get('/bilibili/stream-info', { params })
  },

  logWatchEvent(data: {
    resource_id: string
    event_type: 'open' | 'heartbeat' | 'pause' | 'close' | 'manual_complete'
    episode_number?: number
    watch_duration?: number
    is_completed?: boolean
  }) {
    return request.post('/bilibili/log', data)
  },

  getStats(params?: { resource_id?: string; limit?: number }) {
    return request.get('/bilibili/stats', { params })
  }
}
