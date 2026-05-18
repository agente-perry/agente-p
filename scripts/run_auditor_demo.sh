#!/usr/bin/env bash
# Interactive AuditorGraph (LangGraph) demo wrapper.
#
# Usage:
#   bash scripts/run_auditor_demo.sh                            # single PDF (default)
#   bash scripts/run_auditor_demo.sh tdr_salud_pliego_001       # specific PDF
#   bash scripts/run_auditor_demo.sh --all                      # all 4 golden-set PDFs
#
# Uses the apps/scrapers .venv (which has langgraph + document_intelligence
# installed). Prints colored output to TTY; set NO_COLOR=1 to disable.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PY="$REPO_ROOT/apps/scrapers/.venv/bin/python"

if [[ ! -x "$VENV_PY" ]]; then
  echo "error: virtualenv not found at $VENV_PY" >&2
  echo "create it with: cd apps/scrapers && uv venv && uv pip install -e ." >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  exec "$VENV_PY" "$REPO_ROOT/scripts/run_auditor_demo.py"
elif [[ "$1" == "--all" ]]; then
  exec "$VENV_PY" "$REPO_ROOT/scripts/run_auditor_demo.py" --all
else
  exec "$VENV_PY" "$REPO_ROOT/scripts/run_auditor_demo.py" --pdf "$1"
fi
