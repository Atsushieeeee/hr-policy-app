<script setup lang="ts">
definePageMeta({ admin: true, layout: 'admin' })

// 入力が止まってから、検索する
const SEARCH_DELAY_MS = 500

const notification = useNotificationStore()
const { items, total, loading, error, loadCandidates, grant } = useAdminUsers()

const keyword = ref('')
const query = ref('')
const page = ref(1)
const itemsPerPage = ref(20)
const selected = ref<number[]>([])
const confirming = ref(false)
const granting = ref(false)
// 最初の読み込みが終わったか（候補が0人のときの案内に使う）
const loaded = ref(false)

// ページをまたいで選択しても、確認ダイアログに名前を出せるよう、表示した人の名前を覚えておく
const names = new Map<number, string>()
watch(items, (list) => list.forEach((u) => names.set(u.id, u.name)))
const selectedNames = computed(() => selected.value.map((id) => names.get(id) ?? `ID ${id}`))

const noCandidates = computed(() => loaded.value && !loading.value && total.value === 0 && query.value === '')

let timer: ReturnType<typeof setTimeout> | null = null
watch(keyword, (value) => {
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => {
    query.value = value.trim()
  }, SEARCH_DELAY_MS)
})
onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
})

// 検索語が変わったら、1ページ目に戻す（選択は、そのまま残す）
watch(query, () => {
  page.value = 1
})

const reload = async () => {
  await loadCandidates(page.value, itemsPerPage.value, query.value)
  loaded.value = true
  // 範囲外のページになったときは、1つ前のページに戻る（page の変更で、再取得される）
  if (items.value.length === 0 && page.value > 1) page.value -= 1
}

onMounted(reload)
watch([page, itemsPerPage, query], reload)

const onGrant = async () => {
  granting.value = true
  const count = selected.value.length
  const ok = await grant(selected.value)
  confirming.value = false
  granting.value = false
  if (ok) {
    notification.show(`${count}人を管理者にしました`)
    await navigateTo('/admin/list')
    return
  }
  // 失敗したときは、選択を残したまま、最新の状態を表示する
  await reload()
}
</script>

<template>
  <v-container max-width="960">
    <div class="d-flex align-center mb-4">
      <h1 class="text-h6">管理者を追加</h1>
      <v-spacer />
      <v-btn variant="text" prepend-icon="mdi-arrow-left" to="/admin/list">一覧に戻る</v-btn>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert>
    <v-alert v-if="noCandidates" type="info" variant="tonal" class="mb-4">
      追加できるユーザーがいません。
    </v-alert>

    <v-card>
      <v-card-text>
        <v-text-field
          v-model="keyword"
          label="名前・メールアドレスで検索"
          prepend-inner-icon="mdi-magnify"
          density="comfortable"
          hide-details
          clearable
        />
      </v-card-text>
      <AdminUserTable
        v-model="selected"
        :page="page"
        :items-per-page="itemsPerPage"
        :items="items"
        :total="total"
        :loading="loading"
        @update:page="page = $event"
        @update:items-per-page="itemsPerPage = $event"
      />
      <v-card-actions class="px-4 pb-4">
        <span v-if="selected.length" class="text-medium-emphasis">{{ selected.length }}人を選択中</span>
        <v-spacer />
        <v-btn
          color="primary"
          variant="flat"
          :disabled="selected.length === 0 || granting"
          @click="confirming = true"
        >
          管理者にする
        </v-btn>
      </v-card-actions>
    </v-card>

    <v-dialog v-model="confirming" max-width="440">
      <v-card title="管理者にしますか？">
        <v-card-text>
          次の{{ selected.length }}人に、管理者権限を付与します。
          <ul class="mt-2 ml-4">
            <li v-for="name in selectedNames" :key="name">{{ name }}</li>
          </ul>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn :disabled="granting" @click="confirming = false">キャンセル</v-btn>
          <v-btn color="primary" variant="flat" :loading="granting" @click="onGrant">管理者にする</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>
