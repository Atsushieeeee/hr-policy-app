<script setup lang="ts">
import { useDisplay } from 'vuetify'
import type { PublicFaq } from '~/composables/api/chat/usePublicFaqs'

const open = defineModel<boolean>({ required: true })
defineProps<{ items: PublicFaq[]; loading: boolean; error: string | null; busy: boolean }>()
const emit = defineEmits<{ select: [faq: PublicFaq]; retry: [] }>()

const { smAndDown } = useDisplay()
</script>

<template>
  <v-dialog v-model="open" max-width="600" :fullscreen="smAndDown" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <span class="flex-grow-1">よくある質問</span>
        <v-btn icon="mdi-close" variant="text" aria-label="閉じる" @click="open = false" />
      </v-card-title>
      <v-card-text class="pa-0">
        <ChatFaqList
          :items
          :loading
          :error
          :busy
          @select="emit('select', $event)"
          @retry="emit('retry')"
        />
      </v-card-text>
    </v-card>
  </v-dialog>
</template>
