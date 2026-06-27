# Supervision Cockpit — backend (FastAPI, Python 3.12, uv)
FROM python:3.12-slim

# uv for fast, lockfile-faithful installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install deps first for layer caching. Editable install needs the app package
# present (hatchling builds packages=["app"]), so copy it before installing.
COPY pyproject.toml uv.lock ./
COPY app ./app
RUN uv pip install --system -e ".[dev]"

EXPOSE 8000

# config.py reads ./.env (mounted by compose); SQLITE_PATH=data/ lives on a volume.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
