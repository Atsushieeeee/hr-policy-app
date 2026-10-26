// 全ページに適用するルートガード。既定は「ログイン必須」で、ページごとに definePageMeta で例外を指定する。
//   auth: false      ログイン不要
//   admin: true      管理者権限が必要
//   guestOnly: true  ログイン済みのユーザーは開けない
// ※ これは画面の振り分け（UX）で、権限のチェックはバックエンドが行う。
export default defineNuxtRouteMiddleware(async (to) => {
  const auth = useAuthStore()
  await useAuth().restore()

  if (to.meta.guestOnly && auth.isLoggedIn) {
    return navigateTo('/chat')
  }
  if (to.meta.auth !== false && !auth.isLoggedIn) {
    return navigateTo({ path: '/login', query: { redirect: to.fullPath } })
  }
  if (to.meta.admin && !auth.isAdmin) {
    return navigateTo('/chat')
  }
})
