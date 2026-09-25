<script setup lang="ts">
import { computed } from 'vue'
import { Plus, Trash2 } from 'lucide-vue-next'
import RichStem from './RichStem.vue'

const props = defineProps<{
  item: any
  index: number
}>()

const typeOptions = [
  { value: 'single', label: '单选题' },
  { value: 'multiple', label: '多选题' },
  { value: 'judge', label: '判断题' },
  { value: 'fill', label: '填空题' },
  { value: 'short', label: '简答题' },
  { value: 'essay', label: '论述题' }
]

const isChoice = computed(() => ['single', 'multiple', 'judge'].includes(props.item.question_type))
const isJudge = computed(() => props.item.question_type === 'judge')
const scoreUnset = computed(() => props.item.score === null || props.item.score === undefined)

function addOption() {
  if (!Array.isArray(props.item.options)) props.item.options = []
  const key = String.fromCharCode(65 + props.item.options.length)
  props.item.options.push({ key, text: '' })
}

function removeOption(idx: number) {
  props.item.options.splice(idx, 1)
  props.item.options.forEach((opt: any, i: number) => {
    opt.key = String.fromCharCode(65 + i)
  })
}

function onScoreInput(e: Event) {
  const raw = (e.target as HTMLInputElement).value
  props.item.score = raw === '' ? null : Number(raw)
}
</script>

<template>
  <div class="minimal-card bg-white p-5 dark:bg-zinc-900">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-3">
        <span class="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-sm font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
          {{ index + 1 }}
        </span>
        <select v-model="item.question_type" class="ui-field w-32">
          <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
        <label class="flex items-center gap-2 text-xs text-gray-500 dark:text-zinc-400">
          <span>分值</span>
          <input
            type="number"
            min="0"
            step="0.5"
            class="ui-field w-24"
            :class="scoreUnset ? 'border-amber-300 dark:border-amber-900' : ''"
            placeholder="未设置"
            :value="item.score ?? ''"
            @input="onScoreInput"
          />
          <span v-if="scoreUnset" class="text-[10px] font-semibold text-amber-500">待填</span>
        </label>
      </div>
      <button class="ui-button-danger" @click="$emit('remove', index)">
        <Trash2 class="h-3.5 w-3.5" />
        <span>删除</span>
      </button>
    </div>

    <div class="space-y-4">
      <div>
        <label class="ui-field-label mb-1">题干</label>
        <textarea
          v-model="item.stem"
          class="ui-field"
          rows="2"
          placeholder="题干内容，支持 LaTeX 公式"
        />
        <div
          v-if="item.stem"
          class="mt-2 rounded-lg border border-dashed border-gray-200 bg-gray-50/60 p-3 dark:border-zinc-700 dark:bg-zinc-950/40"
        >
          <div class="mb-1 text-[10px] text-gray-400">预览</div>
          <RichStem :stem="item.stem" :images="item.stem_images" />
        </div>
      </div>

      <div v-if="isChoice" class="space-y-2">
        <label class="ui-field-label">选项</label>
        <div v-for="(opt, oi) in item.options" :key="oi" class="flex items-center gap-2">
          <span class="w-5 flex-shrink-0 text-xs font-semibold text-gray-400">{{ opt.key }}</span>
          <input v-model="opt.text" class="ui-field" />
          <button class="ui-icon-button h-8 w-8 flex-shrink-0" title="删除选项" @click="removeOption(Number(oi))">
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
        <button class="ui-button-secondary" @click="addOption">
          <Plus class="h-3.5 w-3.5" />
          <span>添加选项</span>
        </button>
      </div>

      <div>
        <label class="ui-field-label mb-1">答案</label>
        <select v-if="isJudge" v-model="item.answer" class="ui-field">
          <option value="true">正确</option>
          <option value="false">错误</option>
        </select>
        <input v-else v-model="item.answer" class="ui-field" placeholder="选择题填选项字母，其余填参考答案" />
      </div>

      <div>
        <label class="ui-field-label mb-1">解析（可选）</label>
        <textarea v-model="item.analysis" class="ui-field" rows="2" placeholder="答案解析" />
      </div>
    </div>
  </div>
</template>
