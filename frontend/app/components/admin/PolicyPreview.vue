<script setup lang="ts">
defineProps<{ url: string | null }>()
</script>

<template>
  <iframe v-if="url" :src="url" title="現行の規程のPDF" class="preview" />
  <div v-else class="d-flex align-center ga-3 pa-4">
    <v-progress-circular indeterminate size="24" />
    PDFを読み込み中...
  </div>
</template>

<style scoped>
.preview {
  width: 100%;
  height: 70vh;
  border: 0;
}
</style>
