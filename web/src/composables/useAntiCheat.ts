import { onBeforeUnmount, ref } from 'vue'
import type { BehaviorEventPayload } from '../api/modules/assessment'
import { diffAnswerText } from '../utils/answerEditDiff'

export interface AntiCheatCallbacks {
  reportEvents: (events: BehaviorEventPayload[]) => void | Promise<void>
  onFullscreenExit?: (count: number) => void
  onMaxViolations?: () => void
}

// getRandomValues also works on an HTTP LAN origin, unlike randomUUID.
function eventId(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6]! & 15) | 64
  bytes[8] = (bytes[8]! & 63) | 128
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

export function useAntiCheat(options: { maxFullscreenExits?: number; enforceFullscreen?: boolean } = {}) {
  let enforceFullscreen = options.enforceFullscreen ?? true
  const fullscreenActive = ref(false)
  const fullscreenExitCount = ref(0)
  const blockedActionCount = ref(0)
  const contentHidden = ref(false)
  let tracking = false
  let disposed = false
  let timer: number | undefined
  let flushing = false
  let storageKey = ''
  let sessionId = ''
  let attemptId: string | null = null
  let callbacks: AntiCheatCallbacks = { reportEvents: () => {} }
  const queue: BehaviorEventPayload[] = []
  // An event which may have reached the server must never be edited on retry.
  const sealed = new Set<string>()
  let questionId: string | null = null
  let questionStartedAt: number | null = null
  let away: { id: string; startedAt: number } | null = null
  let copiedText: string | null = null
  const snapshots = new WeakMap<Element, string>()
  const now = () => performance.now()
  const activePage = () => !document.hidden && document.hasFocus() && !away
  const canCountDwell = () => activePage() && (!enforceFullscreen || fullscreenActive.value)

  function persist() {
    if (!storageKey) return
    try {
      if (queue.length) localStorage.setItem(storageKey, JSON.stringify(queue))
      else localStorage.removeItem(storageKey)
    } catch { /* A full/disabled localStorage does not stop answering or HTTP retries. */ }
  }

  function push(event_type: string, payload: Record<string, any> = {}) {
    const previous = queue.at(-1)
    const old = previous?.payload
    if (event_type === 'answer_edit' && previous?.event_type === event_type && old &&
        previous.event_id && !sealed.has(previous.event_id) && old.question_id === payload.question_id &&
        old.field === payload.field && old.input_method === payload.input_method &&
        old.operation === 'insert' && payload.operation === 'insert' &&
        Number(old.position) + Number(old.inserted_chars) === Number(payload.position) &&
        Number(old.inserted_chars) + Number(payload.inserted_chars) <= 4000) {
      old.inserted_chars += payload.inserted_chars
      old.inserted_text = String(old.inserted_text || '') + String(payload.inserted_text || '')
      old.current_length = payload.current_length
      previous.occurred_at = new Date().toISOString()
    } else {
      // Prefer retaining environment events over verbose edit/dwell telemetry.
      if (queue.length >= 1000) {
        const index = queue.findIndex(e => !sealed.has(e.event_id || '') &&
          ['answer_edit', 'question_dwell'].includes(e.event_type))
        if (index >= 0) queue.splice(index, 1)
        else if (event_type === 'answer_edit' || event_type === 'question_dwell') return
        else if (queue.length >= 2000) return
      }
      queue.push({ event_id: eventId(), event_type, payload, occurred_at: new Date().toISOString() })
    }
    persist()
  }

  async function flush() {
    if (flushing || !queue.length) return
    flushing = true
    const batch = queue.slice(0, 200)
    batch.forEach(e => { if (e.event_id) sealed.add(e.event_id) })
    try {
      await callbacks.reportEvents(batch)
      queue.splice(0, batch.length)
      batch.forEach(e => { if (e.event_id) sealed.delete(e.event_id) })
      persist()
    } catch { /* Keep the exact event IDs and payloads for the next retry. */ }
    finally { flushing = false }
    if (!tracking && queue.length && !disposed) {
      timer = window.setTimeout(() => { void flush() }, 5000)
    }
  }

  function commitDwell() {
    if (questionStartedAt === null || !questionId) return
    const duration = Math.max(0, Math.round(now() - questionStartedAt))
    questionStartedAt = now()
    if (duration >= 300) push('question_dwell', { question_id: questionId, duration_ms: duration })
  }

  function leave(reason: string) {
    if (!tracking || away) return
    commitDwell()
    questionStartedAt = null
    away = { id: eventId(), startedAt: now() }
    contentHidden.value = true
    push('page_leave', { episode_id: away.id, reason, question_id: questionId })
    void flush()
  }

  function returnToPage() {
    if (!tracking || document.hidden || !document.hasFocus()) return
    if (away) {
      push('page_return', { episode_id: away.id, duration_ms: Math.round(now() - away.startedAt) })
      away = null
    }
    contentHidden.value = false
    if (questionStartedAt === null && canCountDwell()) questionStartedAt = now()
  }

  const onBlur = () => leave('blur')
  const onVisibility = () => document.hidden ? leave('hidden') : returnToPage()
  const onPageHide = () => { leave('pagehide'); void flush() }

  function fieldElement(target: EventTarget | null): HTMLElement | null {
    return target instanceof Element ? target.closest<HTMLElement>('[data-ac-question]') : null
  }
  function selectedText(target: EventTarget | null) {
    if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) {
      return target.value.slice(target.selectionStart ?? 0, target.selectionEnd ?? 0)
    }
    return document.getSelection()?.toString() || ''
  }
  const onCopy = (e: ClipboardEvent) => {
    // Permit ordinary editing and copying samples; only text copied in this page is trusted for re-paste.
    copiedText = selectedText(e.target) || null
  }
  function blockInsertion(e: Event, type: string) {
    if (e.defaultPrevented) return
    e.preventDefault()
    e.stopPropagation()
    blockedActionCount.value += 1
    push(type, { question_id: fieldElement(e.target)?.dataset.acQuestion ?? questionId })
  }
  const isTestInput = (target: EventTarget | null) => target instanceof Element &&
    !!target.closest('[data-ac-field="stdin"], [data-ac-field="selftest"]')
  const onPaste = (e: ClipboardEvent) => {
    if (isTestInput(e.target)) return
    const text = e.clipboardData?.getData('text/plain')
    if (copiedText !== null && text === copiedText) return
    blockInsertion(e, 'blocked_paste')
  }
  const onDrop = (e: DragEvent) => {
    if (isTestInput(e.target)) return
    if (copiedText !== null && e.dataTransfer?.getData('text/plain') === copiedText) return
    blockInsertion(e, 'blocked_drop')
  }
  const onDragStart = (e: DragEvent) => { copiedText = selectedText(e.target) || null }

  function baseline(e: FocusEvent) {
    const el = e.target
    if (el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) snapshots.set(el, el.value)
  }
  function onInput(e: Event) {
    const el = e.target
    if (!(el instanceof HTMLTextAreaElement || el instanceof HTMLInputElement) ||
        el.closest('[data-code-editor]') || !el.dataset.acQuestion || isTestInput(el)) return
    if ((e as InputEvent).isComposing) return
    const previous = snapshots.get(el) ?? ''
    snapshots.set(el, el.value)
    const diff = diffAnswerText(previous, el.value)
    if (diff.operation === 'none') return
    const inputType = (e as InputEvent).inputType || ''
    recordEditorEdit(el.dataset.acQuestion, {
      field: el.dataset.acField,
      operation: diff.operation, position: diff.position,
      input_method: inputType.startsWith('history') ? 'history' : inputType.includes('Composition') ? 'ime' : 'typing',
      inserted_text: diff.insertedText.slice(0, 4000), deleted_text: diff.deletedText.slice(0, 4000),
      inserted_chars: diff.insertedText.length, deleted_chars: diff.deletedText.length,
      previous_length: previous.length, current_length: el.value.length
    })
  }

  function recordEditorEdit(qid: string, detail: Record<string, any>) {
    if (tracking) push('answer_edit', { ...detail, question_id: qid, field: detail.field || 'code' })
  }

  async function enterFullscreen(): Promise<boolean> {
    if (!enforceFullscreen) { fullscreenActive.value = true; return true }
    try {
      if (!document.fullscreenElement) await document.documentElement.requestFullscreen({ navigationUI: 'hide' })
    } catch {
      fullscreenActive.value = false
      if (tracking) push('fullscreen_denied', { reason: 'rejected_or_unsupported' })
      return false
    }
    fullscreenActive.value = !!document.fullscreenElement
    return fullscreenActive.value
  }
  function onFullscreenChange() {
    const wasActive = fullscreenActive.value
    fullscreenActive.value = !!document.fullscreenElement
    if (!tracking || !enforceFullscreen || wasActive === fullscreenActive.value) return
    if (fullscreenActive.value) {
      push('fullscreen_enter')
      if (canCountDwell()) questionStartedAt = now()
    }
    else {
      commitDwell()
      questionStartedAt = null
      fullscreenExitCount.value += 1
      push('fullscreen_exit', { count: fullscreenExitCount.value })
      void flush()
      callbacks.onFullscreenExit?.(fullscreenExitCount.value)
      if (fullscreenExitCount.value >= (options.maxFullscreenExits ?? 3)) callbacks.onMaxViolations?.()
    }
  }

  const listeners: Array<[EventTarget, string, EventListener]> = [
    [document, 'paste', onPaste as EventListener], [document, 'copy', onCopy as EventListener],
    [document, 'cut', onCopy as EventListener], [document, 'drop', onDrop as EventListener],
    [document, 'dragstart', onDragStart as EventListener], [document, 'input', onInput],
    [document, 'focusin', baseline as EventListener], [document, 'fullscreenchange', onFullscreenChange],
    [document, 'visibilitychange', onVisibility], [window, 'blur', onBlur],
    [window, 'focus', returnToPage], [window, 'pagehide', onPageHide]
  ]

  function startTracking(sid: string, aid: string | null, nextCallbacks: AntiCheatCallbacks) {
    if (tracking) return
    tracking = true
    callbacks = nextCallbacks
    sessionId = sid
    attemptId = aid
    storageKey = `sp_exam_events:${localStorage.getItem('sp_username') || ''}:${aid || sid}`
    if (!queue.length) {
      try {
        const saved = JSON.parse(localStorage.getItem(storageKey) || '[]')
        if (Array.isArray(saved)) saved.slice(0, 2000).forEach(e => {
          if (typeof e.event_id === 'string' && typeof e.event_type === 'string') {
            queue.push(e); sealed.add(e.event_id)
          }
        })
      } catch { /* Ignore a corrupt local event cache. */ }
    }
    // Capture window blur would also catch every input/editor focus change.
    listeners.forEach(([target, type, fn]) => target.addEventListener(type, fn, target !== window))
    fullscreenActive.value = !enforceFullscreen || !!document.fullscreenElement
    questionStartedAt = canCountDwell() ? now() : null
    push('session_start', { session_id: sessionId, attempt_id: attemptId })
    timer = window.setInterval(() => { commitDwell(); void flush() }, 5000)
    void flush()
  }
  function stopTracking() {
    if (!tracking) return
    commitDwell()
    push('session_end', { session_id: sessionId, attempt_id: attemptId })
    tracking = false
    window.clearInterval(timer)
    listeners.forEach(([target, type, fn]) => target.removeEventListener(type, fn, target !== window))
    questionStartedAt = null
    away = null
    contentHidden.value = false
    copiedText = null
    void flush()
  }
  function setCurrentQuestion(qid: string | null) {
    if (questionId === qid) return
    commitDwell()
    questionId = qid
    questionStartedAt = tracking && canCountDwell() ? now() : null
  }
  async function exitFullscreen() {
    try { if (document.fullscreenElement) await document.exitFullscreen() } catch { /* Browser already left. */ }
  }
  onBeforeUnmount(() => { disposed = true; stopTracking(); window.clearTimeout(timer) })
  return {
    fullscreenActive, fullscreenExitCount, blockedActionCount, contentHidden,
    startTracking, stopTracking, enterFullscreen, exitFullscreen, setCurrentQuestion,
    setEnforceFullscreen: (value: boolean) => { enforceFullscreen = value }, recordEditorEdit, flush
  }
}
