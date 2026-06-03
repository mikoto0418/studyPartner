import { ref, onUnmounted, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { ElNotification } from 'element-plus'

const socket = ref<WebSocket | null>(null)
const isConnected = ref(false)
let reconnectTimer: number | null = null

export function useWebSocket() {
  const authStore = useAuthStore()

  const disconnect = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (socket.value) {
      socket.value.close()
      socket.value = null
    }
    isConnected.value = false
  }

  const connect = () => {
    disconnect()
    
    const token = authStore.token
    if (!token) return

    let base = import.meta.env.VITE_WS_BASE_URL as string
    if (!base) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = import.meta.env.DEV ? 'localhost:8000' : window.location.host
      base = `${protocol}//${host}/api/v1`
    }
    
    const wsUrl = `${base}/ws?token=${encodeURIComponent(token)}`
    
    try {
      socket.value = new WebSocket(wsUrl)
      
      socket.value.onopen = () => {
        isConnected.value = true
        console.log('WebSocket successfully connected')
        
        // Start ping heartbeat interval every 30 seconds
        const pingInterval = setInterval(() => {
          if (socket.value && socket.value.readyState === WebSocket.OPEN) {
            socket.value.send('ping')
          } else {
            clearInterval(pingInterval)
          }
        }, 30000)
      }
      
      socket.value.onmessage = (event) => {
        if (event.data === 'pong') return
        
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'notification') {
            ElNotification({
              title: message.data.title || '系统通知',
              message: message.data.content || '',
              type: 'info',
              duration: 6000,
              position: 'top-right'
            })
            
            // Dispatch a custom event so other components (like navbar notifications list) can listen and refresh
            window.dispatchEvent(new CustomEvent('new-notification', { detail: message.data }))
          }
        } catch (e) {
          console.warn('Failed to parse WebSocket message data:', event.data)
        }
      }
      
      socket.value.onclose = (event) => {
        isConnected.value = false
        console.log('WebSocket connection closed:', event.code, event.reason)
        // Auto-reconnect if authenticated and not manually disconnected
        if (authStore.isAuthenticated) {
          reconnectTimer = window.setTimeout(() => {
            console.log('Attempting to reconnect WebSocket...')
            connect()
          }, 5000)
        }
      }
      
      socket.value.onerror = (error) => {
        console.error('WebSocket encountered an error:', error)
      }
    } catch (err) {
      console.error('Failed to create WebSocket instance:', err)
    }
  }

  // Watch auth state to connect/disconnect automatically
  watch(
    () => authStore.token,
    (newToken) => {
      if (newToken) {
        connect()
      } else {
        disconnect()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    // We keep socket connection alive globally, but clean up listeners or socket if needed.
    // Usually we don't disconnect in component onUnmounted if we want global connection.
    // So we don't call disconnect here if useWebSocket is called multiple times.
  })

  return {
    isConnected,
    connect,
    disconnect
  }
}
