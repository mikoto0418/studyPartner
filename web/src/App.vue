<script setup lang="ts">
import { useWebSocket } from './composables/useWebSocket'

useWebSocket()
</script>

<template>
  <router-view />
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
