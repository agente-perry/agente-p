#!/usr/bin/env python3
"""Validate SEACE Salud scraping delivery manifests.

The scraper handoff is only useful when each process has structured metadata,
document inventory, award evidence and OCR status. This script validates those
CSV contracts and emits a JSON report for CI or manual review.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import fitz  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional when validating non-PDF fixtures
    fitz = None


PROCESS_COLUMNS = {
    "process_id",
    "ocid",
    "seace_code",
    "sector",
    "entity_name",
    "entity_ruc",
    "procedure_type",
    "object_description",
    "status",
    "amount_estimated",
    "currency",
    "publication_date",
    "award_date",
    "source_url",
    "scraped_at",
}

DOCUMENT_COLUMNS = {
    "document_id",
    "process_id",
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
}

AWARD_COLUMNS = {
    "award_id",
    "process_id",
    "supplier_name",
    "supplier_ruc",
    "award_amount",
    "award_currency",
    "award_date",
    "award_document_id",
    "award_source_quote",
    "award_source_page",
    "confidence",
}

VALID_DOCUMENT_TYPES = {
    "tdr",
    "bases",
    "bases_integradas",
    "pliego_absolucion",
    "consultas_observaciones",
    "acta",
    "buena_pro",
    "contrato",
    "documento_ganador",
    "otros",
}

VALID_OCR_CLASSES = {"textual", "mixed", "scanned", "corrupt", "unknown"}
VALID_OCR_STATUS = {"not_needed", "needed", "done", "failed", "blocked"}
VALID_PARSE_STATUS = {"pending", "parsed", "failed"}
VALID_CONFIDENCE = {"high", "medium", "low"}
HEX_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


@dataclass
class ValidationReport:
    processes_total: int = 0
    documents_total: int = 0
    awards_total: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ocr: dict[str, int] = field(default_factory=lambda: {key: 0 for key in sorted(VALID_OCR_CLASSES)})

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "processes_total": self.processes_total,
            "documents_total": self.documents_total,
            "awards_total": self.awards_total,
            "errors": self.errors,
            "warnings": self.warnings,
            "ocr": self.ocr,
        }


def validate_delivery(
    base_dir: Path = Path("data/scraped/seace_salud"),
    *,
    check_pdf_open: bool = True,
) -> ValidationReport:
    """Validate scraping delivery CSVs under ``base_dir``."""
    report = ValidationReport()
    processes_path = base_dir / "processes.csv"
    documents_path = base_dir / "documents.csv"
    awards_path = base_dir / "awards.csv"

    processes = _read_csv(processes_path, PROCESS_COLUMNS, report)
    documents = _read_csv(documents_path, DOCUMENT_COLUMNS, report)
    awards = _read_csv(awards_path, AWARD_COLUMNS, report, required=False)

    process_ids = {row.get("process_id", "") for row in processes if row.get("process_id")}
    document_ids = {row.get("document_id", "") for row in documents if row.get("document_id")}

    report.processes_total = len(processes)
    report.documents_total = len(documents)
    report.awards_total = len(awards)

    _validate_processes(processes, report)
    _validate_documents(documents, process_ids, report, check_pdf_open=check_pdf_open)
    _validate_awards(awards, process_ids, document_ids, report)
    return report


def _validate_processes(rows: list[dict[str, str]], report: ValidationReport) -> None:
    seen: set[str] = set()
    for line, row in enumerate(rows, start=2):
        process_id = row.get("process_id", "").strip()
        if not process_id:
            report.errors.append(f"processes.csv:{line}: process_id is required")
            continue
        if process_id in seen:
            report.errors.append(f"processes.csv:{line}: duplicate process_id {process_id}")
        seen.add(process_id)
        for field_name in ("seace_code", "sector", "entity_name", "procedure_type", "object_description", "status", "currency", "source_url", "scraped_at"):
            if not row.get(field_name, "").strip():
                report.errors.append(f"processes.csv:{line}: {field_name} is required")


def _validate_documents(
    rows: list[dict[str, str]],
    process_ids: set[str],
    report: ValidationReport,
    *,
    check_pdf_open: bool,
) -> None:
    seen: set[tuple[str, str, str]] = set()
    for line, row in enumerate(rows, start=2):
        process_id = row.get("process_id", "").strip()
        document_id = row.get("document_id", "").strip()
        document_type = row.get("document_type", "").strip()
        sha256 = row.get("sha256", "").strip()

        if not document_id:
            report.errors.append(f"documents.csv:{line}: document_id is required")
        if process_id not in process_ids:
            report.errors.append(f"documents.csv:{line}: process_id {process_id or '<empty>'} not found in processes.csv")
        if document_type not in VALID_DOCUMENT_TYPES:
            report.errors.append(f"documents.csv:{line}: invalid document_type {document_type!r}")
        if not sha256 or not HEX_SHA256.match(sha256):
            report.errors.append(f"documents.csv:{line}: sha256 must be a 64-char hex digest")

        duplicate_key = (process_id, document_type, sha256)
        if sha256 and duplicate_key in seen:
            report.errors.append(f"documents.csv:{line}: duplicate process_id + document_type + sha256")
        seen.add(duplicate_key)

        file_path = Path(row.get("file_path", ""))
        if not file_path.exists():
            report.errors.append(f"documents.csv:{line}: file_path does not exist: {file_path}")
        else:
            _validate_file_metadata(row, file_path, line, report)
            if check_pdf_open and _looks_like_pdf(row) and fitz is not None:
                _validate_pdf_opens(file_path, line, report)

        pages_total = _int(row.get("pages_total"))
        pages_with_text = _int(row.get("pages_with_text"))
        pages_needing_ocr = _int(row.get("pages_needing_ocr"))
        if pages_total is None or pages_total <= 0:
            report.errors.append(f"documents.csv:{line}: pages_total must be > 0")
        if pages_with_text is None or pages_needing_ocr is None:
            report.errors.append(f"documents.csv:{line}: pages_with_text and pages_needing_ocr must be integers")
        elif pages_total is not None and pages_with_text + pages_needing_ocr > pages_total:
            report.errors.append(f"documents.csv:{line}: pages_with_text + pages_needing_ocr exceeds pages_total")

        ocr_class = row.get("ocr_class", "").strip()
        if ocr_class not in VALID_OCR_CLASSES:
            report.errors.append(f"documents.csv:{line}: invalid ocr_class {ocr_class!r}")
        else:
            report.ocr[ocr_class] += 1
        if row.get("ocr_status", "").strip() not in VALID_OCR_STATUS:
            report.errors.append(f"documents.csv:{line}: invalid ocr_status {row.get('ocr_status')!r}")
        if row.get("parse_status", "").strip() not in VALID_PARSE_STATUS:
            report.errors.append(f"documents.csv:{line}: invalid parse_status {row.get('parse_status')!r}")
        if not row.get("source_url", "").strip():
            report.errors.append(f"documents.csv:{line}: source_url is required")


def _validate_awards(
    rows: list[dict[str, str]],
    process_ids: set[str],
    document_ids: set[str],
    report: ValidationReport,
) -> None:
    for line, row in enumerate(rows, start=2):
        process_id = row.get("process_id", "").strip()
        if process_id not in process_ids:
            report.errors.append(f"awards.csv:{line}: process_id {process_id or '<empty>'} not found in processes.csv")
        supplier_name = row.get("supplier_name", "").strip()
        award_source_quote = row.get("award_source_quote", "").strip()
        award_source_page = row.get("award_source_page", "").strip()
        award_document_id = row.get("award_document_id", "").strip()
        if supplier_name and not award_source_quote:
            report.errors.append(f"awards.csv:{line}: supplier_name requires award_source_quote")
        if award_source_quote and not award_source_page:
            report.errors.append(f"awards.csv:{line}: award_source_quote requires award_source_page")
        if award_document_id and award_document_id not in document_ids:
            report.errors.append(f"awards.csv:{line}: award_document_id {award_document_id} not found in documents.csv")
        if row.get("confidence", "").strip() and row.get("confidence", "").strip() not in VALID_CONFIDENCE:
            report.errors.append(f"awards.csv:{line}: invalid confidence {row.get('confidence')!r}")


def _read_csv(
    path: Path,
    required_columns: set[str],
    report: ValidationReport,
    *,
    required: bool = True,
) -> list[dict[str, str]]:
    if not path.exists():
        if required:
            report.errors.append(f"missing required file: {path}")
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        reader = csv.DictReader(file_obj)
        fieldnames = set(reader.fieldnames or [])
        missing = sorted(required_columns - fieldnames)
        if missing:
            report.errors.append(f"{path.name}: missing columns: {', '.join(missing)}")
        return [{key: value or "" for key, value in row.items()} for row in reader]


def _validate_file_metadata(row: dict[str, str], file_path: Path, line: int, report: ValidationReport) -> None:
    expected_size = _int(row.get("file_size_bytes"))
    actual_size = file_path.stat().st_size
    if expected_size is None or expected_size <= 0:
        report.errors.append(f"documents.csv:{line}: file_size_bytes must be > 0")
    elif expected_size != actual_size:
        report.warnings.append(f"documents.csv:{line}: file_size_bytes {expected_size} != actual {actual_size}")
    expected_sha = row.get("sha256", "").strip().lower()
    if HEX_SHA256.match(expected_sha):
        actual_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
        if actual_sha != expected_sha:
            report.errors.append(f"documents.csv:{line}: sha256 does not match file contents")


def _validate_pdf_opens(file_path: Path, line: int, report: ValidationReport) -> None:
    try:
        with fitz.open(file_path) as document:  # type: ignore[union-attr]
            if len(document) <= 0:
                report.errors.append(f"documents.csv:{line}: PDF has zero pages")
    except Exception as exc:
        report.errors.append(f"documents.csv:{line}: PDF does not open: {exc}")


def _looks_like_pdf(row: dict[str, str]) -> bool:
    mime_type = row.get("mime_type", "").lower()
    file_name = row.get("file_name", "").lower()
    return "pdf" in mime_type or file_name.endswith(".pdf")


def _int(value: str | None) -> int | None:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SEACE Salud scraping delivery CSVs.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON report path.")
    parser.add_argument("--no-pdf-open", action="store_true", help="Skip opening PDFs with PyMuPDF.")
    args = parser.parse_args()

    report = validate_delivery(args.base_dir, check_pdf_open=not args.no_pdf_open)
    payload = report.to_dict()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
