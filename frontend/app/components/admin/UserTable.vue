<script setup lang="ts">
import type { AdminUser } from '~/composables/api/admin/useAdminUsers'

defineProps<{
  items: AdminUser[]
  total: number
  loading: boolean
  /** チェックできない行（自分自身など）のID */
  disabledIds?: number[]
  /** 行の名前の横に付ける印（自分の行など）。ID を指定する */
  markedId?: number
  page: number
  itemsPerPage: number
}>()

const emit = defineEmits<{
  'update:page': [page: number]
  'update:itemsPerPage': [itemsPerPage: number]
}>()

// 選択（ユーザーID）は、ページをまたいで保持される
const selected = defineModel<number[]>({ required: true })

// ソートは、しない（並びは、登録日の古い順）
const headers = [
  { title: '名前', key: 'name', sortable: false },
  { title: 'メールアドレス', key: 'email', sortable: false },
  { title: '登録日', key: 'created_at', sortable: false },
]

const formatDate = (iso: string) => new Date(iso).toLocaleDateString('ja-JP')
</script>

<template>
  <v-data-table-server
    v-model="selected"
    :page="page"
    :items-per-page="itemsPerPage"
    :headers="headers"
    :items="items"
    :items-length="total"
    :loading="loading"
    :items-per-page-options="[10, 20, 50]"
    :item-selectable="(item: AdminUser) => !disabledIds?.includes(item.id)"
    item-value="id"
    items-per-page-text="1ページの件数"
    page-text="{0}〜{1}人（全{2}人）"
    loading-text="読み込み中..."
    no-data-text="該当するユーザーがいません"
    show-select
    @update:page="emit('update:page', $event)"
    @update:items-per-page="emit('update:itemsPerPage', $event)"
  >
    <template #[`item.name`]="{ item }">
      {{ item.name }}
      <v-chip v-if="item.id === markedId" size="x-small" class="ml-2">あなた</v-chip>
    </template>
    <template #[`item.created_at`]="{ item }">{{ formatDate(item.created_at) }}</template>
  </v-data-table-server>
</template>
