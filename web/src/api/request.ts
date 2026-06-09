import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: Number(import.meta.env.VITE_API_TIMEOUT_MS) || 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request Interceptor
request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('sp_token')
    if (token && config.headers) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response Interceptor
request.interceptors.response.use(
  (response) => {
    const res = response.data
    
    // Check business code (0 means success as per API spec 1.1)
    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败，请稍后重试')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    
    return res
  },
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    const isTimeout = error.code === 'ECONNABORTED' || String(error.message || '').toLowerCase().includes('timeout')
    
    if (status === 401) {
      // Unauthorized: clear storage and redirect to login
      ElMessage.warning('身份已过期，请重新登录')
      localStorage.clear()
      router.push('/login')
    } else if (status === 403) {
      ElMessage.error('权限不足，无法进行此操作')
    } else if (isTimeout) {
      ElMessage.error('请求超时，当前网络或隧道响应较慢，请稍后重试')
    } else {
      const errMsg = data?.message || error.message || '系统繁忙，请稍后再试'
      ElMessage.error(errMsg)
    }
    
    return Promise.reject(error)
  }
)

export default request
