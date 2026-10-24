# 就業規則アプリ

就業規則のPDFを管理者がアップロードし、社員がチャット形式で質問すると、就業規則の記載内容に基づいてAIが回答するWebアプリ。

> 開発中（準備段階）。起動手順・画面・デモアカウントは今後追記します。

## 技術スタック

- フロントエンド: Nuxt / Vue / Vuetify
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

# 2. 起動（初回はイメージのビルドが入るため数分かかります）
docker compose up -d --build

# 3. 動作確認
curl http://127.0.0.1:8000/healthz
# => {"status":"ok","db":"ok"}
```

### 停止
```bash
docker compose down        # コンテナを停止・削除（DBのデータは残る）
docker compose down -v     # DBのデータも含めて削除
```

### サービスとポート
| サービス | 内容 | ホスト側のアドレス |
|---|---|---|
| backend | Django（開発サーバー） | http://127.0.0.1:8000 |
| db | MySQL 8.0 | 127.0.0.1:3307（DBクライアントからの接続用） |

- ポートはすべて `127.0.0.1` にのみ公開しています。ホストにMySQLが入っていても競合しないよう、DBは3307にしています（`.env` の `DB_HOST_PORT` で変更可）。
- `backend` はソースをマウントしているため、コードを変更すると自動で反映されます。
- フロントエンド（Nuxt）は今後追加します。

### ログの確認
```bash
docker compose logs -f backend
```
