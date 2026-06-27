.PHONY: install backend frontend dev test lint fmt clean

install:
	cd backend && uv venv && uv pip install -e ".[dev]"
	cd frontend && npm install

backend:
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

# Run both: backend in the background, frontend in the foreground.
dev:
	cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 & \
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -q

lint:
	cd backend && uv run ruff check app

fmt:
	cd backend && uv run ruff format app

clean:
	rm -rf backend/data backend/.pytest_cache backend/.ruff_cache
