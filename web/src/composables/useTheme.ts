import { ref } from 'vue'

const THEME_STORAGE_KEY = 'sp_theme'

// 登录页和主布局共用同一个主题状态：登录前也能切换主题，登录后保持一致。
const isDark = ref(false)

const applyTheme = (dark: boolean) => {
  isDark.value = dark
  document.documentElement.classList.toggle('dark', dark)
}

export const initTheme = () => {
  applyTheme(localStorage.getItem(THEME_STORAGE_KEY) === 'dark')
}

export const useTheme = () => {
  const toggleTheme = () => {
    const next = !isDark.value
    applyTheme(next)
    localStorage.setItem(THEME_STORAGE_KEY, next ? 'dark' : 'light')
  }

  return { isDark, toggleTheme }
}
