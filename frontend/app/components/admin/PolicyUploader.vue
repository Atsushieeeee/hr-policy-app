<script setup lang="ts">
import { MAX_UPLOAD_MB } from '~/composables/api/admin/usePolicy'
import type { PolicyUpload } from '~/composables/api/admin/usePolicy'

const props = defineProps<{
  /** すでに規程が登録されているか（置き換えの確認を出す） */
  hasPolicy: boolean
  upload: PolicyUpload | null
  uploading: boolean
}>()

const emit = defineEmits<{ submit: [file: File] }>()

const file = ref<File | null>(null)
const confirming = ref(false)

const processing = computed(() => props.uploading || props.upload?.status === 'processing')

// サーバーも確認する。ここは、送る前に分かるものを、先に知らせるための確認
const validate = (f: File | null): string | null => {
  if (!f) return null
  const isPdf = f.type === 'application/pdf' || f.name.toLowerCase().endsWith('.pdf')
  if (!isPdf) return 'PDFファイルを選択してください'
  if (f.size > MAX_UPLOAD_MB * 1024 * 1024) return `ファイルが大きすぎます（上限: ${MAX_UPLOAD_MB}MB）`
  return null
}

const fileError = computed(() => validate(file.value))
const canSubmit = computed(() => file.value !== null && fileError.value === null && !processing.value)

const submit = () => {
  confirming.value = false
  if (file.value) emit('submit', file.value)
}

const onClick = () => {
  if (!canSubmit.value) return
  if (props.hasPolicy) confirming.value = true
  else submit()
}

// 受け付けられたら、選んだファイルは空にする
watch(
  () => props.upload?.status,
  (status) => {
    if (status === 'processing') file.value = null
  },
)
</script>

<template>
  <div>
    <v-file-input
      v-model="file"
      label="規程のPDFを選択"
      accept="application/pdf,.pdf"
      prepend-icon=""
      prepend-inner-icon="mdi-file-pdf-box"
      :hint="`PDFのみ、${MAX_UPLOAD_MB}MBまで`"
      persistent-hint
      :error-messages="fileError ?? undefined"
      :disabled="processing"
    />
    <div class="d-flex justify-end mt-4">
      <v-btn color="primary" :disabled="!canSubmit" :loading="uploading" @click="onClick">アップロード</v-btn>
    </div>

    <v-alert v-if="upload?.status === 'processing'" type="info" variant="tonal" class="mt-4">
      <div class="d-flex align-center ga-3">
        <v-progress-circular indeterminate size="20" width="2" />
        「{{ upload.original_filename }}」を処理中です。完了まで、このままお待ちください。
      </div>
    </v-alert>

    <v-alert v-else-if="upload?.status === 'failed'" type="error" variant="tonal" class="mt-4">
      「{{ upload.original_filename }}」を取り込めませんでした。{{ upload.error_message }}
    </v-alert>

    <v-dialog v-model="confirming" max-width="440">
      <v-card title="規程を置き換えますか？">
        <v-card-text>
          現在の規程は、新しいPDFに置き換わります。取り込みが完了するまでは、現在の規程で回答します。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="confirming = false">キャンセル</v-btn>
          <v-btn color="primary" variant="flat" @click="submit">置き換える</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
