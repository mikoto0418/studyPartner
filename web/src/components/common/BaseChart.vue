<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer
])

const props = withDefaults(
  defineProps<{
    option: EChartsOption
    height?: string
    /** 数据为空时展示的占位文案 */
    emptyText?: string
    isEmpty?: boolean
  }>(),
  { height: '320px', emptyText: '暂无数据', isEmpty: false }
)

const el = ref<HTMLDivElement | null>(null)
// shallowRef：echarts 实例内部结构庞大，深响应式化会拖慢渲染且无意义
const chart = shallowRef<echarts.ECharts | null>(null)
let themeObserver: MutationObserver | null = null

const isDark = () => document.documentElement.classList.contains('dark')

/** 跟随 html.dark：主题切换后必须重新 init，否则坐标轴/文字颜色会留在旧主题 */
const rebuild = () => {
  if (!el.value) return
  chart.value?.dispose()
  chart.value = echarts.init(el.value, isDark() ? 'dark' : undefined)
  chart.value.setOption(props.option, true)
}

const resize = () => chart.value?.resize()

onMounted(() => {
  rebuild()
  window.addEventListener('resize', resize)
  themeObserver = new MutationObserver(rebuild)
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['class']
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  themeObserver?.disconnect()
  themeObserver = null
  chart.value?.dispose()
  chart.value = null
})

watch(
  () => props.option,
  (next) => {
    if (!chart.value) return
    chart.value.setOption(next, true)
  },
  { deep: true }
)

// 空数据切回来时容器刚恢复可见，尺寸此前为 0，需要补一次 resize
watch(
  () => props.isEmpty,
  (empty) => {
    if (!empty) requestAnimationFrame(resize)
  }
)
</script>

<template>
  <div class="relative w-full" :style="{ height }">
    <div v-if="isEmpty" class="flex h-full items-center justify-center text-xs text-gray-400 dark:text-zinc-500">
      {{ emptyText }}
    </div>
    <div v-show="!isEmpty" ref="el" class="h-full w-full"></div>
  </div>
</template>
