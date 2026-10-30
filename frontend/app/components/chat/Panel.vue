<script setup lang="ts">
const auth = useAuthStore()
const notification = useNotificationStore()
const { messages, loading, loadError, sending, error, load, ask, retry, startNew } = useChat()
const { registered, error: statusError, loading: checking, check, markNotRegistered } = usePolicyStatus()
const question = ref('')

onMounted(() => {
  check()
  load()
})

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

    <div v-if="loading" class="d-flex justify-center pa-8">
      <v-progress-circular indeterminate />
    </div>

    <v-alert v-else-if="loadError" type="error" variant="tonal" class="chat__notice">
      {{ loadError }}
      <div class="mt-2">
        <v-btn size="small" variant="outlined" @click="load">読み込み直す</v-btn>
      </div>
    </v-alert>

    <ChatMessageList v-else-if="messages.length" class="chat__list" :messages :sending :error @retry="onRetry" />

    <div v-else class="text-center text-medium-emphasis pa-4">
      就業規則の内容について、質問してください。<br>
      回答は、登録されている就業規則に基づきます。
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
