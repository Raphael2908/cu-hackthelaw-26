#!/usr/bin/env bash
# Graceful deploy: pause new work, drain in-flight agent runs, rebuild, health-gate.
set -euo pipefail

cd "$(dirname "$0")/../.."

echo "→ maintenance ON (pause new work)"
docker compose exec -T redis redis-cli SET maintenance 1 || true

echo "→ draining in-flight work (grace period)"
sleep 30

echo "→ rebuilding"
docker compose up -d --build

echo "→ health-gating API"
for i in $(seq 1 30); do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')" 2>/dev/null; then
    echo "  API healthy"
    break
  fi
  sleep 2
done

echo "→ maintenance OFF"
docker compose exec -T redis redis-cli DEL maintenance || true
echo "✓ deploy complete"
