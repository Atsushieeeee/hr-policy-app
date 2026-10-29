<script setup lang="ts">
const MAX_LENGTH = 1000

const auth = useAuthStore()
const { result, error, errorCode, loading, ask } = useChat()
const { registered, error: statusError, loading: checking, check, markNotRegistered } = usePolicyStatus()
const question = ref('')
const asked = ref('')

onMounted(check)

// 登録状況の確認に失敗したときは、入力欄を止めない（質問を送れば、サーバーが判断する）
const notRegistered = computed(() => registered.value === false)
const disabled = computed(() => notRegistered.value || checking.value)

const canSend = computed(
  () => question.value.trim().length > 0 && question.value.length <= MAX_LENGTH && !loading.value && !disabled.value,
)

const send = async () => {
  if (!canSend.value) return
  asked.value = question.value.trim()
  const ok = await ask(asked.value)
  if (ok) question.value = ''
  // 画面を開いた後に、規程が無くなった場合
  else if (errorCode.value === 'POLICY_NOT_REGISTERED') markNotRegistered()
}

// 日本語入力の変換確定のEnterでは送信しない
const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <v-card max-width="720" class="mx-auto mt-8" title="就業規則について質問する">
    <v-card-text>
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

      <v-textarea
        v-model="question"
        label="質問を入力してください"
        rows="3"
        auto-grow
        counter
        :maxlength="MAX_LENGTH"
        :disabled="loading || disabled"
        @keydown="onKeydown"
      />
      <div class="d-flex justify-end">
        <v-btn color="primary" :disabled="!canSend" :loading="loading" @click="send">送信</v-btn>
      </div>
    </v-card-text>

    <v-divider />

    <v-card-text v-if="loading || error || result">
      <div v-if="asked" class="text-medium-emphasis mb-3">質問: {{ asked }}</div>

      <div v-if="loading" class="d-flex align-center ga-3">
        <v-progress-circular indeterminate size="24" />
        回答を作成中...
      </div>

      <v-alert v-else-if="error" type="error" variant="tonal">{{ error }}</v-alert>

      <template v-else-if="result">
        <v-alert :type="result.found ? 'info' : 'warning'" variant="tonal" class="text-pre-wrap">
          {{ result.answer }}
        </v-alert>
        <div v-if="result.sources.length" class="mt-3">
          <div class="text-caption text-medium-emphasis">根拠</div>
          <v-chip v-for="s in result.sources" :key="`${s.article}-${s.page}`" size="small" class="mr-2 mt-1">
            {{ s.article }}<template v-if="s.page">（p.{{ s.page }}）</template>
          </v-chip>
        </div>
        <div class="text-caption text-medium-emphasis mt-4">
          本回答は就業規則の記載に基づく案内です。最終的な判断は人事担当にご確認ください。
        </div>
      </template>
    </v-card-text>
  </v-card>
</template>
