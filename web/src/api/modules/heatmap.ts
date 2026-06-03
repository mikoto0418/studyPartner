import request from '../request'

export interface HeatmapPointOut {
  date: string
  count: number
}

export const heatmapApi = {
  getHeatmapData(params?: {
    start_date?: string
    end_date?: string
    student_id?: string
  }) {
    return request.get('/heatmap/', { params })
  }
}
