import { defineStore } from 'pinia'
import { ref } from 'vue'
import { moduleApi, type FeatureModule } from '../api/modules/module'

export const useModuleStore = defineStore('module', () => {
  const modules = ref<FeatureModule[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const res = await moduleApi.getMyModules()
      modules.value = res.data || []
      loaded.value = true
    } catch {
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  function isVisible(code: string) {
    const m = modules.value.find((x) => x.code === code)
    if (!m) return true
    return m.enabled && m.visible
  }

  return { modules, loaded, loading, load, isVisible }
})