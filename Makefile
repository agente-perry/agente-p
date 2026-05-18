.PHONY: help db-up db-down db-reset db-migrate db-types scrape-bootstrap scrape-score web-dev web-build doc-intel-install doc-intel-test doc-intel-lint doc-intel-typecheck doc-intel-check clean

help:
	@echo ""
	@echo "Contralatam Agent — comandos"
	@echo ""
	@echo "  make db-up              → Postgres + pgvector local (docker)"
	@echo "  make db-down            → Apagar Postgres local"
	@echo "  make db-reset           → Drop + recrear schema desde migraciones"
	@echo "  make db-migrate         → Aplicar migraciones a Supabase/Postgres"
	@echo "  make db-types           → Regenerar tipos TS desde Postgres"
	@echo "  make scrape-bootstrap   → OCDS + SUNAT padron (F1)"
	@echo "  make scrape-score       → Recalcular risk scores (F2)"
	@echo "  make web-dev            → Next.js dev en :3000"
	@echo "  make web-build          → Next.js build production"
	@echo "  make doc-intel-install  → Instalar packages/document_intelligence (extras dev)"
	@echo "  make doc-intel-test     → pytest del Document Intelligence Core"
	@echo "  make doc-intel-lint     → ruff del Document Intelligence Core"
	@echo "  make doc-intel-typecheck → pyright del Document Intelligence Core"
	@echo "  make doc-intel-check    → test + lint + typecheck"
	@echo "  make clean              → Limpiar caches"
	@echo ""

db-up:
	docker compose -f infra/docker/docker-compose.yml up -d
	@echo "✅ Postgres + pgvector en localhost:5432"

db-down:
	docker compose -f infra/docker/docker-compose.yml down

db-reset:
	@bash scripts/db-reset.sh

db-migrate:
	@bash scripts/db-migrate.sh

db-types:
	pnpm db:types

scrape-bootstrap:
	cd apps/scrapers && uv run contralatam bootstrap-ocds --years 2024 2025 2026
	cd apps/scrapers && uv run contralatam bootstrap-sunat

scrape-score:
	cd apps/scrapers && uv run contralatam score --years 2024 2025 2026

web-dev:
	pnpm dev

web-build:
	pnpm build

doc-intel-install:
	cd packages/document_intelligence && uv venv --python 3.11 --quiet && uv pip install -e ".[dev]"

doc-intel-test:
	cd packages/document_intelligence && .venv/bin/pytest tests/ -q

doc-intel-lint:
	cd packages/document_intelligence && .venv/bin/ruff check src tests

doc-intel-typecheck:
	cd packages/document_intelligence && .venv/bin/pyright

doc-intel-check: doc-intel-test doc-intel-lint doc-intel-typecheck

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf .turbo apps/web/.next packages/*/dist
