<script setup lang="ts">
import { useDisplay } from 'vuetify'
import type { ChatSource } from '~/composables/api/chat/useChat'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  source: ChatSource | null
  url: string | null
  loading: boolean
  error: string | null
}>()
const emit = defineEmits<{ retry: [] }>()

const { smAndDown } = useDisplay()

// ページが分からない根拠は、PDFの先頭を表示する
const src = computed(() => (props.url && props.source?.page ? `${props.url}#page=${props.source.page}` : props.url))
</script>

<template>
  <v-dialog v-model="open" max-width="900" :fullscreen="smAndDown" scrollable>
    <v-card>
      <v-card-title class="d-flex align-center">
        <span class="flex-grow-1">
          {{ source?.article }}<template v-if="source?.page">（p.{{ source.page }}）</template>
        </span>
        <v-btn icon="mdi-close" variant="text" aria-label="閉じる" @click="open = false" />
      </v-card-title>

      <v-card-text class="pa-0">
        <div v-if="loading" class="d-flex align-center ga-3 pa-6">
          <v-progress-circular indeterminate size="24" />
          PDFを読み込み中...
        </div>
        <v-alert v-else-if="error" type="error" variant="tonal" class="ma-4">
          {{ error }}
          <div class="mt-2">
            <v-btn size="small" variant="outlined" @click="emit('retry')">もう一度読み込む</v-btn>
          </div>
        </v-alert>
        <!-- 根拠が変わったときは、作り直して、ページを切り替える（ハッシュの変更だけでは、追従しないことがある） -->
        <iframe v-else-if="src" :key="source?.page ?? 0" :src title="現行の規程のPDF" class="viewer" />
      </v-card-text>

      <v-card-actions class="text-caption text-medium-emphasis px-4">
        現在の規程を表示しています。規程が改定されている場合、回答のときとはページが異なることがあります。
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.viewer {
  width: 100%;
  height: 75vh;
  border: 0;
}
</style>
