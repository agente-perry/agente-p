#!/usr/bin/env bash
# Read-only PDF inventory for AgentePerry data/.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-$ROOT_DIR/data}"

echo "============================================================"
echo "AUDITORIA DE PDFs EN DISCO (READ-ONLY)"
echo "============================================================"
echo "Data dir: $DATA_DIR"

if [[ ! -d "$DATA_DIR" ]]; then
  echo "ERROR: data dir does not exist: $DATA_DIR"
  exit 1
fi

echo ""
echo "## Total de PDFs"
find "$DATA_DIR" -type f -iname "*.pdf" 2>/dev/null | wc -l

echo ""
echo "## PDFs por directorio"
find "$DATA_DIR" -type f -iname "*.pdf" 2>/dev/null \
  | xargs -r -n 1 dirname \
  | sort \
  | uniq -c \
  | sort -rn \
  | head -50

echo ""
echo "## Tamano total de data/"
du -sh "$DATA_DIR" 2>/dev/null || true

echo ""
echo "## Top PDFs mas grandes"
find "$DATA_DIR" -type f -iname "*.pdf" -exec du -h {} + 2>/dev/null \
  | sort -rh \
  | head -20

echo ""
echo "## PDFs con OCID identificable en path"
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "  python/python3 not found; skipping OCID path detection"
else
"$PYTHON_BIN" - "$DATA_DIR" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

data_dir = Path(sys.argv[1])
pattern = re.compile(r"ocds[-_][a-z0-9]+[-_][a-z0-9]+[-_][a-z0-9_\-]+", re.IGNORECASE)
total = 0
matched = 0
examples: list[str] = []

for pdf in sorted(data_dir.rglob("*.pdf")):
    total += 1
    if pattern.search(str(pdf)):
        matched += 1
        if len(examples) < 10:
            examples.append(str(pdf))

print(f"  total_pdfs: {total}")
print(f"  with_ocid_in_path: {matched}")
print(f"  without_ocid_in_path: {total - matched}")
if examples:
    print("  examples:")
    for example in examples:
        print(f"    {example}")
PY
fi

echo ""
echo "## Paths sospechosos (tests/fixtures/sample/tmp/dummy)"
find "$DATA_DIR" -type f -iname "*.pdf" 2>/dev/null \
  | grep -E -i 'tests/|fixtures/|sample|/tmp/|_test_|dummy' \
  | head -50 || true
