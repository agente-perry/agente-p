#!/usr/bin/env bash
set -euo pipefail

BUCKET="gs://agente-perry-data-prod"
PROJECT="agente-perry"

echo "=== AgentPerry Data Uploader ==="
echo "Project: ${PROJECT}"
echo "Bucket:  ${BUCKET}"
echo ""

usage() {
  echo "Usage: $0 [--dry-run] [--reset] [--source ocds|sunat|tdrs|all]"
  echo ""
  echo "Options:"
  echo "  --dry-run    Show what would be uploaded without uploading"
  echo "  --reset      Force overwrite existing files"
  echo "  --source     Upload only specific source directory (default: all)"
  echo ""
  echo "Examples:"
  echo "  $0                           # Full sync (recommended)"
  echo "  $0 --source ocds             # Sync only OCDS data"
  echo "  $0 --dry-run                 # Preview changes"
  echo "  $0 --source tdrs --reset     # Force re-upload TDRs"
  echo ""
  echo "Sources available:"
  echo "  ocds, filtered, tdrs, manual_tdrs, tdr_recon, collectors, results, golden_set"
}

DRY_RUN=""
RESET=""
SOURCE=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    --reset) RESET="-d"; shift ;;
    --source) SOURCE="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# Ensure gcloud is authenticated
if ! gcloud config get-value project 2>/dev/null | grep -q "${PROJECT}"; then
  echo "Error: gcloud project is not set to '${PROJECT}'."
  echo "Run: gcloud config set project ${PROJECT}"
  exit 1
fi

sync_dir() {
  local src=$1
  local dst=$2
  local label=$3

  if [[ ! -d "$src" ]]; then
    echo "Skipping $label (not found): $src"
    return
  fi

  echo "Syncing $label..."
  if [[ -n "$DRY_RUN" ]]; then
    echo "  [DRY RUN] gsutil -m rsync -r -c ${RESET} $src $dst"
    gsutil -m rsync -r -c -n "$src" "$dst"
  else
    gsutil -m rsync -r -c ${RESET} "$src" "$dst"
    echo "  Done: $label -> $dst"
  fi
  echo ""
}

# Main sync
if [[ -z "$SOURCE" || "$SOURCE" == "all" ]]; then
  echo "Running FULL sync (all data sources)..."
  echo ""
  sync_dir "data/scraped" "${BUCKET}/scraped" "scraped data"
  sync_dir "data/golden_set" "${BUCKET}/golden_set" "golden set"
elif [[ "$SOURCE" == "ocds" ]]; then
  sync_dir "data/scraped/ocds" "${BUCKET}/scraped/ocds" "OCDS data"
elif [[ "$SOURCE" == "filtered" ]]; then
  sync_dir "data/scraped/filtered" "${BUCKET}/scraped/filtered" "filtered contracts"
elif [[ "$SOURCE" == "tdrs" ]]; then
  sync_dir "data/scraped/tdrs" "${BUCKET}/scraped/tdrs" "TDR PDFs"
elif [[ "$SOURCE" == "manual_tdrs" ]]; then
  sync_dir "data/scraped/manual_tdrs" "${BUCKET}/scraped/manual_tdrs" "manual TDRs"
elif [[ "$SOURCE" == "tdr_recon" ]]; then
  sync_dir "data/scraped/tdr_recon" "${BUCKET}/scraped/tdr_recon" "TDR recon"
elif [[ "$SOURCE" == "collectors" ]]; then
  sync_dir "data/scraped/collectors" "${BUCKET}/scraped/collectors" "collectors"
elif [[ "$SOURCE" == "results" ]]; then
  sync_dir "data/scraped/results" "${BUCKET}/scraped/results" "pipeline results"
elif [[ "$SOURCE" == "golden_set" ]]; then
  sync_dir "data/golden_set" "${BUCKET}/golden_set" "golden set"
else
  echo "Unknown source: $SOURCE"
  usage
  exit 1
fi

echo "=== Upload summary ==="
echo "Project: ${PROJECT}"
echo "Bucket:  ${BUCKET}"
if [[ -n "$DRY_RUN" ]]; then
  echo "Mode:    DRY RUN (no changes made)"
fi
echo ""
echo "Team download command:"
echo "  gsutil -m cp -r ${BUCKET}/scraped ./data/"
echo "  gsutil -m cp -r ${BUCKET}/golden_set ./data/"
echo ""
echo "Done."
