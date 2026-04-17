#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[init] uv sync --dev"
uv sync --dev

echo "[init] docker-compose up -d db"
docker-compose up -d db

echo "[init] waiting for postgres"
for _ in {1..30}; do
  if docker-compose exec -T db pg_isready -U zenigame_fx >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[init] alembic upgrade head"
uv run alembic upgrade head

echo "[init] done"
