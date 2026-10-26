<script setup lang="ts">
const auth = useAuthStore()
const { logout } = useAuth()

const onLogout = async () => {
  await logout()
  await navigateTo('/login')
}
</script>

<template>
  <v-app-bar flat border>
    <v-app-bar-title>
      <NuxtLink to="/chat" class="text-decoration-none text-high-emphasis">就業規則アプリ</NuxtLink>
    </v-app-bar-title>

    <span class="mr-2">{{ auth.user?.name }}</span>

    <v-menu v-if="auth.isAdmin">
      <template #activator="{ props }">
        <v-btn v-bind="props" icon="mdi-cog" aria-label="管理メニュー" />
      </template>
      <v-list>
        <v-list-item to="/admin/upload" title="管理者画面へ" />
      </v-list>
    </v-menu>

    <v-btn icon="mdi-logout" aria-label="ログアウト" @click="onLogout" />
  </v-app-bar>
</template>
