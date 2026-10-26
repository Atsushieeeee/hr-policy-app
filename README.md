# 就業規則アプリ

就業規則のPDFを管理者がアップロードし、社員がチャット形式で質問すると、就業規則の記載内容に基づいてAIが回答するWebアプリ。

> 開発中（準備段階）。起動手順・画面・デモアカウントは今後追記します。

## 技術スタック

- フロントエンド: Nuxt 4 / Vue 3 / Vuetify 3（TypeScript、SPAモード）
- バックエンド: Django / Django REST Framework
- DB: MySQL
- AI: Gemini API（検証）→ さくらのAI Engine（移行予定）
- 環境: Docker / Docker Compose

## 起動方法

### 前提
- Docker / Docker Compose（Docker Desktop など）がインストールされ、起動していること

### 手順
```bash
# 1. 環境変数ファイルを作成（値は必要に応じて編集）
cp .env.example .env
#    チャットを試す場合は、.env の GEMINI_API_KEY に Gemini の APIキーを設定する
#    （Google AI Studio https://aistudio.google.com で無料枠のキーを発行できます）

# 2. 起動（初回はイメージのビルドが入るため数分かかります）
docker compose up -d --build

# 3. DBのマイグレーションと、デモユーザーの作成（初回のみ）
make setup

# 4. 動作確認
curl http://127.0.0.1:8000/healthz
# => {"status":"ok","db":"ok"}

# 5. ブラウザで画面を開く
#    http://127.0.0.1:3000         ログイン画面（デモユーザーでログイン）
#    http://127.0.0.1:3000/chat    チャット画面（就業規則への質問）
#    http://127.0.0.1:3000/status  バックエンドとDBの接続状態（ログイン不要）
```

### ユーザーについて
- ユーザーの登録画面はありません。コマンドで作成します（`docker compose up -d` で起動している状態で実行）。

```bash
make migrate    # マイグレーションを適用
make seed       # デモユーザーを作成（.env の DEMO_PASSWORD がパスワード）
docker compose exec backend python manage.py create_user --email a@example.com --name 名前 [--admin]
docker compose exec backend python manage.py set_password --email a@example.com
```

- 新しいマイグレーションを含む変更を取り込んだ（`git pull` した）ときは、`make migrate` を実行してください。
- `create_user` と `set_password` は、`--password` を省略すると画面で入力を求めます（パスワードは12文字以上）。

デモユーザー（`make seed`）:

| メールアドレス | 権限 |
|---|---|
| admin@example.com | 管理者 |
| employee1@example.com 〜 employee3@example.com | 社員 |

### 画面とログイン
- 画面は、ログインしていないと開けません（開くと、ログイン画面に移ります。ログイン後は、元の画面に戻ります）。
- 管理者権限のあるユーザーには、ヘッダーに歯車アイコンが表示され、管理者画面（`/admin/...`）を開けます。管理者権限のないユーザーが開こうとすると、チャット画面に戻されます。
- アクセストークンはメモリにだけ保持し、ページを再読み込みしたときは、リフレッシュトークン（Cookie）で、ログイン状態を復元します。
- 画面の振り分けは、使いやすさのためのものです。権限のチェックは、バックエンドが行います。

### 認証API
- ログインすると、アクセストークン（15分）がレスポンスで返り、リフレッシュトークン（7日）は HttpOnly の Cookie に入ります。
- 認証が必要なAPIには、アクセストークンを `X-Access-Token` ヘッダで送ります（公開時にBasic認証を前段に置いても干渉しないよう、`Authorization` ヘッダは使いません）。

| メソッド | パス | 内容 |
|---|---|---|
| POST | /api/v1/auth/login | ログイン（`email`、`password`） |
| POST | /api/v1/auth/refresh | アクセストークンの再発行（Cookie使用、リフレッシュトークンも入れ替え） |
| POST | /api/v1/auth/logout | ログアウト（リフレッシュトークンを無効化） |
| GET | /api/v1/me | ログイン中のユーザー情報（`X-Access-Token` が必要） |

```bash
curl -c cookie.txt -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"demo-password"}'
curl http://127.0.0.1:8000/api/v1/me -H "X-Access-Token: <loginで返ったaccess>"
```

- チャットAPI（`POST /api/v1/chat/messages`）は、ログインが必要です。管理者権限の有無に関わらず、ログイン済みのユーザーなら使えます（未認証は 401）。
- `/api/v1/admin/` 配下は、管理者権限（`is_admin`）を持つユーザーだけが使えます（未認証は 401、管理者権限なしは 403）。動作確認用に `GET /api/v1/admin/ping` があります。権限は、トークンではなく DB の現在値で判定するため、変更は次のリクエストから反映されます。
- 管理者用 API は、`core.views.AdminAPIView` を継承して作り、`config/urls.py` の `admin_urlpatterns` に登録します。権限のテストが、登録されたすべての API を自動で検証します。
- エラーは、すべて `{ "error": { "code": "...", "message": "..." } }` の形で返ります。
- `DJANGO_SECRET_KEY` はトークンの署名にも使うため、`DJANGO_DEBUG=false` の環境では32文字以上が必要です。

### AIについて
- 現在は、固定のダミー就業規則（`backend/rag/data/dummy_policy.txt`、架空の会社）に基づいて回答します。規程のアップロード機能は今後追加します。
- 使用するモデルは `.env` の `GEMINI_MODEL` で変更できます。無料枠では、モデルによって混雑や提供終了で失敗することがあります。
- APIキーなしで画面を確認したい場合は、`.env` の `RAG_BACKEND=fake` にすると、AIを呼ばず固定の回答を返します。

### 停止
```bash
docker compose down        # コンテナを停止・削除（DBのデータは残る）
docker compose down -v     # DBのデータも含めて削除
```

### サービスとポート
| サービス | 内容 | ホスト側のアドレス |
|---|---|---|
| frontend | Nuxt（開発サーバー） | http://127.0.0.1:3000 |
| backend | Django（開発サーバー） | http://127.0.0.1:8000 |
| db | MySQL 8.0 | 127.0.0.1:3307（DBクライアントからの接続用） |

- ポートはすべて `127.0.0.1` にのみ公開しています。ホストにMySQLが入っていても競合しないよう、DBは3307にしています（`.env` の `DB_HOST_PORT` で変更可）。
- `frontend` と `backend` はソースをマウントしているため、コードを変更すると自動で反映されます。
- ブラウザからのAPI呼び出しは、同一オリジンの `/api/v1/*` に送り、Nuxtがバックエンドへ中継します（CORS設定が不要）。

### 開発（Lint・テスト）
`docker compose up -d` で起動している状態で、次のコマンドを実行します。

```bash
make lint-backend   # ruff（Lint・フォーマット確認）
make fmt-backend    # ruff（自動修正・整形）
make test-backend   # pytest（テスト用DBを作成するため、rootで接続）

make lint-frontend       # ESLint（関数はアロー関数に統一）
make fmt-frontend        # ESLint（自動修正）
make typecheck-frontend  # 型チェック（vue-tsc）
```

- 変更は、PR 作成時に GitHub Actions（`backend.yml` / `frontend.yml`）で、同じ内容が自動で検査されます。
- フロントの依存パッケージ（`package.json`）を変更したときは、`docker compose up -d --build -V` で起動し直してください。`node_modules` はコンテナ内の保存領域に残るため、`-V` を付けないと古いまま使われます。

### ログの確認
```bash
docker compose logs -f backend   # frontend も同様
```
