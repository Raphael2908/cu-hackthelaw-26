#!/usr/bin/env bash
set -euo pipefail

ROLE="${ROLE:-api}"

case "$ROLE" in
  api)
    exec uvicorn app.main:app --host "${API_HOST:-0.0.0.0}" --port "${API_PORT:-8000}"
    ;;
  worker)
    exec celery -A app.celery_app.celery_app worker --loglevel="${LOG_LEVEL:-info}" \
      -Q q.plan,q.research,q.doc,q.rerank,q.eval,q.synth
    ;;
  beat)
    exec celery -A app.celery_app.celery_app beat --loglevel="${LOG_LEVEL:-info}"
    ;;
  *)
    echo "Unknown ROLE: $ROLE" >&2
    exit 1
    ;;
esac
