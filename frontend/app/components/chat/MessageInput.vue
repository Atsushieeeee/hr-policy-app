<script setup lang="ts">
const MAX_LENGTH = 1000

const question = defineModel<string>({ required: true })
const props = defineProps<{
  disabled: boolean
  sending: boolean
}>()
const emit = defineEmits<{ send: [] }>()

const canSend = computed(
  () =>
    question.value.trim().length > 0 &&
    question.value.length <= MAX_LENGTH &&
    !props.sending &&
    !props.disabled,
)

const send = () => {
  if (canSend.value) emit('send')
}

// 日本語入力の変換確定のEnterでは送信しない。Shift+Enter は改行
const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}
</script>

<template>
  <div class="d-flex align-start ga-2">
    <v-textarea
      v-model="question"
      label="質問を入力してください"
      variant="outlined"
      rows="1"
      max-rows="6"
      auto-grow
      counter
      hide-details="auto"
      :maxlength="MAX_LENGTH"
      :disabled="disabled"
      @keydown="onKeydown"
    />
    <v-btn
      color="primary"
      icon="mdi-send"
      class="mt-1"
      aria-label="送信"
      :disabled="!canSend"
      :loading="sending"
      @click="send"
    />
  </div>
</template>
