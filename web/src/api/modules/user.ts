import request from '../request'

export interface RoleOut {
  id: string
  code: string
  name: string
  description?: string
}

export interface StudentProfileOut {
  id: string
  student_id?: string | null
  grade?: string | null
  major?: string | null
  research_direction?: string | null
  enrollment_date?: string | null
  bio?: string | null
  extra_info?: Record<string, any> | null
}

export interface UserOut {
  id: string
  username: string
  email: string
  nickname?: string
  display_name?: string
  phone?: string
  status: string
  avatar_url?: string
  last_login_at?: string
  created_at: string
  updated_at: string
  roles: RoleOut[]
  student_profile?: StudentProfileOut
}

export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export const getUserDisplayName = (user?: Partial<Pick<UserOut, 'display_name' | 'nickname' | 'username'>> | null) => {
  if (!user) return '未设置姓名'
  return user.display_name || user.nickname?.trim() || '未设置姓名'
}

export const getUserAvatarText = (user?: Partial<Pick<UserOut, 'display_name' | 'nickname' | 'username'>> | null) => {
  return (user?.display_name || user?.nickname?.trim() || '未').charAt(0).toUpperCase()
}

export const userApi = {
  listUsers(params?: { role_code?: string; page?: number; page_size?: number }) {
    return request.get('/users/', { params })
  },

  createUser(data: any) {
    return request.post('/users/', data)
  },

  updateUser(id: string, data: any) {
    return request.put(`/users/${id}`, data)
  },

  deleteUser(id: string) {
    return request.delete(`/users/${id}`)
  },

  updateStudentProfile(userId: string, data: Partial<StudentProfileOut>) {
    return request.put(`/users/${userId}/student-profile`, data)
  }
}
