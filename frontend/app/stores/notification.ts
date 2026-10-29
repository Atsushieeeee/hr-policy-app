type NotificationType = 'success' | 'error'

// 画面の下に一時的に表示する通知（スナックバー）の状態。表示は components/common/Snackbar.vue が行う。
// 画面を移動しても、アプリ全体で表示が続くため、「操作が成功した後に、別の画面へ移動する」場合に使う。
export const useNotificationStore = defineStore('notification', () => {
  const message = ref('')
  const type = ref<NotificationType>('success')
  const visible = ref(false)
  // 同じメッセージを続けて表示しても、表示し直せるようにする
  const sequence = ref(0)

  const show = (newMessage: string, newType: NotificationType = 'success') => {
    message.value = newMessage
    type.value = newType
    sequence.value += 1
    visible.value = true
  }

  const hide = () => {
    visible.value = false
  }

  return { message, type, visible, sequence, show, hide }
})
