<script setup lang="ts">
import type { Faq, FaqStatus } from '~/composables/api/admin/useFaqs'

const notification = useNotificationStore()
const { items, loading, error, load, update, remove, publishReviewed, messageOf } = useFaqs()

const STATUS_FILTERS: { title: string; value: FaqStatus | null }[] = [
  { title: 'すべて', value: null },
  { title: '下書き', value: 'draft' },
  { title: '公開', value: 'published' },
  { title: '要確認', value: 'needs_review' },
]
const STATUS_COLORS: Record<FaqStatus, string> = { draft: 'grey', published: 'success', needs_review: 'warning' }

const status = ref<FaqStatus | null>(null)
const reload = () => load(status.value)
onMounted(reload)
watch(status, reload)

const formatDate = (iso: string) => new Date(iso).toLocaleDateString('ja-JP')

// 操作の失敗は、画面の下に通知する
const run = async (action: () => Promise<unknown>, success?: string) => {
  try {
    await action()
    if (success) notification.show(success)
  } catch (e) {
    notification.show(messageOf(e), 'error')
  }
  await reload()
}

const togglePublish = (faq: Faq) =>
  run(
    () => update(faq.id, { status: faq.status === 'published' ? 'draft' : 'published' }),
    faq.status === 'published' ? '非公開（下書き）にしました' : '公開しました',
  )

// 並べ替えは、隣のFAQと並び順の値を入れ替える。「すべて」で見ているときだけ行う
const canReorder = computed(() => status.value === null)
const move = (index: number, direction: -1 | 1) => {
  const a = items.value[index]
  const b = items.value[index + direction]
  if (!a || !b) return
  return run(async () => {
    // 同じ値のときは、入れ替えても変わらないため、位置から振り直す
    const [first, second] = direction === -1 ? [a, b] : [b, a]
    const [firstOrder, secondOrder] =
      a.sort_order === b.sort_order ? [index, index + 1] : [Math.min(a.sort_order, b.sort_order), Math.max(a.sort_order, b.sort_order)]
    await update(first.id, { sort_order: firstOrder })
    await update(second.id, { sort_order: secondOrder })
  })
}

// 編集（質問と回答）
const editing = ref<Faq | null>(null)
const editOpen = ref(false)
const saving = ref(false)
const saveError = ref<string | null>(null)

const openEdit = (faq: Faq) => {
  editing.value = faq
  saveError.value = null
  editOpen.value = true
}

const save = async ({ question, answer }: { question: string; answer: string }) => {
  if (!editing.value) return
  saving.value = true
  saveError.value = null
  try {
    await update(editing.value.id, { question, answer })
    editOpen.value = false
    notification.show('保存しました')
    await reload()
  } catch (e) {
    saveError.value = messageOf(e)
  } finally {
    saving.value = false
  }
}

// 削除と、要確認のまとめての公開は、確認してから行う
const deleting = ref<Faq | null>(null)
const deleteOpen = computed({
  get: () => deleting.value !== null,
  set: (open) => {
    if (!open) deleting.value = null
  },
})
const confirmDelete = async () => {
  const faq = deleting.value
  if (!faq) return
  deleting.value = null
  await run(() => remove(faq.id), '削除しました')
}

const needsReviewCount = computed(() => items.value.filter((f) => f.status === 'needs_review').length)
const publishAllOpen = ref(false)
const confirmPublishAll = async () => {
  publishAllOpen.value = false
  try {
    const { count } = await publishReviewed()
    notification.show(`${count}件を公開に戻しました`)
  } catch (e) {
    notification.show(messageOf(e), 'error')
  }
  await reload()
}
</script>

<template>
  <div>
    <v-alert v-if="needsReviewCount" type="warning" variant="tonal" class="mb-4">
      規程が置き換えられたため、{{ needsReviewCount }}件のFAQが要確認です。内容を確認して、公開に戻してください。
      <div class="mt-2">
        <v-btn variant="outlined" size="small" @click="publishAllOpen = true">要確認をすべて公開に戻す</v-btn>
      </div>
    </v-alert>

    <div class="d-flex align-center mb-2">
      <v-btn-toggle v-model="status" mandatory density="compact" color="primary" variant="outlined" divided>
        <v-btn v-for="filter in STATUS_FILTERS" :key="filter.title" :value="filter.value" size="small">
          {{ filter.title }}
        </v-btn>
      </v-btn-toggle>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <v-card>
      <v-progress-linear v-if="loading" indeterminate />
      <v-table>
        <thead>
          <tr>
            <th>質問</th>
            <th>状態</th>
            <th class="text-end">表示回数</th>
            <th>更新日</th>
            <th class="text-end">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(faq, index) in items" :key="faq.id">
            <td>
              <span class="d-inline-block text-truncate" style="max-width: 380px">{{ faq.question }}</span>
            </td>
            <td>
              <v-chip size="small" variant="tonal" :color="STATUS_COLORS[faq.status]">{{ faq.status_label }}</v-chip>
            </td>
            <td class="text-end">{{ faq.view_count }}</td>
            <td class="text-no-wrap">{{ formatDate(faq.updated_at) }}</td>
            <td class="text-end text-no-wrap">
              <v-btn
                icon="mdi-arrow-up"
                size="small"
                variant="text"
                aria-label="上へ"
                :disabled="!canReorder || index === 0"
                @click="move(index, -1)"
              />
              <v-btn
                icon="mdi-arrow-down"
                size="small"
                variant="text"
                aria-label="下へ"
                :disabled="!canReorder || index === items.length - 1"
                @click="move(index, 1)"
              />
              <v-btn size="small" variant="outlined" class="mx-1" @click="togglePublish(faq)">
                {{ faq.status === 'published' ? '非公開にする' : '公開する' }}
              </v-btn>
              <v-btn icon="mdi-pencil-outline" size="small" variant="text" aria-label="編集" @click="openEdit(faq)" />
              <v-btn
                icon="mdi-delete-outline"
                size="small"
                variant="text"
                color="error"
                aria-label="削除"
                @click="deleting = faq"
              />
            </td>
          </tr>
          <tr v-if="!items.length && !loading">
            <td colspan="5" class="text-center text-medium-emphasis py-6">FAQはありません</td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <AdminFaqEditDialog
      v-model="editOpen"
      title="FAQの編集"
      save-label="保存"
      :initial-question="editing?.question ?? ''"
      :initial-answer="editing?.answer ?? ''"
      :sources="editing?.sources ?? []"
      :saving="saving"
      :error="saveError"
      @save="save"
    />

    <v-dialog v-model="deleteOpen" max-width="440">
      <v-card title="FAQを削除しますか？">
        <v-card-text>「{{ deleting?.question }}」を削除します。この操作は元に戻せません。</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="deleting = null">キャンセル</v-btn>
          <v-btn color="error" variant="flat" @click="confirmDelete">削除する</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-dialog v-model="publishAllOpen" max-width="440">
      <v-card title="要確認のFAQを公開に戻しますか？">
        <v-card-text>
          要確認のFAQを、すべて公開に戻します。規程の改定に合わせて、内容を確認したことを前提にします。
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="publishAllOpen = false">キャンセル</v-btn>
          <v-btn color="primary" variant="flat" @click="confirmPublishAll">公開に戻す</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>
