<script setup lang="ts">
const route = useRoute()
const { login, loading, error } = useAuth()

const email = ref('')
const password = ref('')

const canSubmit = computed(() => email.value.trim() !== '' && password.value !== '' && !loading.value)

const submit = async () => {
  if (!canSubmit.value) return
  const ok = await login(email.value.trim(), password.value)
  if (ok) {
    await navigateTo(safeRedirect(route.query.redirect))
  }
}
</script>

<template>
  <v-card max-width="400" class="mx-auto mt-16" title="ログイン">
    <v-card-text>
      <v-form @submit.prevent="submit">
        <v-text-field
          v-model="email"
          label="メールアドレス"
          type="email"
          autocomplete="username"
          :disabled="loading"
        />
        <v-text-field
          v-model="password"
          label="パスワード"
          type="password"
          autocomplete="current-password"
          :disabled="loading"
        />
        <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
        <v-btn type="submit" color="primary" block :disabled="!canSubmit" :loading="loading">
          ログイン
        </v-btn>
      </v-form>
    </v-card-text>
  </v-card>
</template>
