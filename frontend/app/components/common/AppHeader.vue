<script setup lang="ts">
import { useDisplay } from 'vuetify'

const auth = useAuthStore()
const { logout } = useAuth()
const route = useRoute()
const { smAndDown } = useDisplay()

// 管理者画面にいるときは、歯車の代わりに、チャット画面へ戻るボタンを出す
const inAdmin = computed(() => route.path.startsWith('/admin'))

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

    <!-- 狭い画面では、アイコンだけにする -->
    <v-btn v-if="inAdmin && smAndDown" to="/chat" icon="mdi-chat-outline" aria-label="チャット画面へ戻る" />
    <v-btn v-else-if="inAdmin" to="/chat" prepend-icon="mdi-chat-outline">チャットへ</v-btn>

    <v-menu v-else-if="auth.isAdmin">
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
