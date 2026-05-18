#!/usr/bin/env python3
"""Build process_document_packs.jsonl from SEACE Salud delivery CSVs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


PROCESS_FIELDS = [
    "process_id",
    "ocid",
    "sector",
    "entity_name",
    "entity_ruc",
    "seace_code",
    "procedure_type",
    "object_description",
    "status",
    "source_url",
    "scraped_at",
]

OPTIONAL_PROCESS_FIELDS = [
    "amount_estimated",
    "currency",
    "publication_date",
    "award_date",
]

DOCUMENT_FIELDS = [
    "document_id",
    "document_type",
    "file_name",
    "file_path",
    "file_url",
    "source_url",
    "mime_type",
    "file_size_bytes",
    "sha256",
    "pages_total",
    "pages_with_text",
    "pages_needing_ocr",
    "text_coverage_ratio",
    "ocr_class",
    "ocr_required",
    "ocr_status",
    "downloaded_at",
    "parse_status",
    "error_message",
]

AWARD_FIELDS = [
    "award_id",
    "supplier_name",
    "supplier_ruc",
    "award_amount",
    "award_currency",
    "award_date",
    "award_document_id",
    "award_source_quote",
    "award_source_page",
    "confidence",
]


def build_process_document_packs(
    base_dir: Path = Path("data/scraped/seace_salud"),
    output_path: Path | None = None,
) -> Path:
    """Build one JSONL line per process with nested documents and award."""
    processes = _read_csv(base_dir / "processes.csv")
    documents = _read_csv(base_dir / "documents.csv")
    awards = _read_csv(base_dir / "awards.csv", required=False)
    output_path = output_path or base_dir / "manifests" / "process_document_packs.jsonl"

    documents_by_process: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for document in documents:
        process_id = document.get("process_id", "")
        documents_by_process[process_id].append(_clean_document(document))

    awards_by_process: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for award in awards:
        process_id = award.get("process_id", "")
        awards_by_process[process_id].append(_clean_award(award))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as file_obj:
        for process in processes:
            process_id = process.get("process_id", "")
            pack = _clean_process(process)
            pack["documents"] = documents_by_process.get(process_id, [])
            awards_for_process = awards_by_process.get(process_id, [])
            pack["award"] = awards_for_process[0] if awards_for_process else None
            file_obj.write(json.dumps(pack, ensure_ascii=False, default=str) + "\n")
    return output_path


def _clean_process(row: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {field: _empty_to_none(row.get(field, "")) for field in PROCESS_FIELDS}
    payload["procedure_code"] = payload.pop("seace_code")
    for field in OPTIONAL_PROCESS_FIELDS:
        payload[field] = _coerce_value(row.get(field, ""))
    return payload


def _clean_document(row: dict[str, str]) -> dict[str, Any]:
    payload: dict[str, Any] = {field: _coerce_value(row.get(field, "")) for field in DOCUMENT_FIELDS}
    return payload


def _clean_award(row: dict[str, str]) -> dict[str, Any]:
    payload = {field: _empty_to_none(row.get(field, "")) for field in AWARD_FIELDS}
    payload["award_amount"] = _coerce_value(row.get("award_amount", ""))
    payload["award_source_page"] = _coerce_value(row.get("award_source_page", ""))
    return payload


def _read_csv(path: Path, *, required: bool = True) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        return [{key: value or "" for key, value in row.items()} for row in csv.DictReader(file_obj)]


def _coerce_value(value: str) -> Any:
    cleaned = value.strip()
    if cleaned == "":
        return None
    if cleaned.lower() in {"true", "false"}:
        return cleaned.lower() == "true"
    if cleaned.isdigit():
        return int(cleaned)
    try:
        return float(cleaned)
    except ValueError:
        return cleaned


def _empty_to_none(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build process_document_packs.jsonl.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    output = build_process_document_packs(args.base_dir, args.out)
    print(json.dumps({"output_path": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
