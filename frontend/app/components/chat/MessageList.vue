<script setup lang="ts">
import type { ChatError, ChatMessage, ChatSource } from '~/composables/api/chat/useChat'

const props = defineProps<{
  messages: ChatMessage[]
  sending: boolean
  error: ChatError | null
}>()
const emit = defineEmits<{ retry: []; 'open-source': [source: ChatSource] }>()

const container = ref<HTMLElement | null>(null)

// 新しい発言・回答・エラーが追加されたら、いちばん下までスクロールする
const scrollToBottom = async () => {
  await nextTick()
  container.value?.scrollTo({ top: container.value.scrollHeight, behavior: 'smooth' })
}

watch(() => [props.messages.length, props.sending, props.error], scrollToBottom)
onMounted(scrollToBottom)
</script>

<template>
  <div ref="container" class="message-list">
    <div class="message-list__inner">
      <template v-for="m in messages" :key="m.key">
        <div v-if="m.role === 'user'" class="d-flex justify-end">
          <v-sheet color="primary" rounded="lg" class="user-message pa-3 text-pre-wrap">{{ m.content }}</v-sheet>
        </div>
        <ChatAnswerBubble v-else :message="m" @open-source="emit('open-source', $event)" />
      </template>

      <div v-if="sending" class="d-flex align-center ga-3 text-medium-emphasis">
        <v-progress-circular indeterminate size="24" />
        回答を作成中...
      </div>

      <v-alert v-if="error" type="error" variant="tonal" :title="error.title">
        {{ error.message }}
        <div v-if="error.retryable" class="mt-2">
          <v-btn size="small" variant="outlined" @click="emit('retry')">再試行</v-btn>
        </div>
      </v-alert>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  overflow-y: auto;
}

.message-list__inner {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 760px;
  margin: 0 auto;
  padding: 16px;
}

.user-message {
  max-width: 80%;
}
</style>
