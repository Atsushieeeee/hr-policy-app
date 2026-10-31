import { ApiError } from '../useApi'

export type AuditLog = {
  id: number
  created_at: string
  action: string
  action_label: string
  actor_email: string
  actor_name: string
  target_type: string
  target_id: string
  detail: Record<string, unknown>
  ip: string | null
}

export type AuditAction = {
  value: string
  label: string
}

type Page = {
  count: number
  page: number
  page_size: number
  actions: AuditAction[]
  results: AuditLog[]
}

// 監査ログの一覧（新しい順）。action を指定すると、その操作の種類だけに絞り込む。
export const useAuditLogs = () => {
  const { request } = useApi()

  const items = ref<AuditLog[]>([])
  const total = ref(0)
  // 絞り込みの選択肢。APIの応答から作る（定義元はバックエンド）
  const actions = ref<AuditAction[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 連続して呼ばれたとき、遅れて返った古い結果で、新しい結果を上書きしない
  let latest = 0

  const load = async (page: number, pageSize: number, action: string | null) => {
    const current = ++latest
    loading.value = true
    error.value = null
    const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (action) query.set('action', action)
    try {
      const data = await request<Page>(`/admin/audit-logs?${query}`)
      if (current !== latest) return
      items.value = data.results
      total.value = data.count
      actions.value = data.actions
    } catch (e) {
      if (current !== latest) return
      // 範囲外のページは、空の一覧として扱う
      if (e instanceof ApiError && e.status === 404) {
        items.value = []
      } else {
        error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
      }
    } finally {
      if (current === latest) loading.value = false
    }
  }

  return { items, total, actions, loading, error, load }
}
