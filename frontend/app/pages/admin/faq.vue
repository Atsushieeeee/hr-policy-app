<script setup lang="ts">
definePageMeta({ admin: true, layout: 'admin' })

const tab = ref<'candidates' | 'list'>('candidates')
</script>

<template>
  <v-container max-width="1200">
    <h1 class="text-h6 mb-2">FAQ</h1>

    <v-tabs v-model="tab" color="primary" class="mb-4">
      <v-tab value="candidates">FAQ候補</v-tab>
      <v-tab value="list">FAQ一覧</v-tab>
    </v-tabs>

    <!-- タブを切り替えるたびに作り直し、最新の内容を読み込む -->
    <AdminFaqCandidates v-if="tab === 'candidates'" />
    <AdminFaqList v-else />
  </v-container>
</template>
