# pyright: reportMissingTypeStubs=false
"""Controlled downloader and usability audit for TDR-like documents."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import fitz

from agenteperry.db.client import DbClient

USER_AGENT = "AgentePerry-TDR-Downloader/1.0 (+https://github.com/hacklatam)"
ALLOWED_EXTENSIONS = {"pdf", "rar", "zip", "doc", "docx"}
ARCHIVE_EXTENSIONS = {"rar", "zip"}

_SCORE_RULES: list[tuple[str, int]] = [
    ("terminos de referencia", 100),
    ("terminos", 95),
    ("tdr", 100),
    ("especificaciones tecnicas", 95),
    ("bases integradas", 85),
    ("bases administrativas", 80),
    ("bases", 75),
    ("requerimiento", 90),
    ("pliego", 50),
]


@dataclass
class DownloadResult:
    status: str
    checksum: str | None
    content_type: str | None
    file_type: str | None
    error: str | None
    output_path: Path | None
    bytes_written: int


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_value.lower().strip()


def score_document_title(title: str) -> int:
    text = normalize_text(title)
    score = 0
    for keyword, points in _SCORE_RULES:
        if keyword in text:
            score = max(score, points)
    return score


def select_tdr_documents(documents: list[dict[str, Any]], pdf_only: bool = False) -> list[dict[str, Any]]:
    """Select and prioritize relevant TDR/Bases documents by title."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for document in documents:
        title = str(document.get("title") or "")
        url = str(document.get("url") or "")
        declared_format = str(document.get("format") or "").lower().strip().lstrip(".")
        if pdf_only and declared_format != "pdf":
            continue
        if declared_format and declared_format not in ALLOWED_EXTENSIONS:
            continue
        if not title or not url:
            continue
        score = score_document_title(title)
        if score <= 0:
            continue
        scored.append((score, document))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [doc for _, doc in scored]


def safe_filename(name: str, fallback: str = "documento") -> str:
    text = normalize_text(name)
    safe = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return safe or fallback


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def infer_file_type(content_type: str | None, url: str, declared_format: str | None = None) -> str | None:
    if declared_format:
        declared_ext = str(declared_format).lower().strip().lstrip(".")
        if declared_ext in ALLOWED_EXTENSIONS:
            return declared_ext

    candidates: list[str] = []
    if content_type:
        candidates.append(content_type.split(";")[0].strip().lower())
    if declared_format:
        candidates.append(str(declared_format).split(";")[0].strip().lower())

    for candidate in candidates:
        guessed = mimetypes.guess_extension(candidate)
        if guessed:
            ext = guessed.lstrip(".").lower()
            if ext == "x-rar-compressed":
                ext = "rar"
            if ext in ALLOWED_EXTENSIONS:
                return ext

    parsed = urlparse(url)
    suffix = Path(parsed.path).suffix.lstrip(".").lower()
    if suffix in ALLOWED_EXTENSIONS:
        return suffix
    return None


def _download_once(url: str, timeout: int) -> tuple[bytes, str | None]:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:  # noqa: S310 - controlled URL from OCDS dataset
        content = response.read()
        content_type = response.headers.get("Content-Type")
        return content, content_type


def download_document(
    url: str,
    output_path: Path,
    timeout: int = 30,
    retries: int = 3,
    declared_format: str | None = None,
) -> DownloadResult:
    """Download one document with retries, timeout, backoff and checksum."""
    last_error: str | None = None
    for attempt in range(1, retries + 1):
        try:
            content, content_type = _download_once(url, timeout=timeout)
            file_type = infer_file_type(content_type, url, declared_format=declared_format)
            if file_type is None:
                return DownloadResult(
                    status="unsupported_format",
                    checksum=None,
                    content_type=content_type,
                    file_type=None,
                    error="Unsupported content type",
                    output_path=None,
                    bytes_written=0,
                )

            final_path = output_path
            if final_path.suffix.lstrip(".").lower() != file_type:
                final_path = output_path.with_suffix(f".{file_type}")
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_bytes(content)

            return DownloadResult(
                status="downloaded",
                checksum=compute_sha256(content),
                content_type=content_type,
                file_type=file_type,
                error=None,
                output_path=final_path,
                bytes_written=len(content),
            )
        except HTTPError as exc:
            if exc.code == 404:
                return DownloadResult(
                    status="not_found",
                    checksum=None,
                    content_type=None,
                    file_type=None,
                    error=f"HTTP 404: {url}",
                    output_path=None,
                    bytes_written=0,
                )
            last_error = f"HTTP {exc.code}: {exc.reason}"
        except URLError as exc:
            last_error = f"URL error: {exc.reason}"
        except TimeoutError:
            last_error = "Timeout"
        except Exception as exc:  # pragma: no cover - defensive path
            last_error = str(exc)

        if attempt < retries:
            time.sleep(attempt * attempt)

    return DownloadResult(
        status="failed",
        checksum=None,
        content_type=None,
        file_type=None,
        error=last_error,
        output_path=None,
        bytes_written=0,
    )


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _extract_documents_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    direct = record.get("documents")
    if isinstance(direct, list):
        direct_items = cast(list[Any], direct)
        out: list[dict[str, Any]] = []
        for item in direct_items:
            if isinstance(item, dict):
                out.append(cast(dict[str, Any], item))
        return out
    raw_data = record.get("raw_data")
    if isinstance(raw_data, dict):
        raw_data_map = cast(dict[str, Any], raw_data)
        tender = raw_data_map.get("tender")
        if isinstance(tender, dict):
            tender_map = cast(dict[str, Any], tender)
            docs = tender_map.get("documents")
            if isinstance(docs, list):
                doc_items = cast(list[Any], docs)
                out_docs: list[dict[str, Any]] = []
                for item in doc_items:
                    if isinstance(item, dict):
                        out_docs.append(cast(dict[str, Any], item))
                return out_docs
    return []


def _fetch_source_record_with_documents(db: DbClient, record: dict[str, Any]) -> dict[str, Any] | None:
    external_id = str(record.get("external_id") or "").strip()
    ocid = str(record.get("ocid") or "").strip()

    if external_id:
        try:
            exact_rows = db.execute(
                """
                SELECT id, external_id, entity_name, monto, fecha, raw_data
                FROM source_records
                WHERE external_id = %s
                  AND record_type = 'contract'
                LIMIT 1
                """,
                (external_id,),
            )
        except Exception:
            return None
        if exact_rows:
            return dict(exact_rows[0])

    if ocid:
        try:
            rows = db.execute(
                """
                SELECT id, external_id, entity_name, monto, fecha, raw_data
                FROM source_records
                WHERE record_type = 'contract'
                  AND (
                    external_id = %s
                    OR external_id LIKE %s
                    OR raw_data->>'ocid' = %s
                  )
                ORDER BY monto DESC NULLS LAST
                LIMIT 1
                """,
                (ocid, f"{ocid}:%", ocid),
            )
        except Exception:
            return None
        if rows:
            return dict(rows[0])
    return None


def _build_doc_external_id(ocid: str, document: dict[str, Any], checksum: str | None, url: str) -> str:
    doc_id = str(document.get("id") or "").strip()
    if doc_id:
        return f"{ocid}::{doc_id}"
    if checksum:
        return f"{ocid}::{checksum[:16]}"
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"{ocid}::{url_hash}"


def _write_audit(output_dir: Path, audit: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_path = output_dir / "audit.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return audit_path


def _upsert_tdr_document(db: DbClient, row: dict[str, Any]) -> None:
    query = """
        INSERT INTO tdr_documents (
            external_id, title, entity_name, procedure_code, source_url, file_url,
            sector, publication_date, estimated_value, storage_path, checksum, parse_status
        ) VALUES (
            %(external_id)s, %(title)s, %(entity_name)s, %(procedure_code)s, %(source_url)s, %(file_url)s,
            %(sector)s, %(publication_date)s, %(estimated_value)s, %(storage_path)s, %(checksum)s, %(parse_status)s
        )
        ON CONFLICT (external_id) DO UPDATE SET
            title = EXCLUDED.title,
            entity_name = EXCLUDED.entity_name,
            procedure_code = EXCLUDED.procedure_code,
            source_url = EXCLUDED.source_url,
            file_url = EXCLUDED.file_url,
            sector = EXCLUDED.sector,
            publication_date = EXCLUDED.publication_date,
            estimated_value = EXCLUDED.estimated_value,
            storage_path = EXCLUDED.storage_path,
            checksum = EXCLUDED.checksum,
            parse_status = EXCLUDED.parse_status,
            updated_at = now()
    """
    try:
        db.execute(query, row)
    except Exception:
        return


def download_tdr_batch(
    input_jsonl: Path,
    sector: str,
    limit: int = 5,
    max_docs_per_contract: int = 1,
    timeout: int = 30,
    retries: int = 3,
    dry_run: bool = False,
    pdf_only: bool = False,
    skip_existing: bool = False,
    audit_after_download: bool = False,
    stop_when_usable: int = 0,
    download_root: Path | None = None,
) -> dict[str, Any]:
    """Download a controlled batch of TDR-like documents from filtered JSONL."""
    records: list[dict[str, Any]] = []
    for line in input_jsonl.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        loaded = json.loads(stripped)
        if isinstance(loaded, dict):
            records.append(cast(dict[str, Any], loaded))

    db = DbClient()
    repo_root = Path(__file__).resolve().parents[5]
    tdr_root = download_root or repo_root / "data" / "tdrs"
    output_dir = tdr_root / sector
    output_dir.mkdir(parents=True, exist_ok=True)

    contracts_seen = 0
    doc_candidates = 0
    doc_selected = 0
    downloaded = 0
    failed = 0
    unsupported = 0
    skipped_no_docs = 0
    processed_docs = 0
    total_candidates_considered = 0
    attempted_downloads = 0
    skipped_existing = 0
    usable_found = 0
    first_usable_path: str | None = None
    needs_ocr_count = 0
    failed_count = 0
    stopped_early = False
    results: list[dict[str, Any]] = []

    for record in records:
        if stopped_early:
            break
        contracts_seen += 1

        resolved = record
        documents = _extract_documents_from_record(resolved)
        if not documents:
            fetched = _fetch_source_record_with_documents(db, record)
            if fetched:
                resolved = {**record, **fetched}
                documents = _extract_documents_from_record(fetched)

        if not documents:
            skipped_no_docs += 1
            continue

        doc_candidates += len(documents)
        selected = select_tdr_documents(documents, pdf_only=pdf_only)
        if not selected:
            skipped_no_docs += 1
            continue

        selected = selected[:max_docs_per_contract]

        ocid = str(resolved.get("ocid") or resolved.get("external_id") or "sin_ocid")
        entity_name = str(resolved.get("entity") or resolved.get("entity_name") or "")
        procedure_code: str | None = None
        raw_data = resolved.get("raw_data")
        if isinstance(raw_data, dict):
            raw_data_map = cast(dict[str, Any], raw_data)
            tender = raw_data_map.get("tender")
            if isinstance(tender, dict):
                tender_map = cast(dict[str, Any], tender)
                tender_id = tender_map.get("id")
                if isinstance(tender_id, str):
                    procedure_code = tender_id
                elif isinstance(tender_id, (int, float)):
                    procedure_code = str(tender_id)

        for index, document in enumerate(selected):
            if total_candidates_considered >= limit:
                stopped_early = stop_when_usable > 0 and usable_found >= stop_when_usable
                break

            title = str(document.get("title") or f"documento_{index + 1}")
            url = str(document.get("url") or "")
            if not url:
                continue

            parsed_url = urlparse(url)
            file_code = parse_qs(parsed_url.query).get("fileCode", [""])[0]
            basename = safe_filename(title)
            if file_code:
                basename = f"{basename}_{safe_filename(file_code)}"
            output_path = output_dir / safe_filename(ocid) / basename
            declared_format = str(document.get("format") or "") or None
            final_output_path = output_path.with_suffix(f".{declared_format}") if declared_format else output_path

            total_candidates_considered += 1

            if skip_existing and final_output_path.exists():
                skipped_existing += 1
                skipped_path = str(final_output_path)
                try:
                    skipped_path = str(final_output_path.relative_to(repo_root))
                except ValueError:
                    skipped_path = str(final_output_path)
                results.append(
                    {
                        "ocid": ocid,
                        "external_id": _build_doc_external_id(ocid, document, None, url),
                        "title": title,
                        "url": url,
                        "status": "skipped_existing",
                        "file_type": declared_format,
                        "checksum": None,
                        "storage_path": skipped_path,
                        "error": None,
                    }
                )
                continue

            doc_selected += 1

            if dry_run:
                status = "skipped"
                result = DownloadResult(
                    status=status,
                    checksum=None,
                    content_type=None,
                    file_type=None,
                    error="dry_run",
                    output_path=output_path,
                    bytes_written=0,
                )
            else:
                attempted_downloads += 1
                result = download_document(
                    url=url,
                    output_path=output_path,
                    timeout=timeout,
                    retries=retries,
                    declared_format=declared_format,
                )

            if not dry_run:
                time.sleep(1)

            processed_docs += 1
            if result.status == "downloaded":
                downloaded += 1
            elif result.status == "unsupported_format":
                unsupported += 1
            elif result.status in {"failed", "not_found"}:
                failed += 1
                failed_count += 1

            text_layer: dict[str, Any] | None = None
            if result.status == "downloaded" and result.output_path and result.file_type == "pdf":
                text_layer = inspect_pdf_text_layer(result.output_path)
                if text_layer["tdr_status"] == "needs_ocr":
                    needs_ocr_count += 1
                if text_layer["is_usable"]:
                    usable_found += 1
                    if first_usable_path is None:
                        first_usable_path = str(result.output_path)

            external_id = _build_doc_external_id(ocid, document, result.checksum, url)
            storage_path = str(result.output_path) if result.output_path else None
            if result.output_path:
                try:
                    storage_path = str(result.output_path.relative_to(repo_root))
                except ValueError:
                    storage_path = str(result.output_path)
            parse_status = "pending" if result.status == "downloaded" else "failed"

            _upsert_tdr_document(
                db,
                {
                    "external_id": external_id,
                    "title": title,
                    "entity_name": entity_name,
                    "procedure_code": procedure_code,
                    "source_url": url,
                    "file_url": url,
                    "sector": sector,
                    "publication_date": _coerce_date(resolved.get("fecha")),
                    "estimated_value": resolved.get("monto"),
                    "storage_path": storage_path,
                    "checksum": result.checksum,
                    "parse_status": parse_status,
                },
            )

            results.append(
                {
                    "ocid": ocid,
                    "external_id": external_id,
                    "title": title,
                    "url": url,
                    "status": result.status,
                    "file_type": result.file_type,
                    "checksum": result.checksum,
                    "storage_path": storage_path,
                    "error": result.error,
                    "text_layer": text_layer,
                }
            )

            if stop_when_usable > 0 and usable_found >= stop_when_usable:
                stopped_early = True
                break

        if total_candidates_considered >= limit:
            break

    avg_docs = (processed_docs / contracts_seen) if contracts_seen else 0.0
    audit = {
        "sector": sector,
        "total_contracts_seen": contracts_seen,
        "documents_candidates": doc_candidates,
        "documents_selected": doc_selected,
        "downloaded": downloaded,
        "failed": failed,
        "unsupported_format": unsupported,
        "skipped_no_documents": skipped_no_docs,
        "avg_docs_per_contract": round(avg_docs, 2),
        "output_dir": str(output_dir),
        "run_at": datetime.now(UTC).isoformat(),
        "total_candidates_considered": total_candidates_considered,
        "attempted_downloads": attempted_downloads,
        "usable_found": usable_found,
        "first_usable_path": first_usable_path,
        "needs_ocr_count": needs_ocr_count,
        "failed_count": failed_count,
        "skipped_existing": skipped_existing,
        "stopped_early": stopped_early,
    }
    audit_path = _write_audit(output_dir, audit)
    pdf_audit = audit_pdf_usability(tdr_root) if audit_after_download else None

    return {
        "audit": audit,
        "audit_path": str(audit_path),
        "pdf_audit": pdf_audit,
        "results": results,
    }


def inspect_pdf_text_layer(
    pdf_path: Path,
    min_chars_per_page: int = 50,
    usable_threshold: float = 0.20,
    partial_threshold: float = 0.05,
) -> dict[str, Any]:
    """Inspect whether a PDF has enough digital text to enter the TDR parser."""
    if pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected PDF path, got: {pdf_path}")

    pages_with_text = 0
    try:
        with fitz.open(pdf_path) as document:
            pdf_document: Any = document
            total_pages = len(pdf_document)
            for page_index in range(total_pages):
                page: Any = pdf_document.load_page(page_index)
                text = str(page.get_text("text") or "").strip()
                if len(text) >= min_chars_per_page:
                    pages_with_text += 1
    except Exception as exc:
        return {
            "path": str(pdf_path),
            "total_pages": 0,
            "pages_with_text": 0,
            "pages_needs_ocr": 0,
            "coverage_pct": 0.0,
            "tdr_status": "needs_ocr",
            "is_usable": False,
            "error": str(exc),
        }

    coverage = (pages_with_text / total_pages) if total_pages else 0.0
    if coverage >= usable_threshold:
        status = "available"
    elif coverage >= partial_threshold:
        status = "partial"
    else:
        status = "needs_ocr"

    return {
        "path": str(pdf_path),
        "total_pages": total_pages,
        "pages_with_text": pages_with_text,
        "pages_needs_ocr": max(total_pages - pages_with_text, 0),
        "coverage_pct": round(coverage * 100, 2),
        "tdr_status": status,
        "is_usable": status == "available",
    }


def audit_pdf_usability(base_dir: Path) -> dict[str, Any]:
    """Audit downloaded PDFs and archives under data/scraped/tdrs."""
    base_dir = base_dir.resolve()
    report_path = base_dir / "pdf_usability_report.csv"
    audit_path = base_dir / "pdf_usability_audit.json"
    rows: list[dict[str, Any]] = []
    pdf_rows: list[dict[str, Any]] = []
    archives_pending = 0
    total_files = 0

    for path in sorted(base_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in {"audit.json", "pdf_usability_report.csv", "pdf_usability_audit.json"}:
            continue
        total_files += 1
        extension = path.suffix.lower().lstrip(".")
        sector = _sector_from_path(base_dir, path)

        if extension == "pdf":
            result = inspect_pdf_text_layer(path)
            row = {
                "path": str(path),
                "sector": sector,
                "extension": extension,
                "total_pages": result["total_pages"],
                "pages_with_text": result["pages_with_text"],
                "pages_needs_ocr": result["pages_needs_ocr"],
                "coverage_pct": result["coverage_pct"],
                "tdr_status": result["tdr_status"],
                "is_usable": result["is_usable"],
                "notes": result.get("error", ""),
            }
            rows.append(row)
            pdf_rows.append(row)
        elif extension in ARCHIVE_EXTENSIONS:
            archives_pending += 1
            rows.append(
                {
                    "path": str(path),
                    "sector": sector,
                    "extension": extension,
                    "total_pages": 0,
                    "pages_with_text": 0,
                    "pages_needs_ocr": 0,
                    "coverage_pct": 0.0,
                    "tdr_status": "archive_pending",
                    "is_usable": False,
                    "notes": "Archive pending extraction; not inspected in Activity 4.2",
                }
            )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "sector",
        "extension",
        "total_pages",
        "pages_with_text",
        "pages_needs_ocr",
        "coverage_pct",
        "tdr_status",
        "is_usable",
        "notes",
    ]
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    pdf_available = [row for row in pdf_rows if row["tdr_status"] == "available"]
    pdf_partial = [row for row in pdf_rows if row["tdr_status"] == "partial"]
    pdf_needs_ocr = [row for row in pdf_rows if row["tdr_status"] == "needs_ocr"]
    recommended = _recommend_golden_set(pdf_available)
    audit = {
        "total_files": total_files,
        "pdf_files": len(pdf_rows),
        "pdf_available": len(pdf_available),
        "pdf_partial": len(pdf_partial),
        "pdf_needs_ocr": len(pdf_needs_ocr),
        "archives_pending": archives_pending,
        "usable_pdfs": [row["path"] for row in pdf_available],
        "needs_ocr_pdfs": [row["path"] for row in pdf_needs_ocr],
        "recommended_for_golden_set": recommended,
        "report_path": str(report_path),
        "audit_path": str(audit_path),
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return audit


def _sector_from_path(base_dir: Path, path: Path) -> str:
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        return "unknown"
    return relative.parts[0] if relative.parts else "unknown"


def _recommend_golden_set(pdf_available: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sector: dict[str, list[dict[str, Any]]] = {}
    for row in pdf_available:
        sector = str(row.get("sector") or "unknown")
        by_sector.setdefault(sector, []).append(row)

    recommendations: list[dict[str, Any]] = []
    for sector in sorted(by_sector):
        candidates = sorted(
            by_sector[sector],
            key=lambda row: (float(row["coverage_pct"]), int(row["pages_with_text"])),
            reverse=True,
        )
        if candidates:
            best = candidates[0]
            recommendations.append(
                {
                    "sector": sector,
                    "path": best["path"],
                    "coverage_pct": best["coverage_pct"],
                    "pages_with_text": best["pages_with_text"],
                }
            )
    return recommendations
