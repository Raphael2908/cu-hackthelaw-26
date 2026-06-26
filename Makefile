.PHONY: up down build logs ps test lint fmt migrate maintenance-on maintenance-off

up:
	docker compose up --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check .

fmt:
	cd backend && uv run ruff format .

# Apply Supabase migrations manually (requires $DATABASE_URL pointing at the project's Postgres).
migrate:
	@for f in infra/supabase/migrations/*.sql; do echo "applying $$f"; psql "$$DATABASE_URL" -f "$$f"; done

maintenance-on:
	docker compose exec redis redis-cli SET maintenance 1

maintenance-off:
	docker compose exec redis redis-cli DEL maintenance
