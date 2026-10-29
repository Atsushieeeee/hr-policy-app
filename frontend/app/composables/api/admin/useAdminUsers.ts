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

// 管理者の一覧、管理者にできるユーザー（候補）の一覧、管理者権限の付与と解除。
export const useAdminUsers = () => {
  const { request, post } = useApi()

  const items = ref<AdminUser[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 連続して呼ばれたとき（検索の入力中など）、遅れて返った古い結果で、新しい結果を上書きしない
  let latest = 0

  const fetchList = async (path: string) => {
    const current = ++latest
    loading.value = true
    error.value = null
    try {
      const data = await request<Page>(path)
      if (current !== latest) return
      items.value = data.results
      total.value = data.count
    } catch (e) {
      if (current !== latest) return
      // 範囲外のページ（最後のページの人を全員外した直後など）は、空の一覧として扱う
      if (e instanceof ApiError && e.status === 404) {
        items.value = []
      } else {
        error.value = toMessage(e)
      }
    } finally {
      if (current === latest) loading.value = false
    }
  }

  const loadAdmins = (page: number, pageSize: number) =>
    fetchList(`/admin/admins?page=${page}&page_size=${pageSize}`)

  // q は、名前・メールアドレスの部分一致
  const loadCandidates = (page: number, pageSize: number, q: string) =>
    fetchList(`/admin/users?page=${page}&page_size=${pageSize}&q=${encodeURIComponent(q)}`)

  // 成功したかどうかを返す。失敗したときの理由は、error に入る
  const send = async (path: string, userIds: number[]): Promise<boolean> => {
    error.value = null
    try {
      await post(path, { user_ids: userIds })
      return true
    } catch (e) {
      error.value = toMessage(e)
      return false
    }
  }

  const grant = (userIds: number[]) => send('/admin/admins', userIds)
  const revoke = (userIds: number[]) => send('/admin/admins/revoke', userIds)

  return { items, total, loading, error, loadAdmins, loadCandidates, grant, revoke }
}
