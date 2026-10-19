#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

: "${APP_ENV:=development}"
export APP_ENV

echo "[1/6] Validating Python syntax"
python3 -m compileall -q apps/api/app apps/api/alembic/versions

echo "[2/6] Running source/regression test suite"
(cd apps/api && python3 -m pytest -q -p no:cacheprovider)

echo "[3/6] Starting Docker stack without deleting volumes"
docker compose -f infra/docker-compose.yml up -d --build

echo "[4/6] Waiting for API health"
for i in $(seq 1 60); do
  if curl -fsS http://localhost:8000/health >/dev/null; then break; fi
  if [ "$i" -eq 60 ]; then
    docker compose -f infra/docker-compose.yml ps
    docker compose -f infra/docker-compose.yml logs --tail=200 api
    exit 1
  fi
  sleep 2
done

echo "[5/6] Verifying migrations and service health"
docker compose -f infra/docker-compose.yml exec -T api alembic current
curl -fsS http://localhost:8000/health

if [ -n "${E2E_ADMIN_EMAIL:-}" ] && [ -n "${E2E_ADMIN_PASSWORD:-}" ]; then
  echo "[6/6] Running authenticated HTTP smoke tests"
  python3 e2e/runtime_smoke.py
else
  echo "[6/6] Authenticated smoke tests skipped: set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to run them."
fi

echo "Runtime acceptance completed. Docker volumes were preserved."
