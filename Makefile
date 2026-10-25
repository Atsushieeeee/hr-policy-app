# docker compose up -d で起動している状態で実行する
.PHONY: lint-backend fmt-backend test-backend

lint-backend:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format --check .

fmt-backend:
	docker compose exec backend ruff check --fix .
	docker compose exec backend ruff format .

# テスト用DBを作成できるよう、rootで接続する
test-backend:
	docker compose exec backend sh -c 'MYSQL_USER=root MYSQL_PASSWORD="$$MYSQL_ROOT_PASSWORD" pytest'
