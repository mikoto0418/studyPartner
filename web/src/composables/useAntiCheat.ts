import { onBeforeUnmount, ref } from 'vue'
import type { BehaviorEventPayload } from '../api/modules/assessment'
import { diffAnswerText } from '../utils/answerEditDiff'

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
  // 失焦/切后台时把卷面盖住：后台窗口仍在渲染，不遮挡的话截图与录屏能完整抄走
  const contentHidden = ref(false)

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
  // 按输入框分别记录「已敲入字符数」与「上次的文本长度」。
  // 用 WeakMap 而不是单个变量：多个输入框共用一个计数器会互相串，
  // 且首次进入某框时无法判断这一下是敲的还是整段灌进来的。
  const keystrokeCounts = new WeakMap<Element, number>()
  const valueSnapshots = new WeakMap<Element, string>()

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
    const occurred_at = iso()
    // 连续逐字输入/退格合并成一个编辑段：保留完整新增/删除文本与边界，
    // 但不要每敲一个字就写一行数据库，避免一篇作文生成数千事件。
    if (event_type === 'answer_edit') {
      const previous = queue[queue.length - 1]
      const old = previous?.payload
      if (
        previous?.event_type === 'answer_edit' &&
        old &&
        old.input_method === payload.input_method &&
        old?.question_id === payload.question_id &&
        old?.field === payload.field
      ) {
        const oldInserted = String(old.inserted_text || '')
        const oldDeleted = String(old.deleted_text || '')
        const inserted = String(payload.inserted_text || '')
        const deleted = String(payload.deleted_text || '')
        const contiguousInsert =
          old.operation === 'insert' && payload.operation === 'insert' &&
          Number(old.position) + oldInserted.length === Number(payload.position)
        const contiguousBackspace =
          old.operation === 'delete' && payload.operation === 'delete' &&
          Number(payload.position) + deleted.length === Number(old.position)
        const contiguousDelete =
          old.operation === 'delete' && payload.operation === 'delete' &&
          Number(payload.position) === Number(old.position)
        if (contiguousInsert) {
          old.inserted_text = oldInserted + inserted
          old.inserted_chars = Number(old.inserted_chars || 0) + Number(payload.inserted_chars || 0)
          old.current_length = payload.current_length
          previous.occurred_at = occurred_at
          return
        }
        if (contiguousBackspace || contiguousDelete) {
          old.position = Math.min(Number(old.position), Number(payload.position))
          old.deleted_text = contiguousBackspace ? deleted + oldDeleted : oldDeleted + deleted
          old.deleted_chars = Number(old.deleted_chars || 0) + Number(payload.deleted_chars || 0)
          old.current_length = payload.current_length
          previous.occurred_at = occurred_at
          return
        }
      }
    }
    if (queue.length >= MAX_QUEUE_SIZE) queue.shift()
    queue.push({ event_type, payload, occurred_at })
  }

  const flush = () => {
    if (!queue.length) return
    // BehaviorBatchReq 上限 200；文本历史可能快速产生大量编辑事件，必须分批发。
    const batch = queue.splice(0, 200)
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
  // Ctrl+F 页内搜索是取答案的常规路径，一并拦掉
  const blockedKeys = new Set(['KeyC', 'KeyV', 'KeyX', 'KeyS', 'KeyP', 'KeyU', 'KeyF'])
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
    const target = e.target as HTMLElement | null
    const editable = !!target && (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT')
    // 输入框内的 Ctrl+A 是「全选自己写的字」，属于正常编辑，放行；
    // 页面级全选（对着题干）才拦 —— 那才是「全选复制」的第一步。
    if (isModifier(e) && e.code === 'KeyA' && !editable) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code, key: e.key })
      return
    }
    if (isModifier(e) && blockedKeys.has(e.code)) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code, key: e.key })
      return
    }
    if (isModifier(e) && e.shiftKey && devtoolsKeys.has(e.code)) {
      preventAndFlag(e, 'blocked_shortcut', { code: e.code, devtools: true })
      return
    }
    // 记录真实敲入的字符数，供输入比对用。带修饰键的组合（Ctrl+Z 等）不产生文字，
    // 输入法组合期间也不计，否则会把正常操作误算成按键。
    if (!e.isComposing && !isModifier(e) && !e.altKey && e.key.length === 1) {
      const t = e.target as Element | null
      if (t) keystrokeCounts.set(t, (keystrokeCounts.get(t) ?? 0) + 1)
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

  // 浏览器原生菜单「粘贴」在部分环境既不派发 paste 也不派发 beforeinput，
  // 只拦事件会漏。这里按「输入框增长了多少字符」与「实际敲了多少键」比对，
  // 多出来的就是非手敲输入。
  //
  // 基线在 focusin 时就记下（此刻输入框通常还是空的），所以「进框第一次就整段
  // 粘贴」同样能抓到 —— 只在 input 事件里首次建基线的话，那一整段会被当成起点跳过。
  // 输入法（中文等）会一次性提交整段文字，且提交那一拍 isComposing 已是 false，
  // 所以用组合状态 + 结束后 150ms 时间窗共同排除，避免把中文作答误判成粘贴。
  let composing = false
  let compositionEndedAt = 0

  const onCompositionStart = () => {
    composing = true
  }

  const onCompositionEnd = () => {
    composing = false
    compositionEndedAt = Date.now()
  }

  const resetInputBaseline = (el: Element) => {
    const value = (el as HTMLInputElement).value
    valueSnapshots.set(el, value)
    keystrokeCounts.set(el, 0)
  }

  const onInputBaseline = (e: FocusEvent) => {
    const el = e.target as HTMLElement | null
    if (!el) return
    if (el.tagName !== 'TEXTAREA' && el.tagName !== 'INPUT') return
    resetInputBaseline(el)
  }

  const onInputCapture = (e: Event) => {
    const el = e.target as HTMLElement | null
    if (!el) return
    const tag = el.tagName
    if (tag !== 'TEXTAREA' && tag !== 'INPUT') return
    const value = (el as HTMLInputElement).value
    // composition 中的中间态不记录；最终 input 到来时，用原快照记成一次 IME 编辑。
    if (composing || (e as InputEvent).isComposing) return
    const previous = valueSnapshots.get(el)
    if (previous === undefined) {
      resetInputBaseline(el)
      return
    }

    const diff = diffAnswerText(previous, value)
    const typed = keystrokeCounts.get(el) ?? 0
    const isImeCommit = Date.now() - compositionEndedAt < 150
    const inputMethod = isImeCommit
      ? 'ime'
      : diff.insertedText.length === 0
        ? 'delete'
        : typed === 0
          ? 'non_key_input'
          : 'typing'

    valueSnapshots.set(el, value)
    keystrokeCounts.set(el, 0)
    if (diff.operation === 'none') return

    const questionId = el.getAttribute('data-ac-question')
    const field = el.getAttribute('data-ac-field')
    push('answer_edit', {
      question_id: questionId,
      field,
      operation: diff.operation,
      input_method: inputMethod,
      position: diff.position,
      inserted_text: diff.insertedText,
      deleted_text: diff.deletedText,
      inserted_chars: diff.insertedText.length,
      deleted_chars: diff.deletedText.length,
      previous_length: previous.length,
      current_length: value.length
    })

    // 原生菜单粘贴等绕过 paste/beforeinput 的路径仍保存完整 edit diff；
    // 额外打违规标记。短的非键盘输入只保留编辑记录，减少语音/候选词误报。
    if (inputMethod === 'non_key_input' && diff.insertedText.length >= 4) {
      recordViolation()
      push('blocked_input', {
        question_id: questionId,
        field,
        inserted: diff.insertedText.length,
        keystrokes: typed
      })
    }
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

  /**
   * 请求进入全屏，返回是否真的进去了。
   *
   * 返回值必须被调用方检查：requestFullscreen 会因「用户拒绝」或「非用户手势」
   * 而 reject，早期实现把异常吞掉后照样放行，学生只要在弹窗上点拒绝就能全程
   * 窗口化作答 —— fullscreenchange 从未触发，退出计数始终为 0，所有基于
   * 「退出全屏」的拦截全部失效。
   */
  const enterFullscreen = async (): Promise<boolean> => {
    try {
      if (!document.fullscreenElement) {
        await document.documentElement.requestFullscreen()
      }
      fullscreenActive.value = true
      return true
    } catch (err) {
      fullscreenActive.value = false
      push('fullscreen_denied', {})
      return false
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
    contentHidden.value = false
  }

  const onBlur = () => {
    focusLostAt = ts()
    // 不遮住的话，切到后台的窗口仍在渲染卷面，截图/录屏能完整抄走
    contentHidden.value = true
    push('focus_loss', {})
  }

  const onVisibilityChange = () => {
    const hidden = document.hidden
    if (hidden) contentHidden.value = true
    else contentHidden.value = false
    push(hidden ? 'visibility_hidden' : 'visibility_visible', {})
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
    // 进输入框就把基线归零。此刻框里通常是空的（或上次的旧值），
    // 之后第一次 input 的增量才是这次真正插入的内容。
    onInputBaseline(e)
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
  // 三重信号叠加，单靠窗口尺寸差早就能被绕过：
  //   1) debugger 语句耗时（开着 devtools 时会被断点挂住）
  //   2) console 对象被打开后才会有的 toString 探针
  //   3) 窗口尺寸差（保留作兜底，宽高同时超过阈值才算）
  // 独立标志，不能复用 devtoolsOpen：那个变量还承担「本次是否已上报」的去重职责
  let probeTriggered = false
  const devtoolsProbe = new Image()
  Object.defineProperty(devtoolsProbe, 'id', {
    get() {
      probeTriggered = true
      return 'ac-probe'
    }
  })

  const detectDevtools = (): boolean => {
    // 1) debugger 计时
    const start = performance.now()
    trapDebugger()
    if (performance.now() - start > 80) return true

    // 2) console 探针：打开 devtools 时 console 会读取对象的 id 触发 getter
    probeTriggered = false
    try {
      // eslint-disable-next-line no-console
      console.log(devtoolsProbe)
      // eslint-disable-next-line no-console
      console.clear()
    } catch (err) {
      // 忽略
    }
    if (probeTriggered) return true

    // 3) 窗口尺寸差兜底：宽高需同时异常，避免系统缩放/侧栏误判
    const w = window.outerWidth - window.innerWidth
    const h = window.outerHeight - window.innerHeight
    return w > 160 && h > 160
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
    document.addEventListener('input', onInputCapture, true)
    document.addEventListener('compositionstart', onCompositionStart, true)
    document.addEventListener('compositionend', onCompositionEnd, true)
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
    document.removeEventListener('input', onInputCapture, true)
    document.removeEventListener('compositionstart', onCompositionStart, true)
    document.removeEventListener('compositionend', onCompositionEnd, true)
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
    composing = false
    compositionEndedAt = 0
    contentHidden.value = false
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
    contentHidden,
    startTracking,
    stopTracking,
    enterFullscreen,
    exitFullscreen,
    flush
  }
}