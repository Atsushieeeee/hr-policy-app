const DEFAULT_REDIRECT = '/chat'

// ログイン後の遷移先。外部サイトへの転送（オープンリダイレクト）を防ぐため、
// 「/」で始まる、同じサイト内のパスだけを許可する。
export const safeRedirect = (value: unknown): string => {
  if (typeof value !== 'string') return DEFAULT_REDIRECT
  if (!value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) {
    return DEFAULT_REDIRECT
  }
  return value
}
