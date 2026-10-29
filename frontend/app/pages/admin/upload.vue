<script setup lang="ts">
definePageMeta({ admin: true, layout: 'admin' })

const { current, upload, pdfUrl, loading, uploading, error, succeeded, load, submit } = usePolicy()

onMounted(load)
</script>

<template>
  <v-container max-width="960">
    <h1 class="text-h6 mb-4">就業規則</h1>

    <div v-if="loading" class="d-flex align-center ga-3">
      <v-progress-circular indeterminate size="24" />
      読み込み中...
    </div>

    <template v-else>
      <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
      <v-alert v-if="succeeded" type="success" variant="tonal" class="mb-4">
        規程を更新しました。以降の質問は、新しい規程に基づいて回答します。
      </v-alert>

      <v-card title="規程のアップロード" class="mb-6">
        <v-card-text>
          <AdminPolicyUploader
            :has-policy="current !== null"
            :upload="upload"
            :uploading="uploading"
            @submit="submit"
          />
        </v-card-text>
      </v-card>

      <v-card title="現行の規程">
        <template v-if="current">
          <v-card-text>
            <AdminPolicyInfo :policy="current" />
          </v-card-text>
          <AdminPolicyPreview :url="pdfUrl" />
        </template>
        <v-card-text v-else class="text-medium-emphasis">
          まだ規程が登録されていません。PDFをアップロードしてください。
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>
