<script setup lang="ts">
const notification = useNotificationStore()
</script>

<template>
  <v-snackbar
    :key="notification.sequence"
    v-model="notification.visible"
    :color="notification.type"
    :timeout="4000"
    location="bottom"
  >
    {{ notification.message }}
    <template #actions>
      <v-btn variant="text" @click="notification.hide()">閉じる</v-btn>
    </template>
  </v-snackbar>
</template>
