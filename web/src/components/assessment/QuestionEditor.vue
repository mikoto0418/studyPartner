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
</script>

<template>
  <div class="rounded-xl border border-gray-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
    <div class="mb-3 flex items-center justify-between gap-3">
      <div class="flex items-center gap-3">
        <span class="flex h-7 w-7 items-center justify-center rounded-md bg-blue-50 text-sm font-semibold text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
          {{ index + 1 }}
        </span>
        <el-select v-model="item.question_type" class="w-36" size="small">
          <el-option v-for="t in typeOptions" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <div class="flex items-center gap-1 text-xs text-gray-500 dark:text-zinc-400">
          分值
          <el-input-number v-model="item.score" :min="0" :precision="1" size="small" class="w-24" />
        </div>
      </div>
      <el-button type="danger" plain size="small" :icon="Trash2" @click="$emit('remove', index)">删除</el-button>
    </div>

    <div class="space-y-3">
      <div>
        <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">题干</label>
        <el-input v-model="item.stem" type="textarea" :rows="2" placeholder="题干内容，支持 LaTeX 公式" />
        <div v-if="item.stem" class="mt-2 rounded-lg border border-dashed border-gray-200 bg-gray-50/60 p-3 dark:border-zinc-700 dark:bg-zinc-950/40">
          <div class="mb-1 text-[10px] text-gray-400">预览</div>
          <RichStem :stem="item.stem" :images="item.stem_images" />
        </div>
      </div>

      <div v-if="isChoice" class="space-y-2">
        <label class="block text-xs font-medium text-gray-500 dark:text-zinc-400">选项</label>
        <div v-for="(opt, oi) in item.options" :key="oi" class="flex items-center gap-2">
          <span class="w-6 text-xs font-semibold text-gray-400">{{ opt.key }}</span>
          <el-input v-model="opt.text" size="small" />
          <el-button size="small" text type="danger" :icon="Trash2" @click="removeOption(Number(oi))" />
        </div>
        <el-button size="small" text type="primary" :icon="Plus" @click="addOption">添加选项</el-button>
      </div>

      <div>
        <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">答案</label>
        <el-select v-if="isJudge" v-model="item.answer" class="w-full" size="small">
          <el-option label="正确" value="true" />
          <el-option label="错误" value="false" />
        </el-select>
        <el-input v-else v-model="item.answer" size="small" placeholder="选择题填选项字母，其余填参考答案" />
      </div>

      <div>
        <label class="mb-1 block text-xs font-medium text-gray-500 dark:text-zinc-400">解析</label>
        <el-input v-model="item.analysis" type="textarea" :rows="2" placeholder="答案解析（可选）" />
      </div>
    </div>
  </div>
</template>