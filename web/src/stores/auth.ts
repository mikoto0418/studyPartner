import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('sp_token'))
  const role = ref<string | null>(localStorage.getItem('sp_role'))
  const username = ref<string | null>(localStorage.getItem('sp_username'))

  const isAuthenticated = computed(() => !!token.value)

  const login = (userData: { token: string; role: string; username: string }) => {
    token.value = userData.token
    role.value = userData.role
    username.value = userData.username

    localStorage.setItem('sp_token', userData.token)
    localStorage.setItem('sp_role', userData.role)
    localStorage.setItem('sp_username', userData.username)
  }

  const logout = () => {
    token.value = null
    role.value = null
    username.value = null

    localStorage.removeItem('sp_token')
    localStorage.removeItem('sp_role')
    localStorage.removeItem('sp_username')
  }

  return {
    token,
    role,
    username,
    isAuthenticated,
    login,
    logout
  }
})
