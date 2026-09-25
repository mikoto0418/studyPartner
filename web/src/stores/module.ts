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

  /** 已加载过就复用缓存，供路由守卫在跳转前同步判定。 */
  async function ensureLoaded() {
    if (loaded.value) return
    await load()
  }

  /**
   * 侧栏入口是否显示：既要模块整体启用，也要管理员勾了「可见」。
   * 模块列表里查不到该 code 时不隐藏 —— 列表是按角色裁剪的，查不到只说明
   * 当前角色本就不涉及它，不代表被关闭。
   */
  function isVisible(code: string) {
    const m = modules.value.find((x) => x.code === code)
    if (!m) return true
    return m.enabled && m.visible
  }

  /**
   * 模块整体是否可用，用于路由拦截。
   * 「可见」只控制侧栏入口，关掉「启用」才是整体不可访问 —— 两者语义不同。
   */
  function isEnabled(code: string) {
    const m = modules.value.find((x) => x.code === code)
    if (!m) return true
    return m.enabled
  }

  /**
   * 某模块是否处于启用态，用于「内容级」显隐（而非入口级）。
   *
   * 与 isVisible 的关键区别：查不到该 code 时返回 false。模块列表按角色裁剪，
   * 学生看不到 teacher-only 的 tasks —— 若沿用 isVisible 的「查不到=不隐藏」，
   * 学生仪表盘就会一直显示导师任务卡片，管理员关掉 tasks 也不生效。
   */
  function isActive(code: string) {
    const m = modules.value.find((x) => x.code === code)
    if (!m) return false
    return m.enabled && m.visible
  }

  return { modules, loaded, loading, load, ensureLoaded, isVisible, isEnabled, isActive }
})
