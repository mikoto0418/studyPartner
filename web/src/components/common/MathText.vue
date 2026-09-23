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

// 单 $ 行内公式的识别规则。不能要求「必须含字母」——$0.5$、$3$、$1:2$
// 是数学卷面的常见形态，误拒会让学生看到带 $ 的裸文本。真正的误判来自
// "$100 到 $200" 这类跨文本匹配：靠「含空格」和「含中日韩文字/全角标点」
// 两条排除，两者覆盖了绝大多数非公式场景。
const INLINE_DOLLAR_RE = /\$([^$\n]*?)\$/g

// 中日韩文字与全角标点（CJK 统一表意文字、CJK 标点、全角字符）
const CJK_RE = /[一-鿿　-〿＀-￯]/

function looksLikeInlineMath(inner: string): boolean {
  if (/[\\^_{}]/.test(inner)) return true
  if (/\s/.test(inner)) return false
  if (!inner.length || inner.length > 32) return false
  if (CJK_RE.test(inner)) return false
  return true
}

const MATH_RE = /\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$/g

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

  type Hit = { start: number; end: number; raw: string; block: boolean }
  const hits: Hit[] = []

  // 块级公式：\[...\]、\(...\)、$$...$$
  MATH_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = MATH_RE.exec(source)) !== null) {
    hits.push({ start: m.index, end: m.index + m[0].length, raw: m[0], block: true })
  }

  // 行内 $...$：用 looksLikeInlineMath 排除金额类文本（见上方规则说明）
  INLINE_DOLLAR_RE.lastIndex = 0
  let im: RegExpExecArray | null
  while ((im = INLINE_DOLLAR_RE.exec(source)) !== null) {
    if (!looksLikeInlineMath(im[1])) {
      // 不像公式就只跳过这个 $，从下一字符重试；
      // 否则「价格 $100，公式 $x^2$」里被拒的 $ 会吞掉后面公式的开头。
      INLINE_DOLLAR_RE.lastIndex = im.index + 1
      continue
    }
    hits.push({ start: im.index, end: im.index + im[0].length, raw: im[0], block: false })
  }

  // 同一位置块级优先；按起点排序后顺序输出，与前一个命中重叠的丢弃
  hits.sort((a, b) => a.start - b.start || Number(b.block) - Number(a.block))

  const out: Seg[] = []
  let last = 0
  for (const hit of hits) {
    if (hit.start < last) continue
    if (hit.start > last) out.push({ type: 'text', text: source.slice(last, hit.start) })
    out.push(renderMath(hit.raw))
    last = hit.end
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