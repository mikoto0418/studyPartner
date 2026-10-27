const pairs: Record<string, string> = { '(': ')', '[': ']', '{': '}', "'": "'", '"': '"' }
const editing = new WeakSet<EventTarget>()
export const isCodeEditorInput = (target: EventTarget) => editing.has(target)

interface Edit {
  from: number
  to: number
  text: string
  start: number
  end: number
}

// Only lexical context needed for pairing: do not insert extra brackets inside strings/comments.
function context(text: string, python: boolean) {
  let quote = '', comment = '', escaped = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!, next = text[i + 1]
    if (comment === 'line') { if (c === '\n') comment = ''; continue }
    if (comment === 'block') { if (c === '*' && next === '/') { comment = ''; i++ }; continue }
    if (quote) {
      if (escaped) { escaped = false; continue }
      if (c === '\\') { escaped = true; continue }
      if (text.slice(i, i + quote.length) === quote) { i += quote.length - 1; quote = '' }
      continue
    }
    if ((python && c === '#') || (!python && c === '/' && next === '/')) { comment = 'line'; continue }
    if (!python && c === '/' && next === '*') { comment = 'block'; i++; continue }
    if (c === "'" || c === '"') {
      quote = python && text.slice(i, i + 3) === c.repeat(3) ? c.repeat(3) : c
      i += quote.length - 1
    }
  }
  return { quote, comment, escaped }
}

export function codeEditorEdit(value: string, start: number, end: number, key: string, shift = false, language = 'python'): Edit | null {
  const replace = (from: number, to: number, text: string, caret = from + text.length, selectionEnd = caret): Edit =>
    ({ from, to, text, start: caret, end: selectionEnd })
  const lineStart = value.slice(0, start).lastIndexOf('\n') + 1
  if (key === 'Tab') {
    if (!shift && start === end) {
      return replace(start, end, ' '.repeat(4 - (start - lineStart) % 4))
    }
    const lastPosition = end > start && value[end - 1] === '\n' ? end - 1 : end
    let lineEnd = value.indexOf('\n', lastPosition)
    if (lineEnd < 0) lineEnd = value.length
    const lines = value.slice(lineStart, lineEnd).split('\n')
    let offset = lineStart
    const changes = lines.map(line => {
      const removed = shift ? (line.startsWith('\t') ? 1 : Math.min(4, line.match(/^ */)![0].length)) : 0
      const change = { offset, removed, added: shift ? 0 : 4 }
      offset += line.length + 1
      return change
    })
    const move = (pos: number) => pos + changes.reduce((sum, c) => {
      if (pos < c.offset) return sum
      return sum + c.added - Math.min(c.removed, pos - c.offset)
    }, 0)
    const text = lines.map((line, i) => shift ? line.slice(changes[i]!.removed) : '    ' + line).join('\n')
    return replace(lineStart, lineEnd, text, move(start), move(end))
  }
  const before = value.slice(0, start), after = value.slice(end)
  const state = context(before, language === 'python')
  if (key === 'Enter') {
    const prefix = value.slice(lineStart, start)
    const base = prefix.match(/^[\t ]*/)![0]
    const trimmed = prefix.trimEnd()
    const opener = trimmed.slice(-1)
    const extra = !state.quote && ((!state.comment && ['{', '[', '('].includes(opener)) || (language === 'python' && prefix.split('#')[0]!.trimEnd().endsWith(':')))
    const indent = base + (extra ? '    ' : '')
    const close = pairs[opener]
    const betweenPair = extra && close && after.startsWith(close)
    return replace(start, end, '\n' + indent + (betweenPair ? '\n' + base : ''), start + 1 + indent.length)
  }
  if (key === 'Backspace' && start === end && start > 0 && pairs[value[start - 1]!] === value[start]) {
    return replace(start - 1, start + 1, '')
  }
  if (start === end && after[0] === key && (')]}'.includes(key) || key === state.quote) && !state.escaped && !state.comment) {
    if (!state.quote || key === state.quote) return replace(start, end, '', start + 1)
  }
  const close = pairs[key]
  if (!close || state.quote || state.comment || state.escaped) return null
  if (start !== end) return replace(start, end, key + value.slice(start, end) + close, start + 1, end + 1)
  if (after && !/^[\s)\]}:;,]/.test(after)) return null
  if ((key === "'" || key === '"') && /[\w]/.test(before.slice(-1))) return null
  return replace(start, end, key + close, start + 1)
}

export function handleCodeEditorKeydown(event: KeyboardEvent, language: string) {
  const el = event.target as HTMLTextAreaElement
  if (event.defaultPrevented || event.isComposing || event.keyCode === 229 || event.ctrlKey || event.metaKey || event.altKey || el.disabled || el.readOnly) return
  const edit = codeEditorEdit(el.value, el.selectionStart, el.selectionEnd, event.key, event.shiftKey, language)
  if (!edit) return
  event.preventDefault()
  const oldValue = el.value
  const changed = oldValue.slice(edit.from, edit.to) !== edit.text
  editing.add(el)
  try {
    if (changed) {
      el.setSelectionRange(edit.from, edit.to)
      // Chromium's native insertion keeps Ctrl+Z/Ctrl+Y history and fires the normal input/save path.
      const applied = document.execCommand('insertText', false, edit.text)
      if (!applied || el.value === oldValue) {
        el.setRangeText(edit.text, edit.from, edit.to, 'end')
        el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: edit.text }))
      }
    }
    el.setSelectionRange(edit.start, edit.end)
  } finally { editing.delete(el) }
}
