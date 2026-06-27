---
name: run-build
description: Spin up a fresh local instance of the Supervision Cockpit via Docker Compose — rebuilds all images and starts redis + backend + worker + frontend together. Use when the user asks to "spin up a local instance", "run the build", "start the app", "bring the stack up", or otherwise wants the full app running locally in Docker (instead of make backend/make frontend separately).
---

# run-build — spin up the local Docker stack

Brings the whole Supervision Cockpit up via Docker Compose, rebuilding every time so the
latest code is running. Replaces starting the backend and frontend separately. Run from the
repo root `/Users/raphael/Develop/cu-hackthelaw-26`.

This is launch/infra only: it spins up the existing app and changes nothing in the
supervision spine. No agent verdicts, nothing auto-approved — architecture §14 is untouched.

## Steps

1. **Preflight.**
   - `docker compose version` — confirm Docker is running (v2 CLI, the `docker compose`
     space form). If it fails, tell the user to start Docker Desktop.
   - Confirm a repo-root `.env` exists (compose mounts it read-only into backend + worker).
     Real mode (`PROVIDER_MODE=real`) needs `ANTHROPIC_API_KEY` set in `.env`; for a
     keyless/offline run the user can set `PROVIDER_MODE=mock` in `.env` first.

2. **Rebuild and start (always fresh).** From the repo root:
   ```
   docker compose up -d --build
   ```
   `--build` forces a fresh image build (latest backend + frontend code); `-d` runs
   detached so the stack keeps running. The build runs `npm ci` and `uv pip install`, so
   it can take several minutes — use a long Bash timeout (e.g. 600000 ms) or run it in the
   background and poll.

3. **Wait until healthy.** Poll `docker compose ps` until `backend` shows `healthy`
   (its healthcheck hits `/healthz`; `frontend` only starts once backend is healthy).

4. **Smoke-check.**
   - `curl -fsS http://localhost:8000/healthz` → expect a 200.
   - Confirm the frontend answers on `http://localhost:3000`.

5. **Report to the user.** Surface:
   - Cockpit / frontend: http://localhost:3000
   - API base: http://localhost:8000/api  (health: http://localhost:8000/healthz)
   - Services up: redis, backend, worker, frontend.

## Operating the stack

- Tail logs: `docker compose logs -f` (or `... logs -f backend` / `frontend` / `worker`).
- Stop, keeping the SQLite data volume: `docker compose down`.
- Full reset (drops the `backend-data` SQLite volume too): `docker compose down -v`.

## Notes

- The browser reaches the backend at `http://localhost:8000` via the `8000:8000` host port
  mapping (set as `NEXT_PUBLIC_API_BASE_URL` in `docker-compose.yml`). Because every page is
  client-rendered, this is correct — do **not** switch it to `http://backend:8000`, which the
  host browser cannot resolve.
- If a rebuild misbehaves, `docker compose down` then re-run step 2 for a clean recreate.
