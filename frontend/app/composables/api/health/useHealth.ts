import { ApiError } from '../useApi'

export type HealthResponse = {
  status: 'ok' | 'error'
  db: 'ok' | 'error'
}

export const useHealth = () => {
  const { request } = useApi()

  const health = ref<HealthResponse | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  const check = async () => {
    loading.value = true
    error.value = null
    try {
      health.value = await request<HealthResponse>('/healthz')
    } catch (e) {
      health.value = null
      error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
    } finally {
      loading.value = false
    }
  }

  return { health, error, loading, check }
}
