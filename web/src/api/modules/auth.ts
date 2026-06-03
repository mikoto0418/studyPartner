import request from '../request'
import { UserOut } from './user'

export interface TokenOut {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: UserOut
}

export const authApi = {
  login(data: any) {
    return request.post('/auth/login', data)
  },

  sendCode(data: { email: string; action_type: 'register' | 'reset_password' }) {
    return request.post('/auth/send-code', data)
  },

  register(data: any) {
    return request.post('/auth/register', data)
  },

  resetPassword(data: any) {
    return request.post('/auth/reset-password', data)
  },

  getMe() {
    return request.get('/auth/me')
  }
}
