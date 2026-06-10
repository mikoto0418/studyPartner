import request from '../request'

export interface LLMProviderConfigOut {
  id: string
  provider_name: string
  display_name?: string
  base_url: string
  model_name: string
  task_type: string
  priority: number
  enabled: boolean
  rpm_limit?: number
  tpm_limit?: number
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export interface LLMConfigUpsertData {
  provider_name: string
  display_name?: string
  base_url?: string
  api_key?: string
  chat_base_url: string
  chat_api_key?: string
  chat_model: string
  embedding_base_url: string
  embedding_api_key?: string
  embedding_model: string
  task_types: string[]
  enabled: boolean
  rpm_limit?: number
  tpm_limit?: number
}

export interface LLMConnectionTestData {
  provider_name: string
  base_url: string
  api_key: string
  model_name: string
  endpoint_type: 'chat' | 'embedding'
}

export interface LLMConnectionTestOut {
  provider_name: string
  model_name: string
  latency_ms: number
  ok: boolean
}

export interface LLMUsageLogOut {
  id: string
  task_type: string
  model_name: string
  total_tokens: number
  latency_ms?: number
  success: boolean
  error_message?: string
  created_at: string
}

export interface AdminOverviewOut {
  total_users: number
  llm_calls_today: number
  storage_bytes: number
  service_status: string
  recent_usage_logs: LLMUsageLogOut[]
}

export interface AdminRuntimeSettingsOut {
  app_env: string
  app_debug: boolean
  inline_scheduler_enabled: boolean
  smtp_configured: boolean
  smtp_host: string
  smtp_from_email?: string
  minio_endpoint: string
  minio_bucket_name: string
  qdrant_endpoint: string
  llm_provider_count: number
  enabled_llm_provider_count: number
}

export const adminApi = {
  listLlmConfigs() {
    return request.get('/admin/llm-configs')
  },

  saveLlmConfigs(data: LLMConfigUpsertData) {
    return request.put('/admin/llm-configs', data)
  },

  testLlmConnection(data: LLMConnectionTestData) {
    return request.post('/admin/llm-configs/test', data)
  },

  getOverview() {
    return request.get('/admin/overview')
  },

  getSettings() {
    return request.get('/admin/settings')
  }
}
