<script setup lang="ts">
// ルートは、チャット画面へ振り分けるだけ（未ログインならルートガードがログイン画面へ送る）
await navigateTo('/chat', { replace: true })
</script>

<template>
  <div />
</template>
