<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
const props = defineProps<{ open: boolean; busy: boolean; ready: boolean }>()
const emit = defineEmits<{ continue: [] }>()
const dialog = ref<HTMLDialogElement | null>(null)
const button = ref<HTMLButtonElement | null>(null)
function sync() {
  if (!dialog.value) return
  if (props.open && !dialog.value.open) {
    dialog.value.showModal()
    button.value?.focus()
  } else if (!props.open && dialog.value.open) dialog.value.close()
}
watch(() => props.open, sync, { flush: 'post' })
onMounted(sync)
onUnmounted(() => dialog.value?.close())
</script>

<template>
  <Teleport to="body">
    <dialog ref="dialog" class="exam-resume" aria-labelledby="exam-resume-title" @cancel.prevent @keydown.tab.prevent="button?.focus()">
      <div class="max-w-md text-center">
        <h2 id="exam-resume-title" class="text-xl font-semibold">请继续本场考试</h2>
        <p class="mt-4 text-sm leading-7 text-zinc-300">考试尚未交卷。当前页面已锁定，请恢复全屏后继续答题。</p>
        <p v-if="!ready" class="mt-2 text-sm text-zinc-300">正在核对作答状态；连接异常时，点击下方按钮重试。</p>
        <button ref="button" type="button" class="mt-7 rounded-md bg-blue-600 px-8 py-3 font-semibold text-white disabled:opacity-50" :disabled="busy" @click="emit('continue')">
          {{ busy ? '正在准备…' : '继续答题' }}
        </button>
      </div>
    </dialog>
  </Teleport>
</template>

<style scoped>
.exam-resume { position: fixed; inset: 0; margin: 0; width: 100vw; height: 100dvh; max-width: none; max-height: none; border: 0; padding: 24px; background: #09090b; color: white; }
.exam-resume[open] { display: flex; align-items: center; justify-content: center; }
.exam-resume::backdrop { background: #09090b; }
</style>
