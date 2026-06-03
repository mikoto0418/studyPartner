import request from '../request'

export const studyTimeApi = {
  reportHeartbeat(data: {
    session_id: string
    duration_seconds: number
    source?: 'platform' | 'bilibili'
  }) {
    return request.post('/study-time/heartbeat', data)
  }
}
