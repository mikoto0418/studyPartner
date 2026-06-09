import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('sp_token'))
  const role = ref<string | null>(localStorage.getItem('sp_role'))
  const username = ref<string | null>(localStorage.getItem('sp_username'))
  const displayName = ref<string | null>(localStorage.getItem('sp_display_name'))

  const isAuthenticated = computed(() => !!token.value)

  const login = (userData: { token: string; role: string; username: string; displayName?: string | null }) => {
    token.value = userData.token
    role.value = userData.role
    username.value = userData.username
    displayName.value = userData.displayName || null

    localStorage.setItem('sp_token', userData.token)
    localStorage.setItem('sp_role', userData.role)
    localStorage.setItem('sp_username', userData.username)
    if (userData.displayName) {
      localStorage.setItem('sp_display_name', userData.displayName)
    } else {
      localStorage.removeItem('sp_display_name')
    }
  }

  const logout = () => {
    token.value = null
    role.value = null
    username.value = null
    displayName.value = null

    localStorage.removeItem('sp_token')
    localStorage.removeItem('sp_role')
    localStorage.removeItem('sp_username')
    localStorage.removeItem('sp_display_name')
  }

  return {
    token,
    role,
    username,
    displayName,
    isAuthenticated,
    login,
    logout
  }
})
