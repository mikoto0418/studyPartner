<script setup lang="ts">
import { computed } from 'vue'
import MathText from '../common/MathText.vue'

interface StemImage {
  index?: number
  url?: string
}

const props = defineProps<{
  stem: string
  images?: StemImage[] | null
}>()

const imgMap = computed(() => {
  const m: Record<number, string> = {}
  for (const im of props.images || []) {
    const i = im.index != null ? Number(im.index) : NaN
    if (!Number.isNaN(i) && im.url) m[i] = im.url
  }
  return m
})

const previewUrls = computed(() =>
  ((props.images || []) as StemImage[])
    .map((im) => im.url)
    .filter((u): u is string => !!u)
)

const segments = computed(() => {
  const parts: Array<{ type: 'text' | 'img'; text?: string; src?: string }> = []
  const text = props.stem || ''
  const re = /\[\[IMG:(\d+)\]\]/g
  let last = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push({ type: 'text', text: text.slice(last, m.index) })
    const idx = Number(m[1])
    parts.push({ type: 'img', src: imgMap.value[idx] })
    last = m.index + m[0].length
  }
  if (last < text.length) parts.push({ type: 'text', text: text.slice(last) })
  return parts
})

const hasContent = computed(() => segments.value.length > 0)
</script>

<template>
  <div v-if="hasContent" class="whitespace-pre-wrap">
    <template v-for="(seg, i) in segments" :key="i">
      <MathText v-if="seg.type === 'text'" :text="seg.text" />
      <el-image
        v-else-if="seg.src"
        :src="seg.src"
        :preview-src-list="previewUrls"
        :initial-index="previewUrls.indexOf(seg.src)"
        fit="contain"
        preview-teleported
        class="mx-1 inline-block cursor-zoom-in align-middle"
        style="width: 180px; vertical-align: middle"
      />
      <span v-else class="mx-1 text-xs text-gray-400">[图片缺失]</span>
    </template>
  </div>
</template>