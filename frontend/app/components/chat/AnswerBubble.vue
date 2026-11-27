<script setup lang="ts">
import type { ChatMessage, ChatSource } from '~/composables/api/chat/useChat'

defineProps<{ message: ChatMessage }>()
defineEmits<{ 'open-source': [source: ChatSource] }>()
</script>

<template>
  <div>
    <v-chip v-if="message.fromFaq" size="x-small" color="primary" variant="tonal" class="mb-1">FAQより</v-chip>
    <v-alert :type="message.found ? 'info' : 'warning'" variant="tonal" class="text-pre-wrap">
      {{ message.content }}
    </v-alert>
    <div v-if="message.sources.length" class="mt-2">
      <div class="text-caption text-medium-emphasis">根拠</div>
      <v-chip
        v-for="s in message.sources"
        :key="`${s.article}-${s.page}`"
        size="small"
        class="mr-2 mt-1"
        link
        @click="$emit('open-source', s)"
      >
        {{ s.article }}<template v-if="s.page">（p.{{ s.page }}）</template>
      </v-chip>
    </div>
    <div class="text-caption text-medium-emphasis mt-2">
      <template v-if="message.fromFaq">
        管理者が確認したFAQの回答です。最終的な判断は人事担当にご確認ください。
      </template>
      <template v-else>本回答は就業規則の記載に基づく案内です。最終的な判断は人事担当にご確認ください。</template>
    </div>
  </div>
</template>
