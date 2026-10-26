export type AuthUser = {
  id: number
  email: string
  name: string
  is_admin: boolean
}

// ログイン状態を保持するストア。状態だけを持ち、API呼び出しは composables/api/auth/useAuth.ts が行う。
// アクセストークンはメモリ上にだけ保持する（localStorage などには保存しない）。
export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const accessToken = ref<string | null>(null)
  // ページを開いたときの、ログイン状態の復元が終わったか
  const restored = ref(false)

  const isLoggedIn = computed(() => user.value !== null && accessToken.value !== null)
  const isAdmin = computed(() => user.value?.is_admin === true)

  const setSession = (newUser: AuthUser, token: string) => {
    user.value = newUser
    accessToken.value = token
  }

  const setUser = (newUser: AuthUser) => {
    user.value = newUser
  }

  const setAccessToken = (token: string) => {
    accessToken.value = token
  }

  const clear = () => {
    user.value = null
    accessToken.value = null
  }

  const markRestored = () => {
    restored.value = true
  }

  return {
    user,
    accessToken,
    restored,
    isLoggedIn,
    isAdmin,
    setSession,
    setUser,
    setAccessToken,
    clear,
    markRestored,
  }
})
