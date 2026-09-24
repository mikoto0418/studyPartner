import request from '../request'

export interface FeatureModule {
  code: string
  name: string
  description?: string | null
  enabled: boolean
  visible: boolean
}

export const moduleApi = {
  getMyModules() {
    return request.get('/modules')
  },

  listAllModules() {
    return request.get('/modules/all')
  },

  updateModule(code: string, data: { enabled?: boolean; visible?: boolean }) {
    return request.patch(`/modules/${code}`, data)
  }
}