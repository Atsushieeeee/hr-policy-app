import { ApiError } from '../useApi'

export type FaqSource = {
  policy_id: number
  article: string
  page: number | null
}

export type FaqCandidate = {
  question: string
  ask_count: number
  user_count: number
  last_asked_at: string
  answer: string
  sources: FaqSource[]
  source_message_id: number
  registered: boolean
}

type Page = {
  count: number
  page: number
  page_size: number
  results: FaqCandidate[]
}

// FAQにする候補（よく聞かれている質問）の一覧。
export const useFaqCandidates = () => {
  const { request } = useApi()

  const items = ref<FaqCandidate[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // 連続して呼ばれたとき、遅れて返った古い結果で、新しい結果を上書きしない
  let latest = 0

  const load = async (page: number, pageSize: number, includeRegistered: boolean) => {
    const current = ++latest
    loading.value = true
    error.value = null
    const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (includeRegistered) query.set('include_registered', 'true')
    try {
      const data = await request<Page>(`/admin/faq-candidates?${query}`)
      if (current !== latest) return
      items.value = data.results
      total.value = data.count
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

  return { items, total, loading, error, load }
}
