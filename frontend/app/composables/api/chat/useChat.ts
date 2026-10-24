import { ApiError } from '../useApi'

export type ChatSource = {
  article: string
  page: number | null
}

export type ChatAnswer = {
  answer: string
  found: boolean
  sources: ChatSource[]
}

export const useChat = () => {
  const { post } = useApi()

  const result = ref<ChatAnswer | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  // 成功したかどうかを返す（画面側が、成功時だけ入力欄を空にするなどに使う）
  const ask = async (question: string): Promise<boolean> => {
    loading.value = true
    error.value = null
    try {
      result.value = await post<ChatAnswer>('/chat/messages', { question })
      return true
    } catch (e) {
      result.value = null
      error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
      return false
    } finally {
      loading.value = false
    }
  }

  const reset = () => {
    result.value = null
    error.value = null
  }

  return { result, error, loading, ask, reset }
}
