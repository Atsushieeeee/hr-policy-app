import vuetify, { transformAssetUrls } from 'vite-plugin-vuetify'

// コンテナ内からバックエンドへ中継する際の宛先（docker compose のサービス名）
const apiProxyTarget = process.env.API_PROXY_TARGET || 'http://backend:8000'

export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  // 認証必須の社内アプリでSEOは不要なため、SPAモードで動かす
  ssr: false,
  devtools: { enabled: true },

  // composables/api 配下は、リソースごとのサブディレクトリも自動インポートの対象にする
  imports: { dirs: ['composables/api/**'] },

  css: ['@mdi/font/css/materialdesignicons.css', 'vuetify/styles'],
  build: { transpile: ['vuetify'] },
  vite: {
    vue: { template: { transformAssetUrls } },
  },
  modules: [
    '@nuxt/eslint',
    '@pinia/nuxt',
    (_options, nuxt) => {
      nuxt.hooks.hook('vite:extendConfig', (config) => {
        config.plugins!.push(vuetify({ autoImport: true }))
      })
    },
  ],

  // ブラウザからは同一オリジンの /api/* を呼び、Nuxtがバックエンドへ中継する（CORS設定が不要）
  routeRules: {
    '/api/**': { proxy: `${apiProxyTarget}/api/**` },
  },
})
