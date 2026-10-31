<script setup lang="ts">
definePageMeta({ admin: true, layout: 'admin' })

const { items, total, actions, loading, error, load } = useAuditLogs()

const page = ref(1)
const itemsPerPage = ref(20)
const action = ref<string | null>(null)

const reload = () => load(page.value, itemsPerPage.value, action.value)

onMounted(reload)
watch([page, itemsPerPage], reload)
// 絞り込みを変えたら、1ページ目から表示する
watch(action, () => {
  if (page.value === 1) reload()
  else page.value = 1
})
</script>

<template>
  <v-container max-width="1200">
    <div class="d-flex align-center mb-4">
      <h1 class="text-h6">監査ログ</h1>
      <v-spacer />
      <v-select
        v-model="action"
        :items="actions"
        item-title="label"
        item-value="value"
        label="操作の種類"
        placeholder="すべて"
        density="compact"
        variant="outlined"
        clearable
        hide-details
        max-width="260"
      />
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <v-card>
      <AdminAuditLogTable
        :page="page"
        :items-per-page="itemsPerPage"
        :items="items"
        :total="total"
        :loading="loading"
        @update:page="page = $event"
        @update:items-per-page="itemsPerPage = $event"
      />
    </v-card>
  </v-container>
</template>
