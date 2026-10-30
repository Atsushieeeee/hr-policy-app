import { ApiError } from '../useApi'

// 現行の規程のPDF（利用者向け）。ブラウザ内の Blob URL にして、iframe で表示できるようにする。
// 取得は1回だけで、開くたびに使い回す。不要になったら release で解放する。
export const usePolicyFile = () => {
  const { getBlob } = useApi()

  const url = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  let pending: Promise<void> | null = null
  let released = false

  // 取得済みなら、何もしない。取得中に、もう一度呼ばれたときは、同じ取得を待つ
  const load = (): Promise<void> => {
    if (url.value) return Promise.resolve()
    pending ??= (async () => {
      loading.value = true
      error.value = null
      try {
        const blob = await getBlob('/policy/file')
        // 取得している間に、画面を離れていたら、捨てる
        if (!released) url.value = URL.createObjectURL(blob)
      } catch (e) {
        error.value = e instanceof ApiError ? e.message : '予期しないエラーが発生しました'
      } finally {
        loading.value = false
        pending = null
      }
    })()
    return pending
  }

  const release = () => {
    released = true
    if (url.value) URL.revokeObjectURL(url.value)
    url.value = null
  }

  return { url, loading, error, load, release }
}
