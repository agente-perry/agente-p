#!/usr/bin/env bash
# Read-only fixture-origin audit for AgentePerry code and local data paths.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "============================================================"
echo "AUDITORIA DE ORIGEN FIXTURE (READ-ONLY)"
echo "============================================================"
echo "Repo: $ROOT_DIR"

echo ""
echo "## Referencias a tests/fixtures en codigo"
grep -RInE 'tests/fixtures|fixtures/|sample|/tmp/|_test_|dummy' \
  "$ROOT_DIR/apps/scrapers/src" \
  "$ROOT_DIR/apps/scrapers/tests" \
  "$ROOT_DIR/scripts" 2>/dev/null \
  | head -200 || true

echo ""
echo "## Referencias a raw_path"
grep -RInE 'raw_path|metadata.*raw_path' \
  "$ROOT_DIR/apps/scrapers/src" \
  "$ROOT_DIR/scripts" 2>/dev/null \
  | head -200 || true

echo ""
echo "## Loaders y comandos que aceptan paths locales"
grep -RInE 'argument\(|option\(|Path\(|input_path|manifest|jsonl|csv|load|upsert|pipeline' \
  "$ROOT_DIR/apps/scrapers/src/agenteperry" \
  "$ROOT_DIR/scripts" 2>/dev/null \
  | grep -E 'loader|sync|cli|collector|ingestion|audit|phase1' \
  | head -250 || true

echo ""
echo "## Fixtures SUNAT/padron existentes"
find "$ROOT_DIR/apps/scrapers/tests/fixtures" -type f 2>/dev/null \
  | grep -E -i 'sunat|padron|ruc|company|empresa' \
  | sort || true

echo ""
echo "## Guard anti-fixture detectado"
grep -RInE 'allow_fixture|production_guard|assert_production|FORBIDDEN_PATH|fixtures' \
  "$ROOT_DIR/apps/scrapers/src/agenteperry" \
  "$ROOT_DIR/scripts" 2>/dev/null \
  | head -200 || true
