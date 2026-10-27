<script setup lang="ts">
import { useWebSocket } from './composables/useWebSocket'
import { examNavigationUnavailable } from './utils/examNavigation'
const retryExamStatus = () => window.location.reload()

useWebSocket()
</script>

<template>
  <div v-if="examNavigationUnavailable" class="fixed inset-0 flex flex-col items-center justify-center bg-zinc-950 p-6 text-center text-white">
    <p>暂时无法确认考试状态，请恢复内网连接后继续。</p>
    <button class="mt-6 rounded bg-blue-600 px-6 py-3" @click="retryExamStatus">继续答题</button>
  </div>
  <router-view v-else />
</template>

<style>
/* Global resets if needed */
html, body, #app {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
}
</style>
