<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Annotation, Compartment, EditorState, Transaction } from '@codemirror/state'
import { EditorView, drawSelection, dropCursor, highlightActiveLine, highlightActiveLineGutter, keymap, lineNumbers, rectangularSelection } from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { bracketMatching, defaultHighlightStyle, foldGutter, foldKeymap, indentOnInput, indentUnit, syntaxHighlighting } from '@codemirror/language'
import { closeBrackets, closeBracketsKeymap } from '@codemirror/autocomplete'
import { highlightSelectionMatches, search, searchKeymap } from '@codemirror/search'
import { python } from '@codemirror/lang-python'
import { java } from '@codemirror/lang-java'
import { cpp } from '@codemirror/lang-cpp'
import { javascript } from '@codemirror/lang-javascript'

const props = withDefaults(defineProps<{
  modelValue: string
  language: string
  documentId: string
  disabled?: boolean
}>(), { disabled: false })
const emit = defineEmits<{
  'update:modelValue': [value: string]
  save: []
  edit: [detail: {
    operation: string; input_method: string; inserted_chars: number; deleted_chars: number
    current_length: number; position: number; inserted_text: string; deleted_text: string
  }]
}>()
const host = ref<HTMLDivElement | null>(null)
const cursor = ref('1:1')
const languageConfig = new Compartment()
const editableConfig = new Compartment()
const externalChange = Annotation.define<boolean>()
const documents = new Map<string, { state: EditorState; top: number; left: number }>()
let view: EditorView | undefined
let activeId = ''
let activeLanguage = ''
let activeDisabled = false

const languageExtension = () => {
  if (props.language === 'java') return java()
  if (props.language === 'c' || props.language === 'cpp') return cpp()
  if (props.language === 'javascript') return javascript()
  return python()
}
const editableExtension = () => [EditorState.readOnly.of(props.disabled), EditorView.editable.of(!props.disabled)]
const updateCursor = () => {
  if (!view) return
  const head = view.state.selection.main.head
  const line = view.state.doc.lineAt(head)
  cursor.value = `${line.number}:${head - line.from + 1}`
}
function createState() {
  return EditorState.create({
    doc: props.modelValue,
    extensions: [
      lineNumbers(), highlightActiveLineGutter(), history(), drawSelection(), dropCursor(),
      rectangularSelection(), indentOnInput(), bracketMatching(), closeBrackets(),
      foldGutter(), highlightActiveLine(), highlightSelectionMatches(), search({ top: true }),
      syntaxHighlighting(defaultHighlightStyle), indentUnit.of('    '), EditorState.tabSize.of(4),
      languageConfig.of(languageExtension()), editableConfig.of(editableExtension()),
      EditorView.contentAttributes.of({ 'aria-label': '代码编辑器', spellcheck: 'false', autocapitalize: 'off' }),
      keymap.of([
        { key: 'Mod-s', preventDefault: true, run: () => { if (!props.disabled) emit('save'); return true } },
        indentWithTab, ...closeBracketsKeymap, ...defaultKeymap, ...searchKeymap, ...historyKeymap, ...foldKeymap
      ]),
      EditorView.updateListener.of(update => {
        updateCursor()
        if (!update.docChanged || update.transactions.every(tr => tr.annotation(externalChange))) return
        emit('update:modelValue', update.state.doc.toString())
        for (const tr of update.transactions) {
          if (!tr.docChanged || tr.annotation(externalChange)) continue
          let inserted = 0, deleted = 0, position = 0, insertedText = '', deletedText = ''
          let first = true
          tr.changes.iterChanges((from, to, _fromB, _toB, text) => {
            if (first) { position = from; first = false }
            inserted += text.length
            deleted += to - from
            insertedText = (insertedText + text.toString()).slice(0, 4000)
            deletedText = (deletedText + tr.startState.doc.sliceString(from, to)).slice(0, 4000)
          })
          const event = tr.annotation(Transaction.userEvent) || ''
          const inputMethod = event.startsWith('undo') || event.startsWith('redo') ? 'history'
            : event.includes('paste') ? 'paste' : event.includes('compose') ? 'ime'
              : event === 'input.type' ? 'typing' : event.startsWith('delete') ? 'delete' : 'editor_assist'
          emit('edit', {
            operation: inserted && deleted ? 'replace' : inserted ? 'insert' : 'delete', input_method: inputMethod,
            inserted_chars: inserted, deleted_chars: deleted, current_length: tr.newDoc.length,
            position, inserted_text: insertedText, deleted_text: deletedText
          })
        }
      })
    ]
  })
}

function sync() {
  if (!view) return
  let switched = false
  if (activeId !== props.documentId) {
    documents.set(activeId, { state: view.state, top: view.scrollDOM.scrollTop, left: view.scrollDOM.scrollLeft })
    const previous = documents.get(props.documentId)
    activeId = props.documentId
    view.setState(previous?.state ?? createState())
    view.scrollDOM.scrollTop = previous?.top ?? 0
    view.scrollDOM.scrollLeft = previous?.left ?? 0
    switched = true
  }
  // Reconfiguration preserves per-question undo history and selection.
  if (switched || activeLanguage !== props.language || activeDisabled !== props.disabled) {
    view.dispatch({ effects: [languageConfig.reconfigure(languageExtension()), editableConfig.reconfigure(editableExtension())] })
    activeLanguage = props.language
    activeDisabled = props.disabled
  }
  if (view.state.doc.toString() !== props.modelValue) {
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: props.modelValue },
      annotations: [externalChange.of(true), Transaction.addToHistory.of(false)]
    })
  }
  updateCursor()
}
watch(() => [props.documentId, props.modelValue, props.language, props.disabled], sync)
onMounted(() => {
  activeId = props.documentId
  activeLanguage = props.language
  activeDisabled = props.disabled
  view = new EditorView({ state: createState(), parent: host.value! })
  updateCursor()
})
onBeforeUnmount(() => { view?.destroy(); documents.clear() })
</script>

<template>
  <div data-code-editor class="code-editor-shell">
    <div ref="host" class="code-editor-host" />
    <div class="code-editor-status">
      <span>行:列 {{ cursor }}</span><span>空格: 4</span>
      <span class="ml-auto">Ctrl+F 查找 · Ctrl+S 保存 · Esc 后 Tab 移出编辑器</span>
    </div>
  </div>
</template>

<style scoped>
.code-editor-shell { display: flex; flex-direction: column; min-height: 180px; height: 100%; min-width: 0; background: #fff; }
.code-editor-host { flex: 1; min-height: 0; overflow: hidden; }
.code-editor-host :deep(.cm-editor) { height: 100%; font-size: 14px; }
.code-editor-host :deep(.cm-scroller) { overflow: auto; font-family: Consolas, 'Courier New', monospace; line-height: 1.65; }
.code-editor-host :deep(.cm-content) { padding: 12px 0; }
.code-editor-host :deep(.cm-gutters) { background: #f8fafc; color: #94a3b8; border-right: 1px solid #e2e8f0; }
.code-editor-host :deep(.cm-activeLine), .code-editor-host :deep(.cm-activeLineGutter) { background: #eff6ff80; }
.code-editor-host :deep(.cm-focused) { outline: none; }
.code-editor-host :deep(.cm-panels) { font-size: 12px; }
.code-editor-host :deep(.cm-search) { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; padding: 8px 28px 8px 8px; }
.code-editor-host :deep(.cm-textfield) { max-width: 100%; border: 1px solid #cbd5e1; border-radius: 4px; padding: 3px 6px; }
.code-editor-status { display: flex; flex-wrap: wrap; gap: 12px; padding: 5px 12px; font-size: 10px; color: #64748b; background: #f8fafc; border-top: 1px solid #e2e8f0; }
:global(.dark) .code-editor-shell { background: #18181b; color: #e4e4e7; }
:global(.dark) .code-editor-host :deep(.cm-gutters), :global(.dark) .code-editor-status { background: #18181b; color: #a1a1aa; border-color: #3f3f46; }
:global(.dark) .code-editor-host :deep(.cm-activeLine), :global(.dark) .code-editor-host :deep(.cm-activeLineGutter) { background: #27272a; }
:global(.dark) .code-editor-host :deep(.cm-cursor) { border-left-color: #fafafa; }
:global(.dark) .code-editor-host :deep(.cm-selectionBackground) { background: #1e40af !important; }
</style>
