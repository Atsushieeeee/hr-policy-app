<script setup lang="ts">
import type { PublicFaq } from '~/composables/api/chat/usePublicFaqs'

defineProps<{
  items: PublicFaq[]
  loading: boolean
  error: string | null
  /** FAQの回答を取得している間は、選べなくする */
  busy: boolean
}>()
const emit = defineEmits<{ select: [faq: PublicFaq]; retry: [] }>()
</script>

<template>
  <div>
    <div v-if="loading" class="d-flex justify-center pa-4">
      <v-progress-circular indeterminate size="24" />
    </div>
    <v-alert v-else-if="error" type="error" variant="tonal" density="compact">
      よくある質問を読み込めませんでした。
      <div class="mt-2">
        <v-btn size="small" variant="outlined" @click="emit('retry')">もう一度読み込む</v-btn>
      </div>
    </v-alert>
    <v-list v-else-if="items.length" density="compact" class="faq-list">
      <v-list-subheader>よくある質問</v-list-subheader>
      <v-list-item
        v-for="faq in items"
        :key="faq.id"
        :title="faq.question"
        prepend-icon="mdi-help-circle-outline"
        :disabled="busy"
        @click="emit('select', faq)"
      />
    </v-list>
  </div>
</template>

<style scoped>
.faq-list {
  background: transparent;
}
</style>
