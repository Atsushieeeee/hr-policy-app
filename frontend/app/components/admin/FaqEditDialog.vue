<script setup lang="ts">
import { useDisplay } from 'vuetify'
import type { FaqSource } from '~/composables/api/admin/useFaqCandidates'
import type { ChatSource } from '~/composables/api/chat/useChat'

const open = defineModel<boolean>({ required: true })
const props = defineProps<{
  title: string
  saveLabel: string
  initialQuestion: string
  initialAnswer: string
  sources: FaqSource[]
  saving: boolean
  error: string | null
}>()
const emit = defineEmits<{ save: [value: { question: string; answer: string }] }>()

const { smAndDown } = useDisplay()

const MAX_QUESTION_LENGTH = 1000

const question = ref('')
const answer = ref('')

// 開くたびに、渡された内容を入れ直す（前回の編集を引きずらない）
watch(open, (isOpen) => {
  if (!isOpen) return
  question.value = props.initialQuestion
  answer.value = props.initialAnswer
})

const canSave = computed(
  () => question.value.trim() !== '' && answer.value.trim() !== '' && question.value.length <= MAX_QUESTION_LENGTH,
)

const save = () => {
  if (canSave.value && !props.saving) emit('save', { question: question.value.trim(), answer: answer.value.trim() })
}

// 根拠から、現在の規程のPDFをそのページで開く（チャットの根拠と同じ仕組み）
const policyFile = usePolicyFile()
const sourceOpen = ref(false)
const selected = ref<ChatSource | null>(null)

const openSource = async (source: FaqSource) => {
  selected.value = { article: source.article, page: source.page }
  sourceOpen.value = true
  await policyFile.load()
}

onBeforeUnmount(policyFile.release)
</script>

<template>
  <v-dialog v-model="open" max-width="720" :fullscreen="smAndDown" scrollable persistent>
    <v-card>
      <v-card-title>{{ title }}</v-card-title>

      <v-card-text>
        <v-alert type="warning" variant="tonal" density="compact" class="mb-4">
          AIの回答は、誤りを含むことがあります。規程の原文を確認してから、公開してください。
        </v-alert>

        <v-textarea
          v-model="question"
          label="質問"
          rows="2"
          auto-grow
          variant="outlined"
          :counter="MAX_QUESTION_LENGTH"
          :disabled="saving"
        />
        <v-textarea v-model="answer" label="回答" rows="6" auto-grow variant="outlined" :disabled="saving" />

        <div v-if="sources.length" class="mb-2">
          <div class="text-caption text-medium-emphasis mb-1">根拠（押すと、規程のPDFを開きます）</div>
          <div class="d-flex flex-wrap ga-2">
            <v-chip
              v-for="(source, i) in sources"
              :key="i"
              prepend-icon="mdi-file-document-outline"
              variant="outlined"
              size="small"
              @click="openSource(source)"
            >
              {{ source.article }}<template v-if="source.page">（p.{{ source.page }}）</template>
            </v-chip>
          </div>
        </div>

        <v-alert v-if="error" type="error" variant="tonal" class="mt-3">{{ error }}</v-alert>
      </v-card-text>

      <v-card-actions>
        <v-spacer />
        <v-btn :disabled="saving" @click="open = false">キャンセル</v-btn>
        <v-btn color="primary" variant="flat" :loading="saving" :disabled="!canSave" @click="save">
          {{ saveLabel }}
        </v-btn>
      </v-card-actions>
    </v-card>

    <ChatSourceDialog
      v-model="sourceOpen"
      :source="selected"
      :url="policyFile.url.value"
      :loading="policyFile.loading.value"
      :error="policyFile.error.value"
      @retry="policyFile.load"
    />
  </v-dialog>
</template>
