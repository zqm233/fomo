#!/bin/sh
set -e
cd /app

UVICORN=/app/.venv/bin/uvicorn
ALEMBIC=/app/.venv/bin/alembic

if [ ! -x "$UVICORN" ]; then
  echo "error: $UVICORN not found — image build may have failed during uv sync" >&2
  exit 1
fi

if [ "${SKIP_DB_MIGRATIONS:-}" != "1" ] && [ -x "$ALEMBIC" ]; then
  "$ALEMBIC" upgrade head
fi

exec "$UVICORN" main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
