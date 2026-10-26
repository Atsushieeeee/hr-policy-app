<script setup lang="ts">
const auth = useAuthStore()
</script>

<template>
  <div>
    <CommonAppHeader v-if="auth.isLoggedIn" />
    <v-main>
      <slot />
    </v-main>
  </div>
</template>
