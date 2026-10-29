import { ApiError } from '../useApi'

export type PolicyCurrent = {
  id: number
  title: string
  original_filename: string
  file_size: number
  page_count: number | null
  uploaded_by: { id: number; name: string }
  uploaded_at: string
}

export type PolicyUpload = {
  id: number
  original_filename: string
  status: 'processing' | 'failed'
  error_code: string
  error_message: string
}

type PolicyInfo = {
  current: PolicyCurrent | null
  upload: PolicyUpload | null
}

export const MAX_UPLOAD_MB = 20
// 取り込みの状況を確認する間隔
const POLL_INTERVAL_MS = 3000

const toMessage = (e: unknown) => (e instanceof ApiError ? e.message : '予期しないエラーが発生しました')

// 現行の規程の情報とPDF、アップロード（取り込みの状況の確認を含む）。
export const usePolicy = () => {
  const { request, upload: sendFile, getBlob } = useApi()

  const current = ref<PolicyCurrent | null>(null)
  const upload = ref<PolicyUpload | null>(null)
  // PDFのプレビュー用のURL（ブラウザ内の Blob URL）
  const pdfUrl = ref<string | null>(null)
  const loading = ref(true)
  const uploading = ref(false)
  const error = ref<string | null>(null)
  // 直前のアップロードが、取り込みまで成功したか
  const succeeded = ref(false)

  let previewId: number | null = null
  let timer: ReturnType<typeof setTimeout> | null = null

  const stopPolling = () => {
    if (timer) clearTimeout(timer)
    timer = null
  }

  const clearPdf = () => {
    if (pdfUrl.value) URL.revokeObjectURL(pdfUrl.value)
    pdfUrl.value = null
    previewId = null
  }

  // 現行の規程が変わったときだけ、PDFを取得し直す
  const syncPdf = async () => {
    const id = current.value?.id ?? null
    if (id === previewId) return
    clearPdf()
    if (id === null) return
    try {
      const blob = await getBlob('/admin/policy/file')
      // 取得している間に、さらに別の規程に変わっていたら、捨てる
      if (current.value?.id !== id) return
      pdfUrl.value = URL.createObjectURL(blob)
      previewId = id
    } catch (e) {
      error.value = toMessage(e)
    }
  }

  const fetchInfo = async () => {
    const wasProcessing = upload.value?.status === 'processing'
    const info = await request<PolicyInfo>('/admin/policy')
    current.value = info.current
    upload.value = info.upload
    // 処理中だったものが、失敗の記録も残さず無くなった = 取り込みが完了した
    if (wasProcessing && info.upload === null) succeeded.value = true
    await syncPdf()
  }

  const poll = () => {
    stopPolling()
    timer = setTimeout(async () => {
      try {
        await fetchInfo()
      } catch (e) {
        error.value = toMessage(e)
        return
      }
      if (upload.value?.status === 'processing') poll()
    }, POLL_INTERVAL_MS)
  }

  // 画面を開いたとき。処理中のものがあれば、状況の確認を再開する
  const load = async () => {
    loading.value = true
    error.value = null
    try {
      await fetchInfo()
      if (upload.value?.status === 'processing') poll()
    } catch (e) {
      error.value = toMessage(e)
    } finally {
      loading.value = false
    }
  }

  // 受け付けられたかどうかを返す
  const submit = async (file: File): Promise<boolean> => {
    uploading.value = true
    error.value = null
    succeeded.value = false
    try {
      const form = new FormData()
      form.append('file', file)
      upload.value = await sendFile<PolicyUpload>('/admin/policy', form)
      poll()
      return true
    } catch (e) {
      error.value = toMessage(e)
      return false
    } finally {
      uploading.value = false
    }
  }

  onBeforeUnmount(() => {
    stopPolling()
    clearPdf()
  })

  return { current, upload, pdfUrl, loading, uploading, error, succeeded, load, submit }
}
