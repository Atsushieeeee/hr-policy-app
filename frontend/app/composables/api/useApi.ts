// タイムアウトの基準はバックエンドが持つ（例: Geminiの呼び出しは30秒で打ち切る）。
// ここは「最後の安全網」で、バックエンドの上限より長くしておく。
// こうすると、先にバックエンドが分かりやすいエラーを返せる。
//   外部API(30秒) < サーバーの上限 < プロキシ < ブラウザ(この値)
// 特別に長く待つ処理（大きなファイルのアップロードなど）だけ、呼び出し側で timeoutMs を上書きする。
const DEFAULT_TIMEOUT_MS = 60_000
// ファイルのアップロード（大きなPDFなど）は、通信に時間がかかるため、長めにする
export const UPLOAD_TIMEOUT_MS = 120_000

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
    public readonly code: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

type RequestOptions = RequestInit & {
  timeoutMs?: number
  /** true にすると、アクセストークンを付けず、401でも更新しない（ログイン・更新・ログアウト用） */
  skipAuth?: boolean
  /** 'blob' にすると、成功時の応答をファイル（PDFなど）として受け取る。既定は JSON */
  responseType?: 'json' | 'blob'
}

type RawResult = { response: Response; body: unknown }

// バックエンドのエラー形式 { error: { code, message } } を読み取る
const toApiError = (status: number, body: unknown): ApiError => {
  const error = (body as { error?: { code?: string; message?: string } } | null)?.error
  if (error?.message) {
    return new ApiError(error.message, status, error.code ?? null)
  }
  return new ApiError(`リクエストに失敗しました (${status})`, status)
}

// アクセストークンの更新。同時に複数のリクエストが401になっても、更新は1回にまとめる。
// （使用済みのリフレッシュトークンが再利用されると、バックエンドが全ログインを無効にするため）
let refreshing: Promise<boolean> | null = null

export const refreshAccessToken = (): Promise<boolean> => {
  const auth = useAuthStore()
  refreshing ??= (async () => {
    try {
      const response = await fetch('/api/v1/auth/refresh', {
        method: 'POST',
        headers: { Accept: 'application/json' },
      })
      if (!response.ok) {
        auth.clear()
        return false
      }
      const data = (await response.json()) as { access: string }
      auth.setAccessToken(data.access)
      return true
    } catch {
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

// API呼び出しの共通処理。トークンの付与、401時の更新、タイムアウト、エラーの正規化をここに集約する。
export const useApi = () => {
  const auth = useAuthStore()
  const router = useRouter()

  const run = async (path: string, init: RequestOptions, token: string | null): Promise<RawResult> => {
    const { timeoutMs = DEFAULT_TIMEOUT_MS, skipAuth, responseType = 'json', ...fetchInit } = init
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(`/api/v1${path}`, {
        ...fetchInit,
        headers: {
          Accept: responseType === 'blob' ? 'application/pdf, application/json' : 'application/json',
          ...(token && !skipAuth ? { 'X-Access-Token': token } : {}),
          ...fetchInit.headers,
        },
        signal: controller.signal,
      })
      // 失敗したときは、ファイルを要求していても、エラーはJSONで返ってくる
      const body =
        response.status === 204
          ? null
          : responseType === 'blob' && response.ok
            ? await response.blob()
            : await response.json().catch(() => null)
      return { response, body }
    } finally {
      clearTimeout(timer)
    }
  }

  const handleSessionExpired = async () => {
    auth.clear()
    const current = router.currentRoute.value
    if (current.path !== '/login') {
      await navigateTo({ path: '/login', query: { redirect: current.fullPath } })
    }
  }

  const request = async <T>(path: string, init: RequestOptions = {}): Promise<T> => {
    try {
      let result = await run(path, init, auth.accessToken)

      // アクセストークンの期限切れ: 更新して、1回だけやり直す
      if (result.response.status === 401 && !init.skipAuth && auth.accessToken) {
        if (await refreshAccessToken()) {
          result = await run(path, init, auth.accessToken)
        } else {
          await handleSessionExpired()
          throw new ApiError('ログインの有効期限が切れました', 401, 'SESSION_EXPIRED')
        }
      }

      if (!result.response.ok) {
        throw toApiError(result.response.status, result.body)
      }
      return result.body as T
    } catch (e) {
      if (e instanceof ApiError) throw e
      if (e instanceof DOMException && e.name === 'AbortError') {
        throw new ApiError('サーバーからの応答がありません（タイムアウト）', null)
      }
      throw new ApiError('サーバーに接続できません', null)
    }
  }

  const post = <T>(path: string, body: unknown, init: RequestOptions = {}): Promise<T> =>
    request<T>(path, {
      ...init,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...init.headers },
      body: JSON.stringify(body),
    })

  const patch = <T>(path: string, body: unknown, init: RequestOptions = {}): Promise<T> =>
    request<T>(path, {
      ...init,
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json', ...init.headers },
      body: JSON.stringify(body),
    })

  const del = (path: string, init: RequestOptions = {}): Promise<null> =>
    request<null>(path, { ...init, method: 'DELETE' })

  // ファイル（multipart）を送る。Content-Type は付けない（ブラウザが境界つきで設定する）
  const upload = <T>(path: string, form: FormData, init: RequestOptions = {}): Promise<T> =>
    request<T>(path, { timeoutMs: UPLOAD_TIMEOUT_MS, ...init, method: 'PUT', body: form })

  // ファイル（PDFなど）を取得する
  const getBlob = (path: string, init: RequestOptions = {}): Promise<Blob> =>
    request<Blob>(path, { ...init, responseType: 'blob' })

  return { request, post, patch, del, upload, getBlob }
}
