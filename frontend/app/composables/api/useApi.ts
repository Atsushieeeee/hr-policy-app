// タイムアウトの基準はバックエンドが持つ。
// バックエンドの上限（デフォルト30秒）より長くしておく。
// 特別に長く待つ処理だけ、呼び出し側で timeoutMs を上書きする。
const DEFAULT_TIMEOUT_MS = 60_000

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

type RequestOptions = RequestInit & { timeoutMs?: number }

// バックエンドのエラー形式 { error: { code, message } } を読み取る
const toApiError = async (response: Response): Promise<ApiError> => {
  try {
    const data = await response.json()
    if (data?.error?.message) {
      return new ApiError(data.error.message, response.status, data.error.code ?? null)
    }
  } catch {
    // JSONでない場合は、下の汎用メッセージを使う
  }
  return new ApiError(`リクエストに失敗しました (${response.status})`, response.status)
}

// API呼び出しの共通処理。タイムアウトとエラーの正規化をここに集約する。
// （認証トークンの付与は、フェーズ1でここに追加する）
export const useApi = () => {
  const request = async <T>(path: string, init: RequestOptions = {}): Promise<T> => {
    const { timeoutMs = DEFAULT_TIMEOUT_MS, ...fetchInit } = init
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await fetch(`/api/v1${path}`, {
        ...fetchInit,
        headers: { Accept: 'application/json', ...fetchInit.headers },
        signal: controller.signal,
      })
      if (!response.ok) {
        throw await toApiError(response)
      }
      return (await response.json()) as T
    } catch (e) {
      if (e instanceof ApiError) throw e
      if (e instanceof DOMException && e.name === 'AbortError') {
        throw new ApiError('サーバーからの応答がありません（タイムアウト）', null)
      }
      throw new ApiError('サーバーに接続できません', null)
    } finally {
      clearTimeout(timer)
    }
  }

  const post = <T>(path: string, body: unknown, init: RequestOptions = {}): Promise<T> =>
    request<T>(path, {
      ...init,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...init.headers },
      body: JSON.stringify(body),
    })

  return { request, post }
}
