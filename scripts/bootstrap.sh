#!/usr/bin/env bash
# One-shot Fase 1 bootstrap: start DB, migrate, install scrapers, download OCDS + SUNAT.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "▸ 1/5  Starting Postgres + pgvector (docker)..."
docker compose -f infra/docker/docker-compose.yml up -d
sleep 5

echo "▸ 2/5  Applying migrations..."
bash scripts/db-migrate.sh

echo "▸ 3/5  Installing Python scrapers (uv)..."
cd apps/scrapers
if ! command -v uv >/dev/null; then
  echo "uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
fi
uv sync
uv run playwright install chromium

echo "▸ 4/5  Bootstrap OCDS 2024-2026..."
uv run contralatam bootstrap-ocds --years 2024 2025 2026

echo "▸ 5/5  Bootstrap SUNAT padrón..."
uv run contralatam bootstrap-sunat

echo "✅ Bootstrap complete. Next: implement scoring (Fase 2)."
