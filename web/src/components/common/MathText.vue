<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps<{
  text?: string | null
}>()

type Seg =
  | { type: 'text'; text: string }
  | { type: 'math'; html: string; display: boolean }

const MATH_RE = /\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|\$[^$\n]+?\$/g

function renderMath(raw: string): Seg {
  let display = false
  let latex = raw
  if (raw.startsWith('\\[') && raw.endsWith('\\]')) {
    display = true
    latex = raw.slice(2, -2)
  } else if (raw.startsWith('\\(') && raw.endsWith('\\)')) {
    latex = raw.slice(2, -2)
  } else if (raw.startsWith('$$') && raw.endsWith('$$')) {
    display = true
    latex = raw.slice(2, -2)
  } else if (raw.startsWith('$') && raw.endsWith('$')) {
    latex = raw.slice(1, -1)
  }

  try {
    const html = katex.renderToString(latex, {
      throwOnError: false,
      displayMode: display
    })
    return { type: 'math', html, display }
  } catch {
    return { type: 'text', text: raw }
  }
}

const segments = computed<Seg[]>(() => {
  const source = props.text || ''
  if (!source) return []

  const out: Seg[] = []
  let last = 0
  let m: RegExpExecArray | null
  MATH_RE.lastIndex = 0
  while ((m = MATH_RE.exec(source)) !== null) {
    if (m.index > last) out.push({ type: 'text', text: source.slice(last, m.index) })
    out.push(renderMath(m[0]))
    last = m.index + m[0].length
  }
  if (last < source.length) out.push({ type: 'text', text: source.slice(last) })
  if (out.length === 0) out.push({ type: 'text', text: source })
  return out
})
</script>

<template>
  <span class="mathtext whitespace-pre-wrap">
    <template v-for="(seg, i) in segments" :key="i">
      <span v-if="seg.type === 'text'">{{ seg.text }}</span>
      <span
        v-else
        :class="seg.display ? 'block py-1' : 'inline-block align-middle'"
        v-html="seg.html"
      />
    </template>
  </span>
</template>