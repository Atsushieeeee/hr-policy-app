<script setup lang="ts">
const { health, error, loading, check } = useHealth()

onMounted(check)
</script>

<template>
  <v-card max-width="480" class="mx-auto mt-16" title="接続状態">
    <v-card-text>
      <div v-if="loading" class="d-flex align-center ga-3">
        <v-progress-circular indeterminate size="24" />
        確認中...
      </div>

      <v-alert v-else-if="error" type="error" variant="tonal">
        {{ error }}
      </v-alert>

      <v-list v-else-if="health" density="compact">
        <v-list-item title="バックエンド" :subtitle="health.status" />
        <v-list-item title="データベース" :subtitle="health.db" />
      </v-list>
    </v-card-text>

    <v-card-actions>
      <v-btn :disabled="loading" @click="check">再確認</v-btn>
    </v-card-actions>
  </v-card>
</template>
