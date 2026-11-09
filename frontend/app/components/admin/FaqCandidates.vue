<script setup lang="ts">
import type { FaqCandidate } from '~/composables/api/admin/useFaqCandidates'

const emit = defineEmits<{ registered: [] }>()

const notification = useNotificationStore()
const { items, total, loading, error, load } = useFaqCandidates()
const { create, messageOf } = useFaqs()

const page = ref(1)
const itemsPerPage = ref(20)
const includeRegistered = ref(false)

const reload = () => load(page.value, itemsPerPage.value, includeRegistered.value)

onMounted(reload)
watch([page, itemsPerPage], reload)
// 表示の条件を変えたら、1ページ目から表示する
watch(includeRegistered, () => {
  if (page.value === 1) reload()
  else page.value = 1
})

// ソートは、しない（並びは、聞かれた回数の多い順）
const headers = [
  { title: '質問', key: 'question', sortable: false },
  { title: '回数', key: 'ask_count', sortable: false, align: 'end' as const },
  { title: '人数', key: 'user_count', sortable: false, align: 'end' as const },
  { title: '最後に聞かれた日時', key: 'last_asked_at', sortable: false },
  { title: '', key: 'actions', sortable: false, align: 'end' as const },
]

const formatDate = (iso: string) => new Date(iso).toLocaleString('ja-JP')

// 登録のダイアログ。質問と回答は、候補の内容を最初から入れておく
const dialog = ref(false)
const target = ref<FaqCandidate | null>(null)
const saving = ref(false)
const saveError = ref<string | null>(null)

const openDialog = (candidate: FaqCandidate) => {
  target.value = candidate
  saveError.value = null
  dialog.value = true
}

const save = async ({ question, answer }: { question: string; answer: string }) => {
  if (!target.value) return
  saving.value = true
  saveError.value = null
  try {
    await create({ question, answer, source_message_id: target.value.source_message_id })
    dialog.value = false
    notification.show('下書きで登録しました。FAQ一覧で公開できます')
    emit('registered')
    await reload()
  } catch (e) {
    saveError.value = messageOf(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="d-flex align-center mb-2">
      <span class="text-body-2 text-medium-emphasis">よく聞かれている質問です。回答のあるものだけを表示します。</span>
      <v-spacer />
      <v-switch v-model="includeRegistered" label="登録済みも表示" density="compact" hide-details color="primary" />
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <v-card>
      <v-data-table-server
        :page="page"
        :items-per-page="itemsPerPage"
        :headers="headers"
        :items="items"
        :items-length="total"
        :loading="loading"
        :items-per-page-options="[10, 20, 50, 100]"
        item-value="source_message_id"
        items-per-page-text="1ページの件数"
        page-text="{0}〜{1}件（全{2}件）"
        loading-text="読み込み中..."
        no-data-text="FAQにできる質問は、まだありません"
        @update:page="page = $event"
        @update:items-per-page="itemsPerPage = $event"
      >
        <template #[`item.question`]="{ item }">
          <span class="d-inline-block text-truncate" style="max-width: 420px">{{ item.question }}</span>
        </template>
        <template #[`item.last_asked_at`]="{ item }">
          <span class="text-no-wrap">{{ formatDate(item.last_asked_at) }}</span>
        </template>
        <template #[`item.actions`]="{ item }">
          <v-chip v-if="item.registered" size="small" color="success" variant="tonal">登録済み</v-chip>
          <v-btn v-else size="small" color="primary" variant="outlined" @click="openDialog(item)">FAQに登録</v-btn>
        </template>
      </v-data-table-server>
    </v-card>

    <AdminFaqEditDialog
      v-model="dialog"
      title="FAQに登録"
      save-label="下書きで登録"
      :initial-question="target?.question ?? ''"
      :initial-answer="target?.answer ?? ''"
      :sources="target?.sources ?? []"
      :saving="saving"
      :error="saveError"
      @save="save"
    />
  </div>
</template>
