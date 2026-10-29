import { ApiError } from '../useApi'

export type AdminUser = {
  id: number
  name: string
  email: string
  created_at: string
}

type Page = {
  count: number
  page: number
  page_size: number
  results: AdminUser[]
}

const toMessage = (e: unknown) => (e instanceof ApiError ? e.message : '予期しないエラーが発生しました')

// 管理者の一覧と、管理者権限の解除。
export const useAdminUsers = () => {
  const { request, post } = useApi()

  const items = ref<AdminUser[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async (page: number, pageSize: number) => {
    loading.value = true
    error.value = null
    try {
      const data = await request<Page>(`/admin/admins?page=${page}&page_size=${pageSize}`)
      items.value = data.results
      total.value = data.count
    } catch (e) {
      // 範囲外のページ（最後のページの人を全員外した直後など）は、空の一覧として扱う
      if (e instanceof ApiError && e.status === 404) {
        items.value = []
      } else {
        error.value = toMessage(e)
      }
    } finally {
      loading.value = false
    }
  }

  // 成功したかどうかを返す。失敗したときの理由は、error に入る
  const revoke = async (userIds: number[]): Promise<boolean> => {
    error.value = null
    try {
      await post('/admin/admins/revoke', { user_ids: userIds })
      return true
    } catch (e) {
      error.value = toMessage(e)
      return false
    }
  }

  return { items, total, loading, error, load, revoke }
}
