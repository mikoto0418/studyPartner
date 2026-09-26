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
  { value: 'essay', label: '论述题' },
  { value: 'code', label: '编程题' }
]

const isChoice = computed(() => ['single', 'multiple', 'judge'].includes(props.item.question_type))
const isJudge = computed(() => props.item.question_type === 'judge')
const isCode = computed(() => props.item.question_type === 'code')
const scoreUnset = computed(() => props.item.score === null || props.item.score === undefined)

const codeLanguages = [
  { value: 'python', label: 'Python 3' },
  { value: 'javascript', label: 'JavaScript (Node)' },
  { value: 'java', label: 'Java 17' }
]

const testCases = computed<any[]>(() => {
  if (!Array.isArray(props.item.test_cases)) props.item.test_cases = []
  return props.item.test_cases
})

function addTestCase() {
  if (!Array.isArray(props.item.test_cases)) props.item.test_cases = []
  props.item.test_cases.push({ input: '', expected_output: '' })
}

function removeTestCase(idx: number) {
  props.item.test_cases.splice(idx, 1)
}

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
  <div class="minimal-card minimal-card-static bg-white p-5 dark:bg-zinc-900">
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

    <div class="space-y-5">
      <div>
        <label class="ui-field-label mb-1">题干</label>
        <textarea
          v-model="item.stem"
          class="ui-field"
          rows="4"
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

      <template v-if="isCode">
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="ui-field-label mb-1">编程语言</label>
            <select v-model="item.language" class="ui-field">
              <option v-for="lang in codeLanguages" :key="lang.value" :value="lang.value">{{ lang.label }}</option>
            </select>
            <p class="ui-field-help">学生只能用它作答；判题与 AI 阅卷都按该语言执行。</p>
          </div>
          <div>
            <label class="ui-field-label mb-1">起始代码（可选）</label>
            <textarea v-model="item.starter_code" class="ui-field font-mono" rows="5" placeholder="给学生预填的代码骨架" />
          </div>
        </div>

        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="ui-field-label">测试用例</label>
            <button class="ui-button-secondary" @click="addTestCase">
              <Plus class="h-3.5 w-3.5" />
              <span>添加用例</span>
            </button>
          </div>
          <p class="ui-field-help">
            用例只用于判题，不会下发给学生 —— 学生靠「自测」自己验证。程序需从标准输入读取数据、把结果打到标准输出，逐行比较（忽略行尾空白）。
          </p>
          <div
            v-for="(tc, ti) in testCases"
            :key="ti"
            class="rounded-lg border border-gray-100 p-3 dark:border-zinc-800"
          >
            <div class="mb-2 flex items-center justify-between">
              <span class="text-[10px] font-semibold text-gray-500">用例 {{ ti + 1 }}</span>
              <div class="flex items-center gap-3">
                <button class="ui-icon-button h-7 w-7" title="删除用例" @click="removeTestCase(Number(ti))">
                  <Trash2 class="h-3 w-3" />
                </button>
              </div>
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <label class="space-y-1">
                <span class="text-[10px] text-gray-400">输入</span>
                <textarea v-model="tc.input" class="ui-field font-mono" rows="3" placeholder="每行一个输入，留空表示无输入" />
              </label>
              <label class="space-y-1">
                <span class="text-[10px] text-gray-400">期望输出</span>
                <textarea v-model="tc.expected_output" class="ui-field font-mono" rows="3" placeholder="期望的标准输出" />
              </label>
            </div>
          </div>
          <p v-if="!testCases.length" class="rounded-lg border border-dashed border-gray-200 px-3 py-4 text-center text-[11px] text-gray-400 dark:border-zinc-700">
            还没有测试用例。没有用例时只能靠 AI 阅卷，无法自动判题。
          </p>
        </div>
      </template>

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

      <div v-if="!isCode">
        <label class="ui-field-label mb-1">答案</label>
        <select v-if="isJudge" v-model="item.answer" class="ui-field">
          <option value="true">正确</option>
          <option value="false">错误</option>
        </select>
        <input v-else v-model="item.answer" class="ui-field" placeholder="选择题填选项字母，其余填参考答案" />
      </div>
      <div v-else>
        <label class="ui-field-label mb-1">参考解法（可选）</label>
        <textarea
          v-model="item.answer"
          class="ui-field font-mono"
          rows="6"
          placeholder="一份可AC的标准代码，供 AI 阅卷比对思路"
        />
      </div>

      <div>
        <label class="ui-field-label mb-1">解析（可选）</label>
        <textarea v-model="item.analysis" class="ui-field" rows="3" placeholder="答案解析" />
      </div>
    </div>
  </div>
</template>
