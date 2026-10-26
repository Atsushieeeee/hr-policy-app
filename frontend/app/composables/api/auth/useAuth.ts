import { ApiError } from '../useApi'
import type { AuthUser } from '~/stores/auth'

type LoginResponse = {
  access: string
  user: AuthUser
}

// ページを開いたときの復元は、同時に何度呼ばれても1回だけ行う
let restoring: Promise<void> | null = null

export const useAuth = () => {
  const { request, post } = useApi()
  const store = useAuthStore()

  const error = ref<string | null>(null)
  const loading = ref(false)

  // 成功したかどうかを返す（画面側が、成功時だけ画面を移動するなどに使う）
  const login = async (email: string, password: string): Promise<boolean> => {
    loading.value = true
    error.value = null
    try {
      const data = await post<LoginResponse>('/auth/login', { email, password }, { skipAuth: true })
      store.setSession(data.user, data.access)
      return true
    } catch (e) {
      error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
      return false
    } finally {
      loading.value = false
    }
  }

  const logout = async () => {
    try {
      await post('/auth/logout', {}, { skipAuth: true })
    } catch {
      // サーバー側の失敗でも、この端末のログイン状態は消す
    } finally {
      store.clear()
    }
  }

  // ページの再読み込み後も、リフレッシュトークン（Cookie）でログイン状態を復元する
  const restore = (): Promise<void> => {
    if (store.restored) return Promise.resolve()
    restoring ??= (async () => {
      try {
        if (await refreshAccessToken()) {
          store.setUser(await request<AuthUser>('/me'))
        }
      } catch {
        store.clear()
      } finally {
        store.markRestored()
        restoring = null
      }
    })()
    return restoring
  }

  return { error, loading, login, logout, restore }
}
