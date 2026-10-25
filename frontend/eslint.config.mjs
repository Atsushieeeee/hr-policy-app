// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt({
  rules: {
    // 関数はアロー関数（const name = () => {}）に統一する
    'func-style': ['error', 'expression'],
    'prefer-arrow-callback': 'error',
  },
})
