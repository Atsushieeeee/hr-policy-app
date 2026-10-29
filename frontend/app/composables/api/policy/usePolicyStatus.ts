import { ApiError } from '../useApi'

type PolicyStatus = {
  registered: boolean
}

// 規程が登録されているか。ログイン済みなら誰でも確認できる。
export const usePolicyStatus = () => {
  const { request } = useApi()

  // 確認前は null
  const registered = ref<boolean | null>(null)
  const error = ref<string | null>(null)
  const loading = ref(false)

  const check = async () => {
    loading.value = true
    error.value = null
    try {
      registered.value = (await request<PolicyStatus>('/policy/status')).registered
    } catch (e) {
      registered.value = null
      error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
    } finally {
      loading.value = false
    }
  }

  // 質問を送ったときに、サーバーが「未登録」と返した場合など、画面の状態を合わせる
  const markNotRegistered = () => {
    registered.value = false
  }

  return { registered, error, loading, check, markNotRegistered }
}
