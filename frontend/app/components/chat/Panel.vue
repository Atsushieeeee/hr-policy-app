<script setup lang="ts">
import { ApiError } from '~/composables/api/useApi'
import type { PublicFaq } from '~/composables/api/chat/usePublicFaqs'

const auth = useAuthStore()
const notification = useNotificationStore()
const { messages, loading, loadError, sending, error, load, ask, retry, startNew, showFaq } = useChat()
const faqs = usePublicFaqs()
const { registered, error: statusError, loading: checking, check, markNotRegistered } = usePolicyStatus()
const {
  url: pdfUrl,
  loading: pdfLoading,
  error: pdfError,
  load: loadPdf,
  release: releasePdf,
} = usePolicyFile()
const question = ref('')
const sourceOpen = ref(false)
const selectedSource = ref<ChatSource | null>(null)

onMounted(() => {
  check()
  load()
  faqs.load()
})
onBeforeUnmount(releasePdf)

// 登録状況の確認に失敗したときは、入力欄を止めない（質問を送れば、サーバーが判断する）
const notRegistered = computed(() => registered.value === false)
const disabled = computed(() => notRegistered.value || checking.value || loading.value || loadError.value !== null)
// 会話が空のときだけ、入力欄を画面の中央に置く
const isEmpty = computed(() => !loading.value && messages.value.length === 0)

// 画面を開いた後に、規程が無くなった場合は、未登録の表示に切り替えて、質問は入力欄へ戻す
const handleResult = (result: AskResult, asked: string) => {
  if (result === 'not-registered') {
    markNotRegistered()
    question.value = asked
  }
}

const send = async () => {
  const asked = question.value.trim()
  question.value = ''
  handleResult(await ask(asked), asked)
}

const onRetry = async () => {
  const lastQuestion = [...messages.value].reverse().find((m) => m.role === 'user')?.content ?? ''
  handleResult(await retry(), lastQuestion)
}

// 根拠を押したとき。PDFは、初めて開くときに1回だけ取得する
const openSource = (source: ChatSource) => {
  selectedSource.value = source
  sourceOpen.value = true
  loadPdf()
}

// FAQを選んだとき。回答を取得して、会話に表示する（AIは呼ばない）
const faqOpen = ref(false)
const faqBusy = ref(false)
const selectFaq = async (faq: PublicFaq) => {
  if (faqBusy.value) return
  faqBusy.value = true
  try {
    const detail = await faqs.fetchDetail(faq.id)
    showFaq(detail.question, detail.answer, detail.sources.map(({ article, page }) => ({ article, page })))
    faqOpen.value = false
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) {
      // 選ぶ前に、非公開になった
      notification.show('このFAQは、公開が終了しました', 'error')
      await faqs.load()
    } else {
      notification.show(e instanceof ApiError ? e.message : '予期しないエラーが発生しました', 'error')
    }
  } finally {
    faqBusy.value = false
  }
}

const onStartNew = async () => {
  const failure = await startNew()
  if (failure) notification.show(failure, 'error')
}
</script>

<template>
  <div class="chat" :class="{ 'chat--empty': isEmpty }">
    <div class="chat__header">
      <div class="chat__header-inner">
        <div class="text-h6">就業規則について質問する</div>
        <div>
          <v-btn
            v-if="faqs.items.value.length"
            variant="text"
            prepend-icon="mdi-help-circle-outline"
            :disabled="loading"
            @click="faqOpen = true"
          >
            よくある質問
          </v-btn>
          <v-btn
            variant="text"
            prepend-icon="mdi-plus"
            :disabled="messages.length === 0 || sending || loading"
            @click="onStartNew"
          >
            新しい会話
          </v-btn>
        </div>
      </div>
    </div>

    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate />
    </div>

    <v-alert v-else-if="loadError" type="error" variant="tonal" class="chat__notice">
      {{ loadError }}
      <div class="mt-2">
        <v-btn size="small" variant="outlined" @click="load">読み込み直す</v-btn>
      </div>
    </v-alert>

    <ChatMessageList
      v-else-if="messages.length"
      class="chat__list"
      :messages
      :sending
      :error
      @retry="onRetry"
      @open-source="openSource"
    />

    <div v-else class="chat__empty">
      <div class="text-center text-medium-emphasis pa-4">
        就業規則の内容について、質問してください。<br>
        回答は、登録されている就業規則に基づきます。
      </div>
      <ChatFaqList
        :items="faqs.items.value"
        :loading="faqs.loading.value"
        :error="faqs.error.value"
        :busy="faqBusy"
        @select="selectFaq"
        @retry="faqs.load"
      />
    </div>

    <div class="chat__input">
      <v-alert v-if="notRegistered" type="warning" variant="tonal" class="mb-4" title="就業規則が未登録です">
        <template v-if="auth.isAdmin">
          <NuxtLink to="/admin/upload">管理者画面</NuxtLink>から、就業規則のPDFをアップロードしてください。
        </template>
        <template v-else>管理者に、就業規則の登録を依頼してください。</template>
        <div class="mt-2">
          <v-btn size="small" variant="outlined" :loading="checking" @click="check">もう一度確認する</v-btn>
        </div>
      </v-alert>
      <v-alert v-else-if="statusError" type="error" variant="tonal" class="mb-4">{{ statusError }}</v-alert>

      <ChatMessageInput v-model="question" :disabled :sending @send="send" />
    </div>

    <ChatFaqDialog
      v-model="faqOpen"
      :items="faqs.items.value"
      :loading="faqs.loading.value"
      :error="faqs.error.value"
      :busy="faqBusy"
      @select="selectFaq"
      @retry="faqs.load"
    />

    <ChatSourceDialog
      v-model="sourceOpen"
      :source="selectedSource"
      :url="pdfUrl"
      :loading="pdfLoading"
      :error="pdfError"
      @retry="loadPdf"
    />
  </div>
</template>

<style scoped>
/* ヘッダー（64px）を除いた高さを使い、入力欄を画面の下に置く */
.chat {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 64px);
}

.chat--empty {
  justify-content: center;
}

.chat__header,
.chat__empty,
.chat__input,
.chat__notice {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 0 16px;
}

.chat__header {
  flex: none;
  padding-top: 8px;
}

.chat__header-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
}

.chat__list {
  flex: 1;
  min-height: 0;
}

.chat__input {
  flex: none;
  padding-top: 8px;
  padding-bottom: 16px;
}
</style>
