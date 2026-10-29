<script setup lang="ts">
import { useDisplay } from 'vuetify'

const auth = useAuthStore()
const { mdAndUp } = useDisplay()

const items = [
  { title: '就業規則', to: '/admin/upload', icon: 'mdi-file-document-outline' },
  { title: '管理者一覧', to: '/admin/list', icon: 'mdi-account-key-outline' },
]
</script>

<template>
  <div>
    <CommonAppHeader v-if="auth.isLoggedIn" />

    <v-navigation-drawer v-if="mdAndUp" permanent width="220">
      <v-list nav>
        <v-list-item v-for="item in items" :key="item.to" :to="item.to" :prepend-icon="item.icon" :title="item.title" />
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <!-- 画面が狭いときは、左のナビの代わりに、上にタブで表示する -->
      <v-tabs v-if="!mdAndUp" color="primary">
        <v-tab v-for="item in items" :key="item.to" :to="item.to">{{ item.title }}</v-tab>
      </v-tabs>
      <slot />
    </v-main>
  </div>
</template>
