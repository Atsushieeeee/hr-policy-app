import { ApiError } from '../useApi'
import type { FaqSource } from './useFaqCandidates'

export type FaqStatus = 'draft' | 'published' | 'needs_review'

export type Faq = {
  id: number
  question: string
  answer: string
  sources: FaqSource[]
  status: FaqStatus
  status_label: string
  sort_order: number
  view_count: number
  created_at: string
  updated_at: string
}

type Page = {
  count: number
  results: Faq[]
}

// 並べ替えを画面で行うため、一覧は1回で全件（上限100件）を取得する
const PAGE_SIZE = 100

const messageOf = (e: unknown) => (e instanceof ApiError ? e.message : '予期しないエラーが発生しました')

// FAQの一覧と、登録・編集・公開・削除。操作の失敗は、呼び出し側が表示できるよう、例外のまま投げる。
export const useFaqs = () => {
  const { request, post, patch, del } = useApi()

  const items = ref<Faq[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let latest = 0

  const load = async (status: FaqStatus | null = null) => {
    const current = ++latest
    loading.value = true
    error.value = null
    const query = new URLSearchParams({ page_size: String(PAGE_SIZE) })
    if (status) query.set('status', status)
    try {
      const data = await request<Page>(`/admin/faqs?${query}`)
      if (current !== latest) return
      items.value = data.results
      total.value = data.count
    } catch (e) {
      if (current !== latest) return
      error.value = messageOf(e)
    } finally {
      if (current === latest) loading.value = false
    }
  }

  const create = (body: { question: string; answer: string; source_message_id?: number }) =>
    post<Faq>('/admin/faqs', body)

  const update = (id: number, body: Partial<Pick<Faq, 'question' | 'answer' | 'sort_order'>> & { status?: 'draft' | 'published' }) =>
    patch<Faq>(`/admin/faqs/${id}`, body)

  const remove = (id: number) => del(`/admin/faqs/${id}`)

  const publishReviewed = () => post<{ count: number }>('/admin/faqs/publish-reviewed', {})

  return { items, total, loading, error, load, create, update, remove, publishReviewed, messageOf }
}
