<script setup lang="ts">
definePageMeta({ admin: true, layout: 'admin' })

const auth = useAuthStore()
const { items, total, loading, error, load, revoke } = useAdminUsers()

const page = ref(1)
const itemsPerPage = ref(20)
const selected = ref<number[]>([])
const confirming = ref(false)
const revoking = ref(false)
const message = ref<string | null>(null)

// ページをまたいで選択しても、確認ダイアログに名前を出せるよう、表示した人の名前を覚えておく
const names = new Map<number, string>()
watch(items, (list) => list.forEach((u) => names.set(u.id, u.name)))
const selectedNames = computed(() => selected.value.map((id) => names.get(id) ?? `ID ${id}`))

const onlyOne = computed(() => total.value === 1)
const canRevoke = computed(() => selected.value.length > 0 && !onlyOne.value && !revoking.value)

const reload = async () => {
  await load(page.value, itemsPerPage.value)
  // 最後のページの人を全員外したときは、1つ前のページに戻る（page の変更で、再取得される）
  if (items.value.length === 0 && page.value > 1) page.value -= 1
}

onMounted(reload)
watch([page, itemsPerPage], reload)

const onRevoke = async () => {
  revoking.value = true
  message.value = null
  const count = selected.value.length
  const ok = await revoke(selected.value)
  confirming.value = false
  if (ok) {
    selected.value = []
    message.value = `${count}人の管理者権限を外しました`
  }
  // 失敗（409など）したときも、最新の状態を表示する
  await reload()
  revoking.value = false
}
</script>

<template>
  <v-container max-width="960">
    <div class="d-flex align-center mb-4">
      <h1 class="text-h6">管理者一覧</h1>
      <v-spacer />
      <v-btn color="primary" prepend-icon="mdi-account-plus" to="/admin/create">管理者を追加</v-btn>
    </div>

    <v-alert v-if="message" type="success" variant="tonal" closable class="mb-4" @click:close="message = null">
      {{ message }}
    </v-alert>
    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>

    <v-card>
      <AdminUserTable
        v-model="selected"
        :page="page"
        :items-per-page="itemsPerPage"
        :items="items"
        :total="total"
        :loading="loading"
        :disabled-ids="auth.user ? [auth.user.id] : []"
        :marked-id="auth.user?.id"
        @update:page="page = $event"
        @update:items-per-page="itemsPerPage = $event"
      />
      <v-card-actions class="px-4 pb-4">
        <span v-if="onlyOne" class="text-medium-emphasis">管理者が1人のため、権限を外せません。</span>
        <span v-else-if="selected.length" class="text-medium-emphasis">{{ selected.length }}人を選択中</span>
        <v-spacer />
        <v-btn color="error" variant="flat" :disabled="!canRevoke" @click="confirming = true">
          管理者権限を外す
        </v-btn>
      </v-card-actions>
    </v-card>

    <v-dialog v-model="confirming" max-width="440">
      <v-card title="管理者権限を外しますか？">
        <v-card-text>
          次の{{ selected.length }}人から、管理者権限を外します。
          <ul class="mt-2 ml-4">
            <li v-for="name in selectedNames" :key="name">{{ name }}</li>
          </ul>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="revoking" @click="confirming = false">キャンセル</v-btn>
          <v-btn color="error" variant="flat" :loading="revoking" @click="onRevoke">外す</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
