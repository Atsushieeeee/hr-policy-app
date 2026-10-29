<script setup lang="ts">
import type { PolicyCurrent } from '~/composables/api/admin/usePolicy'

defineProps<{ policy: PolicyCurrent }>()

const formatDate = (iso: string) => new Date(iso).toLocaleString('ja-JP')
</script>

<template>
  <v-table density="compact">
    <tbody>
      <tr>
        <th class="text-no-wrap">ファイル名</th>
        <td>{{ policy.original_filename }}</td>
      </tr>
      <tr>
        <th class="text-no-wrap">アップロードした管理者</th>
        <td>{{ policy.uploaded_by.name }}</td>
      </tr>
      <tr>
        <th class="text-no-wrap">アップロード日時</th>
        <td>{{ formatDate(policy.uploaded_at) }}</td>
      </tr>
      <tr>
        <th class="text-no-wrap">ページ数</th>
        <td>{{ policy.page_count ?? '-' }}</td>
      </tr>
    </tbody>
  </v-table>
</template>
