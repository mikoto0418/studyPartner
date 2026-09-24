import { onBeforeUnmount, ref } from 'vue'
import type { BehaviorEventPayload } from '../api/modules/assessment'

export interface AntiCheatCallbacks {
  // 允许返回 Promise，失败时可把事件放回队列重投
  reportEvents: (events: BehaviorEventPayload[]) => void | Promise<void>
  onFullscreenExit?: (count: number) => void
  onMaxViolations?: () => void
}

// 离线时事件会积压在内存里，设上限避免无限增长
const MAX_QUEUE_SIZE = 500

interface FocusState {
  startedAt: number
  target: string
  questionId: string | null
  field: string | null
}

export function useAntiCheat(options: { maxFullscreenExits?: number } = {}) {
  const maxFullscreenExits = options.maxFullscreenExits ?? 3
  const fullscreenActive = ref(false)
  const fullscreenExitCount = ref(0)
  const blockedActionCount = ref(0)

  let tracking = false
  let flushTimer: number | null = null
  let heartbeatTimer: number | null = null
  let devtoolsTimer: number | null = null
  let scrollTimer: number | null = null
  let focusLostAt: number | null = null
  let focusState: FocusState | null = null
  let currentQuestion: string | null = null
  let questionStartedAt: number | null = null
  let devtoolsOpen = false

  const queue: BehaviorEventPayload[] = []

  let sessionId = ''
  let attemptId: string | null = null
  let reportEvents: AntiCheatCallbacks['reportEvents'] = () => {}
  let onFullscreenExit: NonNullable<AntiCheatCallbacks['onFullscreenExit']> = () => {}
  let onMaxViolations: NonNullable<AntiCheatCallbacks['onMaxViolations']> = () => {}

  const trapDebugger = new Function('debugger')

  const ts = () => Date.now()
  const iso = () => new Date().toISOString()

  const push = (event_type: string, payload: Record<string, any> = {}) => {
    if (queue.length >= MAX_QUEUE_SIZE) queue.shift()
    queue.push({ event_type, payload, occurred_at: iso() })
  }

  const flush = () => {
    if (!queue.length) return
    const batch = queue.splice(0, queue.length)
    // 上报失败就把这批事件放回队首，等下一次 flush 重投；
    // 否则一次网络抖动就会让这段作答永久没有行为证据。
    const requeue = () => {
      if (queue.length + batch.length > MAX_QUEUE_SIZE) {
        // 队列已满，这批只能丢弃；留个痕迹，否则行为证据会无声消失。
        console.warn(`[anti-cheat] 行为事件队列已满，丢弃 ${batch.length} 条事件`)
        return
      }
      queue.unshift(...batch)
    }
    try {
      const res = reportEvents(batch)
      if (res && typeof (res as Promise<void>).catch === 'function') {
        ;(res as Promise<void>).catch(requeue)
      }
    } catch (err) {
      requeue()
    }
  }

  const recordViolation = () => {
    blockedActionCount.value += 1
  }

  // ---------- 键盘/剪贴板多层拦截 ----------
  const isModifier = (e: KeyboardEvent) => e.ctrlKey || e.metaKey
  const blockedKeys = new Set(['KeyC', 'KeyV', 'KeyX', 'KeyS', 'KeyP', 'KeyU'])
  const blockedFKeys = new Set(['F12', 'F3'])
  const devtoolsKeys = new Set(['KeyI', 'KeyJ', 'KeyC'])

  const preventAndFlag = (e: Event, type: string, payload: Record<string, any> = {}) => {
    e.preventDefault()
    e.stopPropagation()
    recordViolation()
    push(type, payload)
  }

  const onKeydown = (e: KeyboardEvent) => {
    if (blockedFKeys.has(e.code)) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code })
      return
    }
    if (isModifier(e) && blockedKeys.has(e.code)) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code, key: e.key })
      return
    }
    if (isModifier(e) && e.shiftKey && devtoolsKeys.has(e.code)) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code, devtools: true })
    }
  }

  const onKeyup = (e: KeyboardEvent) => {
    if (e.code === 'PrintScreen') {
      recordViolation()
      push('blocked_shortcut', { code: 'PrintScreen' })
    }
  }

  const blockClipboard = (type: string) => (e: Event) => {
    preventAndFlag(e, type, {})
  }

  const onPaste = blockClipboard('blocked_paste')
  const onCopy = blockClipboard('blocked_copy')
  const onCut = blockClipboard('blocked_cut')
  const onDrop = blockClipboard('blocked_drop')
  const onContextMenu = blockClipboard('blocked_contextmenu')

  const onBeforeInput = (e: InputEvent) => {
    const inputType = (e as any).inputType
    if (inputType === 'insertFromPaste' || inputType === 'insertFromDrop' || inputType === 'insertReplacementText') {
      preventAndFlag(e, 'blocked_insert', { input_type: inputType })
    }
  }

  const onSelectStart = (e: Event) => {
    const el = e.target as HTMLElement | null
    const tag = el && el.tagName
    if (tag === 'TEXTAREA' || tag === 'INPUT') return
    preventAndFlag(e, 'blocked_selection', {})
  }

  const onDragStart = (e: Event) => {
    preventAndFlag(e, 'blocked_drag', {})
  }

  // ---------- 接管 execCommand 与剪贴板读取 ----------
  let originalExecCommand: typeof document.execCommand | null = null
  let originalReadText: typeof navigator.clipboard.readText | null = null
  let originalRead: typeof navigator.clipboard.read | null = null

  const installOverrides = () => {
    if (document.execCommand) {
      originalExecCommand = document.execCommand.bind(document)
      ;(document as any).execCommand = (command: string, ...args: any[]) => {
        const cmd = String(command).toLowerCase()
        if (cmd === 'copy' || cmd === 'cut' || cmd === 'paste') {
          recordViolation()
          push('blocked_exec', { command: cmd })
          return false
        }
        return originalExecCommand!(command, ...args)
      }
    }
    try {
      if (navigator.clipboard) {
        originalReadText = navigator.clipboard.readText.bind(navigator.clipboard)
        originalRead = navigator.clipboard.read.bind(navigator.clipboard)
        ;(navigator.clipboard as any).readText = async () => {
          recordViolation()
          push('clipboard_read', { source: 'readText' })
          throw new DOMException('Blocked', 'NotAllowedError')
        }
        ;(navigator.clipboard as any).read = async () => {
          recordViolation()
          push('clipboard_read', { source: 'read' })
          throw new DOMException('Blocked', 'NotAllowedError')
        }
      }
    } catch (err) {
      // 剪贴板 API 为只读时忽略覆写失败
    }
  }

  const restoreOverrides = () => {
    if (originalExecCommand) {
      ;(document as any).execCommand = originalExecCommand
      originalExecCommand = null
    }
    try {
      if (navigator.clipboard) {
        if (originalReadText) (navigator.clipboard as any).readText = originalReadText
        if (originalRead) (navigator.clipboard as any).read = originalRead
      }
    } catch (err) {}
    originalReadText = null
    originalRead = null
  }

  // ---------- 全屏 ----------
  const isFullscreen = () => !!document.fullscreenElement

  const enterFullscreen = async () => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
      }
      fullscreenActive.value = true
    } catch (err) {
      push('fullscreen_denied', {})
    }
  }

  const onFullscreenChange = () => {
    const active = isFullscreen()
    fullscreenActive.value = active
    if (!active) {
      fullscreenExitCount.value += 1
      push('fullscreen_exit', { count: fullscreenExitCount.value })
      onFullscreenExit(fullscreenExitCount.value)
      if (fullscreenExitCount.value >= maxFullscreenExits) {
        onMaxViolations()
      }
    } else {
      push('fullscreen_enter', {})
    }
  }

  const onFocus = () => {
    if (focusLostAt != null) {
      const durationMs = ts() - focusLostAt
      focusLostAt = null
      push('focus_gain', { duration_ms: durationMs })
    }
  }

  const onBlur = () => {
    focusLostAt = ts()
    push('focus_loss', {})
  }

  const onVisibilityChange = () => {
    push(document.hidden ? 'visibility_hidden' : 'visibility_visible', {})
  }

  // ---------- 焦点位置与停留时长 ----------
  const describeFocus = (el: Element | null): FocusState | null => {
    if (!el) return null
    const target = el.getAttribute('data-ac-target')
    if (!target) return null
    return {
      startedAt: ts(),
      target,
      questionId: el.getAttribute('data-ac-question'),
      field: el.getAttribute('data-ac-field')
    }
  }

  const onFocusIn = (e: FocusEvent) => {
    const next = describeFocus(e.target as Element | null)
    commitFocusDwell()
    focusState = next
  }

  const onFocusOut = (_e: FocusEvent) => {
    commitFocusDwell()
    focusState = null
  }

  const commitFocusDwell = () => {
    if (!focusState) return
    const now = ts()
    const durationMs = now - focusState.startedAt
    focusState.startedAt = now
    if (durationMs >= 300) {
      push('focus_dwell', {
        target: focusState.target,
        question_id: focusState.questionId,
        field: focusState.field,
        duration_ms: durationMs
      })
    }
  }

  // ---------- 视口题目停留 ----------
  const findCurrentQuestion = (): string | null => {
    const els = document.querySelectorAll('[data-ac-scroll-question]')
    if (!els.length) return null
    const center = window.innerHeight / 2
    let best: string | null = null
    let bestDist = Infinity
    els.forEach((el) => {
      const rect = el.getBoundingClientRect()
      const elCenter = (rect.top + rect.bottom) / 2
      const dist = Math.abs(elCenter - center)
      const onScreen = rect.top <= center && rect.bottom >= center
      if (onScreen) {
        best = el.getAttribute('data-ac-scroll-question')
        bestDist = 0
      } else if (elCenter > 0 && elCenter < window.innerHeight && dist < bestDist) {
        bestDist = dist
        best = el.getAttribute('data-ac-scroll-question')
      }
    })
    return best
  }

  const commitQuestionDwell = () => {
    if (currentQuestion == null || questionStartedAt == null) return
    const durationMs = ts() - questionStartedAt
    questionStartedAt = ts()
    if (durationMs >= 1000) {
      push('question_dwell', { question_id: currentQuestion, duration_ms: durationMs })
    }
  }

  const updateCurrentQuestion = () => {
    const qid = findCurrentQuestion()
    if (qid === currentQuestion) return
    commitQuestionDwell()
    currentQuestion = qid
    questionStartedAt = ts()
  }

  const onScroll = () => {
    if (scrollTimer != null) return
    scrollTimer = window.setTimeout(() => {
      scrollTimer = null
      updateCurrentQuestion()
    }, 400)
  }

  // ---------- 开发者工具检测 ----------
  const detectDevtools = (): boolean => {
    const start = performance.now()
    trapDebugger()
    if (performance.now() - start > 80) return true
    const w = window.outerWidth - window.innerWidth
    const h = window.outerHeight - window.innerHeight
    return w > 160 || h > 160
  }

  const onDevtoolsCheck = () => {
    const open = detectDevtools()
    if (open && !devtoolsOpen) {
      devtoolsOpen = true
      recordViolation()
      push('devtools_open', {})
    } else if (!open && devtoolsOpen) {
      devtoolsOpen = false
    }
  }

  const onHeartbeat = () => {
    commitFocusDwell()
    commitQuestionDwell()
  }

  const startTracking = (sid: string, aid: string | null, callbacks: AntiCheatCallbacks) => {
    if (tracking) return
    tracking = true
    sessionId = sid
    attemptId = aid
    reportEvents = callbacks.reportEvents
    onFullscreenExit = callbacks.onFullscreenExit ?? (() => {})
    onMaxViolations = callbacks.onMaxViolations ?? (() => {})

    window.addEventListener('keydown', onKeydown, true)
    window.addEventListener('keyup', onKeyup, true)
    document.addEventListener('paste', onPaste, true)
    document.addEventListener('copy', onCopy, true)
    document.addEventListener('cut', onCut, true)
    document.addEventListener('drop', onDrop, true)
    document.addEventListener('contextmenu', onContextMenu, true)
    document.addEventListener('beforeinput', onBeforeInput, true)
    document.addEventListener('selectstart', onSelectStart, true)
    document.addEventListener('dragstart', onDragStart, true)
    document.addEventListener('fullscreenchange', onFullscreenChange)
    window.addEventListener('focus', onFocus)
    window.addEventListener('blur', onBlur)
    window.addEventListener('scroll', onScroll, true)
    document.addEventListener('visibilitychange', onVisibilityChange)
    document.addEventListener('focusin', onFocusIn, true)
    document.addEventListener('focusout', onFocusOut, true)
    window.addEventListener('pagehide', onPageHide)

    installOverrides()

    push('session_start', { session_id: sessionId, attempt_id: attemptId })
    currentQuestion = findCurrentQuestion()
    questionStartedAt = ts()
    enterFullscreen()

    flushTimer = window.setInterval(flush, 5000)
    heartbeatTimer = window.setInterval(onHeartbeat, 6000)
    devtoolsTimer = window.setInterval(onDevtoolsCheck, 1200)
  }

  const onPageHide = () => {
    if (!tracking) return
    push('session_end', { session_id: sessionId, attempt_id: attemptId, reason: 'pagehide' })
    flush()
  }

  const stopTracking = () => {
    if (!tracking) return
    tracking = false
    commitFocusDwell()
    commitQuestionDwell()
    push('session_end', { session_id: sessionId, attempt_id: attemptId, reason: 'stop' })
    flush()

    if (flushTimer != null) {
      clearInterval(flushTimer)
      flushTimer = null
    }
    if (heartbeatTimer != null) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
    if (devtoolsTimer != null) {
      clearInterval(devtoolsTimer)
      devtoolsTimer = null
    }
    if (scrollTimer != null) {
      clearTimeout(scrollTimer)
      scrollTimer = null
    }

    window.removeEventListener('keydown', onKeydown, true)
    window.removeEventListener('keyup', onKeyup, true)
    document.removeEventListener('paste', onPaste, true)
    document.removeEventListener('copy', onCopy, true)
    document.removeEventListener('cut', onCut, true)
    document.removeEventListener('drop', onDrop, true)
    document.removeEventListener('contextmenu', onContextMenu, true)
    document.removeEventListener('beforeinput', onBeforeInput, true)
    document.removeEventListener('selectstart', onSelectStart, true)
    document.removeEventListener('dragstart', onDragStart, true)
    document.removeEventListener('fullscreenchange', onFullscreenChange)
    window.removeEventListener('focus', onFocus)
    window.removeEventListener('blur', onBlur)
    window.removeEventListener('scroll', onScroll, true)
    document.removeEventListener('visibilitychange', onVisibilityChange)
    document.removeEventListener('focusin', onFocusIn, true)
    document.removeEventListener('focusout', onFocusOut, true)
    window.removeEventListener('pagehide', onPageHide)

    restoreOverrides()

    focusState = null
    currentQuestion = null
    questionStartedAt = null
    devtoolsOpen = false
  }

  const exitFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen()
      }
    } catch (err) {
      // 忽略退出失败
    }
  }

  onBeforeUnmount(() => stopTracking())

  return {
    fullscreenActive,
    fullscreenExitCount,
    blockedActionCount,
    startTracking,
    stopTracking,
    enterFullscreen,
    exitFullscreen,
    flush
  }
}