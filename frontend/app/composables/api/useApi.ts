const DEFAULT_TIMEOUT_MS = 10_000

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number | null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// API呼び出しの共通処理。タイムアウトとエラーの正規化をここに集約する。
// （認証トークンの付与は、フェーズ1でここに追加する）
export function useApi() {
  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS)
    try {
      const response = await fetch(`/api/v1${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...init.headers },
        signal: controller.signal,
      })
      if (!response.ok) {
        throw new ApiError(`リクエストに失敗しました (${response.status})`, response.status)
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

  return { request }
}
