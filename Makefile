# docker compose up -d で起動している状態で実行する
.PHONY: migrate seed setup lint-backend fmt-backend test-backend lint-frontend fmt-frontend typecheck-frontend

migrate:
	docker compose exec backend python manage.py migrate

# デモ用のユーザーを作成する（.env の DEMO_PASSWORD を使用）
seed:
	docker compose exec backend python manage.py seed_demo

# 初回用: マイグレーションとデモユーザーの作成
setup: migrate seed

lint-backend:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .

fmt-backend:
	docker compose exec backend ruff check --fix .
	docker compose exec backend ruff format .

# テスト用DBを作成できるよう、rootで接続する
test-backend:
	docker compose exec backend sh -c 'MYSQL_USER=root MYSQL_PASSWORD="$$MYSQL_ROOT_PASSWORD" pytest'

lint-frontend:
	docker compose exec frontend npm run lint

fmt-frontend:
	docker compose exec frontend npm run lint:fix

typecheck-frontend:
	docker compose exec frontend npm run typecheck
