import { ApiError } from '../useApi'
import type { ChatSource } from './useChat'

export type PublicFaq = {
  id: number
  question: string
}

export type PublicFaqDetail = PublicFaq & {
  answer: string
  sources: ChatSource[]
}

// 社員向けの、公開中のFAQ。AIは呼ばない。管理者向けの useFaqs とは別のAPIを使う。
export const usePublicFaqs = () => {
  const { request } = useApi()

  const items = ref<PublicFaq[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const load = async () => {
    loading.value = true
    error.value = null
    try {
      items.value = await request<PublicFaq[]>('/faqs')
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
    } finally {
      loading.value = false
    }
  }

  // 詳細を開くと、サーバー側で表示回数が増える。失敗は、呼び出し側で扱う
  const fetchDetail = (id: number) => request<PublicFaqDetail>(`/faqs/${id}`)

  return { items, loading, error, load, fetchDetail }
}
