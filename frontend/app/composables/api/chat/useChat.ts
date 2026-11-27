import { ApiError } from '../useApi'

export type ChatSource = {
  article: string
  page: number | null
}

export type ChatMessage = {
  // 画面の描画用のキー（サーバーのIDか、送信中に仮につける番号）
  key: string
  role: 'user' | 'assistant'
  content: string
  // 回答だけに付く（質問では null）。false は「規程に該当する記載なし」
  found: boolean | null
  sources: ChatSource[]
  // FAQの回答（AIの回答ではない）。サーバーには保存されない
  fromFaq?: boolean
}

// 画面に表示するエラー。サーバーのコードごとに、見出しを分ける
export type ChatError = {
  title: string
  message: string
  code: string | null
  retryable: boolean
}

// ok: 回答できた / error: 失敗（error に内容が入る） / not-registered: 規程が未登録だった
export type AskResult = 'ok' | 'error' | 'not-registered'

type ServerMessage = {
  id: number
  role: 'user' | 'assistant'
  content: string
  found: boolean | null
  sources: ChatSource[]
}

type SessionResponse = {
  session_id: number | null
  messages: ServerMessage[]
}

type AnswerResponse = {
  session_id: number
  message_id: number
  answer: string
  found: boolean
  sources: ChatSource[]
}

const UNEXPECTED_MESSAGE = '予期しないエラーが発生しました'

const ERROR_TITLES: Record<string, string> = {
  RATE_LIMITED: '質問の回数が上限に達しました',
  AI_BUSY: 'AIが混み合っています',
  AI_RATE_LIMITED: 'AIが混み合っています',
  AI_UNAVAILABLE: 'AIに問題が発生しました',
  AI_ERROR: 'AIに問題が発生しました',
  AI_INVALID_RESPONSE: 'AIに問題が発生しました',
}

const describeError = (e: unknown): ChatError => {
  if (!(e instanceof ApiError)) {
    return { title: '質問を送れませんでした', message: UNEXPECTED_MESSAGE, code: null, retryable: true }
  }
  // タイムアウトと、接続できない場合（HTTPの応答がない）
  if (e.status === null) {
    return { title: '応答がありません', message: e.message, code: e.code, retryable: true }
  }
  if (e.status === 404) {
    return {
      title: '会話が見つかりません',
      message: '「新しい会話」から、やり直してください',
      code: e.code,
      retryable: false,
    }
  }
  if (e.code === 'SESSION_EXPIRED' || e.code === 'VALIDATION_ERROR') {
    return { title: '質問を送れませんでした', message: e.message, code: e.code, retryable: false }
  }
  return {
    title: (e.code && ERROR_TITLES[e.code]) || '質問を送れませんでした',
    message: e.message,
    code: e.code,
    retryable: true,
  }
}

export const useChat = () => {
  const { request, post } = useApi()

  const sessionId = ref<number | null>(null)
  const messages = ref<ChatMessage[]>([])
  // 会話の読み込み中
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  // 質問を送って、回答を待っている間
  const sending = ref(false)
  // 直近の質問が失敗したときだけ入る。質問は、messages の末尾に残す
  const error = ref<ChatError | null>(null)
  let failedQuestion: string | null = null
  let localSequence = 0

  // 最新の会話を読み込む。画面を開き直しても、会話が続く
  const load = async () => {
    loading.value = true
    loadError.value = null
    try {
      const data = await request<SessionResponse>('/chat/sessions/current')
      sessionId.value = data.session_id
      messages.value = data.messages.map((m) => ({
        key: `m-${m.id}`,
        role: m.role,
        content: m.content,
        found: m.found,
        sources: m.sources,
      }))
      error.value = null
      failedQuestion = null
    } catch (e) {
      loadError.value = e instanceof ApiError ? e.message : UNEXPECTED_MESSAGE
    } finally {
      loading.value = false
    }
  }

  const ask = async (question: string): Promise<AskResult> => {
    sending.value = true
    error.value = null
    failedQuestion = null
    messages.value.push({ key: `local-${++localSequence}`, role: 'user', content: question, found: null, sources: [] })
    try {
      const data = await post<AnswerResponse>('/chat/messages', {
        question,
        ...(sessionId.value === null ? {} : { session_id: sessionId.value }),
      })
      sessionId.value = data.session_id
      messages.value.push({
        key: `m-${data.message_id}`,
        role: 'assistant',
        content: data.answer,
        found: data.found,
        sources: data.sources,
      })
      return 'ok'
    } catch (e) {
      const described = describeError(e)
      if (described.code === 'POLICY_NOT_REGISTERED') {
        // 質問は送られていないので、履歴からも外す
        messages.value.pop()
        return 'not-registered'
      }
      error.value = described
      failedQuestion = question
      return 'error'
    } finally {
      sending.value = false
    }
  }

  // FAQの質問と回答を、会話に表示する。AIは呼ばず、サーバーにも保存しない（画面を開き直すと消える）
  const showFaq = (question: string, answer: string, sources: ChatSource[]) => {
    messages.value.push(
      { key: `local-${++localSequence}`, role: 'user', content: question, found: null, sources: [] },
      { key: `local-${++localSequence}`, role: 'assistant', content: answer, found: true, sources, fromFaq: true },
    )
  }

  // 失敗した質問を、もう一度送る
  const retry = async (): Promise<AskResult> => {
    if (failedQuestion === null || sending.value) return 'error'
    const question = failedQuestion
    messages.value.pop()
    return ask(question)
  }

  // 「新しい会話」を始める。失敗したときは、エラーのメッセージを返す
  const startNew = async (): Promise<string | null> => {
    if (sending.value) return null
    try {
      const data = await post<{ session_id: number }>('/chat/sessions', {})
      sessionId.value = data.session_id
      messages.value = []
      error.value = null
      failedQuestion = null
      return null
    } catch (e) {
      return e instanceof ApiError ? e.message : UNEXPECTED_MESSAGE
    }
  }

  return { messages, loading, loadError, sending, error, load, ask, retry, startNew, showFaq }
}
