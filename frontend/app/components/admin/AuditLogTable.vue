<script setup lang="ts">
import type { AuditLog } from '~/composables/api/admin/useAuditLogs'

defineProps<{
  items: AuditLog[]
  total: number
  loading: boolean
  page: number
  itemsPerPage: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
  'update:itemsPerPage': [itemsPerPage: number]
}>()

// ソートは、しない（並びは、新しい順）
const headers = [
  { title: '日時', key: 'created_at', sortable: false },
  { title: '操作', key: 'action_label', sortable: false },
  { title: '操作者', key: 'actor_email', sortable: false },
  { title: '内容', key: 'detail', sortable: false },
  { title: 'IPアドレス', key: 'ip', sortable: false },
]

const formatDate = (iso: string) => new Date(iso).toLocaleString('ja-JP')

const LOGIN_FAILURE_REASONS: Record<string, string> = {
  invalid_credentials: 'パスワード違い',
  locked: 'ロック中',
}

const str = (v: unknown) => (v === null || v === undefined ? '' : String(v))

// 開いたときに出す、項目の表示名。この順に並べる。ここにない項目は、項目名のまま、最後に出す
const DETAIL_LABELS: Record<string, string> = {
  reason: '理由',
  email: 'メールアドレス',
  old_filename: '置き換え前のファイル',
  new_filename: '置き換え後のファイル',
  page_count: 'ページ数',
  filename: 'ファイル名',
  created: '作成',
  skipped: 'スキップ',
  errors: 'エラー',
}

const detailValue = (key: string, value: unknown): string => {
  if (key === 'reason') return LOGIN_FAILURE_REASONS[str(value)] ?? str(value)
  if (key === 'old_filename' && !value) return 'なし（新規登録）'
  if (key === 'page_count') return `${str(value)}ページ`
  if (['created', 'skipped', 'errors'].includes(key)) return `${str(value)}件`
  return str(value) || '—'
}

const DETAIL_ORDER = Object.keys(DETAIL_LABELS)
const orderOf = (key: string) => {
  const i = DETAIL_ORDER.indexOf(key)
  return i === -1 ? DETAIL_ORDER.length : i
}

const detailRows = (log: AuditLog) =>
  Object.entries(log.detail)
    .sort(([a], [b]) => orderOf(a) - orderOf(b))
    .map(([key, value]) => ({ label: DETAIL_LABELS[key] ?? key, value: detailValue(key, value) }))

// 操作ごとに、detail を人が読める文にする。対応していない操作は、「項目=値」を並べる
const formatDetail = ({ action, detail: d }: AuditLog): string => {
  switch (action) {
    case 'login.success':
      return '—'
    case 'login.failure':
      return LOGIN_FAILURE_REASONS[str(d.reason)] ?? str(d.reason)
    case 'admin.grant':
    case 'admin.revoke':
      return str(d.email)
    case 'policy.replace':
      return `${str(d.old_filename) || '新規登録'} → ${str(d.new_filename)}（${str(d.page_count)}ページ）`
    case 'users.import':
      return `${str(d.filename)}（作成${str(d.created)}件、スキップ${str(d.skipped)}件、エラー${str(d.errors)}件）`
    default:
      return Object.entries(d).map(([k, v]) => `${k}=${str(v)}`).join(', ') || '—'
  }
}
</script>

<template>
  <v-data-table-server
    :page="page"
    :items-per-page="itemsPerPage"
    :headers="headers"
    :items="items"
    :items-length="total"
    :loading="loading"
    :items-per-page-options="[10, 20, 50, 100]"
    item-value="id"
    items-per-page-text="1ページの件数"
    page-text="{0}〜{1}件（全{2}件）"
    loading-text="読み込み中..."
    no-data-text="記録はありません"
    show-expand
    @update:page="emit('update:page', $event)"
    @update:items-per-page="emit('update:itemsPerPage', $event)"
  >
    <template #[`item.created_at`]="{ item }">
      <span class="text-no-wrap">{{ formatDate(item.created_at) }}</span>
    </template>
    <template #[`item.actor_email`]="{ item }">
      <template v-if="item.actor_name">
        {{ item.actor_name }}
        <div class="text-caption text-medium-emphasis">{{ item.actor_email }}</div>
      </template>
      <template v-else>{{ item.actor_email || '—' }}</template>
    </template>
    <template #[`item.detail`]="{ item }">
      <span class="d-inline-block text-truncate" style="max-width: 360px">
        {{ formatDetail(item) || '—' }}
      </span>
    </template>
    <!-- 開いて見せる内容がない行には、開く矢印を出さない -->
    <template #[`item.data-table-expand`]="{ item, internalItem, isExpanded, toggleExpand }">
      <v-btn
        v-if="detailRows(item).length"
        :icon="isExpanded(internalItem) ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        :aria-label="isExpanded(internalItem) ? '閉じる' : '内容を開く'"
        variant="text"
        size="small"
        @click="toggleExpand(internalItem)"
      />
    </template>
    <template #expanded-row="{ columns, item }">
      <tr>
        <td :colspan="columns.length" class="py-3">
          <v-table density="compact" class="bg-transparent">
            <tbody>
              <tr v-for="row in detailRows(item)" :key="row.label">
                <th class="text-medium-emphasis text-no-wrap" style="width: 200px">{{ row.label }}</th>
                <td>{{ row.value }}</td>
              </tr>
            </tbody>
          </v-table>
        </td>
      </tr>
    </template>
    <template #[`item.ip`]="{ item }">{{ item.ip ?? '—' }}</template>
  </v-data-table-server>
</template>
