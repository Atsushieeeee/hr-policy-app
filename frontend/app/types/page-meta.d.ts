// definePageMeta で指定できる、独自のルート設定
declare module '#app' {
  interface PageMeta {
    /** false にするとログイン不要のページになる（既定はログイン必須） */
    auth?: boolean
    /** true にすると、管理者権限を持つユーザーだけが開ける */
    admin?: boolean
    /** true にすると、ログイン済みのユーザーは開けない（ログイン画面など） */
    guestOnly?: boolean
  }
}

export {}
