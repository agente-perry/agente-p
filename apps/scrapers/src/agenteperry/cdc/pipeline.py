# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""CDC Pipeline: detect changes → download TDR → verify text → generate dossier.

Wires together:
- SEACEChangeDetector   (hash-based change detection)
- select_tdr_documents  (pick best document URL from OCDS tender.documents[])
- download_document     (HTTP download with retry and checksum)
- inspect_pdf_text_layer (verify digital text coverage)
- extract_pdf_pages + chunk_pages + detect_flags_in_pages (parse pipeline)
- generate_dossier + render_dossier_markdown (output)

No database connection required.
No SEACE HTML scraping.
No Playwright.
OCR fallback optional (disabled by default).
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteperry.cdc.detector import ChangeEvent, SEACEChangeDetector
from agenteperry.graph.neo4j_enrichment import (
    enrich_dossier_with_graph,
    render_graph_findings_markdown,
)
from agenteperry.ocr.models import OcrDocumentStatus
from agenteperry.ocr.processor import OcrProcessor
from agenteperry.tdr.chunking import chunk_pages
from agenteperry.tdr.dossier import generate_dossier, render_dossier_markdown
from agenteperry.tdr.downloader import (
    DownloadResult,
    download_document,
    inspect_pdf_text_layer,
    safe_filename,
    select_tdr_documents,
)
from agenteperry.tdr.flags import detect_flags_in_pages
from agenteperry.tdr.models import TdrPage
from agenteperry.tdr.parsing import extract_pdf_pages

# ---------------------------------------------------------------------------
# Result codes
# ---------------------------------------------------------------------------

STATUS_DOSSIER_GENERATED = "dossier_generated"
STATUS_NO_FLAGS = "no_flags_detected"
STATUS_NO_TDR = "no_tdr_url"
STATUS_NOT_PDF = "not_pdf_archive_pending"
STATUS_NEEDS_OCR = "needs_ocr"
STATUS_DOWNLOAD_ERROR = "download_error"
STATUS_DRY_RUN = "dry_run"

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@dataclass
class CDCStats:
    """Counters for one CDC pipeline run."""

    run_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    total_evaluated: int = 0
    new_contracts: int = 0
    modified_contracts: int = 0
    priority_contracts: int = 0
    skipped_sector: int = 0
    skipped_no_change: int = 0

    # TDR resolution
    tdrs_url_found: int = 0
    tdrs_url_not_found: int = 0
    tdrs_downloaded: int = 0
    tdrs_download_failed: int = 0
    tdrs_not_pdf: int = 0

    # Text verification
    tdrs_available: int = 0   # has digital text layer
    tdrs_needs_ocr: int = 0
    tdrs_processed_with_ocr: int = 0

    # Dossier outputs
    dossiers_generated: int = 0
    dossiers_with_flags: int = 0
    dossiers_no_flags: int = 0
    dossiers_graph_enriched: int = 0  # dossiers enriched with Neo4j graph findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_at": self.run_at,
            "total_evaluated": self.total_evaluated,
            "new_contracts": self.new_contracts,
            "modified_contracts": self.modified_contracts,
            "priority_contracts": self.priority_contracts,
            "skipped_sector": self.skipped_sector,
            "skipped_no_change": self.skipped_no_change,
            "tdrs_url_found": self.tdrs_url_found,
            "tdrs_url_not_found": self.tdrs_url_not_found,
            "tdrs_downloaded": self.tdrs_downloaded,
            "tdrs_download_failed": self.tdrs_download_failed,
            "tdrs_not_pdf": self.tdrs_not_pdf,
            "tdrs_available": self.tdrs_available,
            "tdrs_needs_ocr": self.tdrs_needs_ocr,
            "tdrs_processed_with_ocr": self.tdrs_processed_with_ocr,
            "dossiers_generated": self.dossiers_generated,
            "dossiers_with_flags": self.dossiers_with_flags,
            "dossiers_no_flags": self.dossiers_no_flags,
            "dossiers_graph_enriched": self.dossiers_graph_enriched,
        }


# ---------------------------------------------------------------------------
# Per-contract result
# ---------------------------------------------------------------------------

@dataclass
class ContractResult:
    """Result for a single contract processed by CDCPipeline."""

    ocid: str
    change_type: str
    sector: str
    entity_name: str
    monto: float | None
    status: str = ""
    tdr_url: str | None = None
    tdr_path: str | None = None
    pages: int = 0
    coverage_pct: float = 0.0
    chunks: int = 0
    flags: int = 0
    risk_level: str = "SIN_SENALES"
    dossier_path: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_documents(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Extract OCDS tender.documents[] from any record shape."""
    direct = record.get("documents")
    if isinstance(direct, list):
        return [d for d in direct if isinstance(d, dict)]

    raw_data = record.get("raw_data")
    if isinstance(raw_data, dict):
        tender = raw_data.get("tender")
        if isinstance(tender, dict):
            docs = tender.get("documents")
            if isinstance(docs, list):
                return [d for d in docs if isinstance(d, dict)]
    return []


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return cleaned[:60]


def _load_ocr_pages_jsonl(ocr_pages_jsonl: Path, *, tdr_id: str) -> list[Any]:
    pages: list[Any] = []
    lines = ocr_pages_jsonl.read_text(encoding="utf-8").splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        row = json.loads(stripped)
        if not isinstance(row, dict):
            continue
        page_number = int(row.get("page_number") or 0)
        if page_number <= 0:
            continue
        text = str(row.get("text") or "")
        pages.append({"tdr_id": tdr_id, "page_number": page_number, "text_content": text})
    pages.sort(key=lambda item: int(item["page_number"]))
    return pages


def _entity_name(record: Mapping[str, Any]) -> str:
    return str(
        record.get("entity")
        or record.get("entity_name")
        or "Sin dato"
    )


def _monto(record: Mapping[str, Any]) -> float | None:
    raw = record.get("monto") or record.get("amount")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _procedure_code(record: Mapping[str, Any]) -> str | None:
    raw = (
        record.get("objeto")
        or (record.get("parsed_data") or {}).get("procedure_type")
        or ""
    )
    return str(raw) or None


def _supplier_ruc(record: Mapping[str, Any]) -> str | None:
    """Extract 11-digit supplier RUC from the record."""
    ruc = record.get("supplier_ruc") or ""
    digits = "".join(ch for ch in str(ruc) if ch.isdigit())
    return digits if len(digits) == 11 else None


def _buyer_ruc(record: Mapping[str, Any]) -> str | None:
    """Extract 11-digit buyer (entity) RUC from the record."""
    for field_name in ("entity_ruc", "buyer_ruc"):
        ruc = record.get(field_name) or ""
        digits = "".join(ch for ch in str(ruc) if ch.isdigit())
        if len(digits) == 11:
            return digits
    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class CDCPipeline:
    """Change-driven TDR analysis pipeline.

    For every new or modified priority contract:
    1. Find the best TDR/Bases document URL from OCDS tender.documents[]
    2. Download and verify the PDF has a digital text layer
    3. Run the full analysis pipeline (parse → chunk → flags → dossier)
    4. Write dossier.json + dossier.md to output_dir/<ocid_slug>/

    Parameters
    ----------
    sector_filter:
        When set, process only contracts matching this sector
        ("salud" | "ambiente" | "otros").  ``None`` = process all priority.
    limit:
        Maximum number of contracts to *process*
        (after ordering by change detection).
    dry_run:
        If True, detect changes but do not download or analyze anything.
    output_dir:
        Base directory where per-contract result folders are created.
    rate_limit_seconds:
        Pause between HTTP downloads.
    pdf_only:
        If True, skip RAR/ZIP and only download PDF documents.
    max_chars:
        Chunk size for text splitting.
    overlap_chars:
        Overlap between consecutive chunks.
    """

    def __init__(
        self,
        *,
        sector_filter: str | None = None,
        limit: int = 50,
        dry_run: bool = False,
        output_dir: Path = Path("data/results"),
        rate_limit_seconds: float = 1.0,
        pdf_only: bool = True,
        max_chars: int = 1200,
        overlap_chars: int = 160,
        enable_ocr_fallback: bool = False,
        ocr_output_dir: Path = Path("data/ocr"),
        ocr_workers: int = 2,
    ) -> None:
        self.sector_filter = sector_filter
        self.limit = limit
        self.dry_run = dry_run
        self.output_dir = output_dir
        self.rate_limit_seconds = rate_limit_seconds
        self.pdf_only = pdf_only
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars
        self.enable_ocr_fallback = enable_ocr_fallback
        self.ocr_output_dir = ocr_output_dir
        self.ocr_workers = ocr_workers
        self.ocr_processor = OcrProcessor(output_base_dir=ocr_output_dir)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(
        self,
        records: list[Mapping[str, Any]],
        detector: SEACEChangeDetector,
    ) -> tuple[CDCStats, list[ContractResult]]:
        """Run the CDC pipeline over a list of OCDS records.

        Returns (stats, per-contract results).
        Commits the hash registry on success.
        """
        stats = CDCStats(total_evaluated=len(records))
        results: list[ContractResult] = []
        processed = 0

        for change in detector.detect_changes(
            records,
            sector_filter=self.sector_filter,
            priority_only=True,
        ):
            if change.change_type == "new":
                stats.new_contracts += 1
            else:
                stats.modified_contracts += 1

            if not change.is_priority:
                stats.skipped_sector += 1
                continue

            stats.priority_contracts += 1

            if processed >= self.limit:
                break

            result = self._process_change(change, stats)
            results.append(result)
            processed += 1

        # Count skipped (no change)
        stats.skipped_no_change = stats.total_evaluated - stats.new_contracts - stats.modified_contracts

        # Persist hashes — only if not dry_run
        if not self.dry_run:
            detector.commit()

        return stats, results

    # ------------------------------------------------------------------
    # Per-contract processing
    # ------------------------------------------------------------------

    def _process_change(
        self,
        change: ChangeEvent,
        stats: CDCStats,
    ) -> ContractResult:
        record = change.record
        ocid = change.ocid
        entity = _entity_name(record)
        monto = _monto(record)

        base_result = ContractResult(
            ocid=ocid,
            change_type=change.change_type,
            sector=change.sector,
            entity_name=entity,
            monto=monto,
        )

        # ---------------------------------------------------------------
        # Dry-run: just report, do not download
        # ---------------------------------------------------------------
        if self.dry_run:
            documents = _extract_documents(record)
            selected = select_tdr_documents(documents, pdf_only=self.pdf_only)
            dry_url: str | None = str(selected[0].get("url") or "") or None if selected else None

            base_result.status = STATUS_DRY_RUN
            base_result.tdr_url = dry_url
            stats.tdrs_url_found += 1 if dry_url else 0
            stats.tdrs_url_not_found += 0 if dry_url else 1
            return base_result

        # ---------------------------------------------------------------
        # Find best document URL
        # ---------------------------------------------------------------
        documents = _extract_documents(record)
        selected = select_tdr_documents(documents, pdf_only=self.pdf_only)

        if not selected:
            stats.tdrs_url_not_found += 1
            base_result.status = STATUS_NO_TDR
            return base_result

        stats.tdrs_url_found += 1
        doc = selected[0]
        url: str = str(doc.get("url") or "")
        if not url:
            stats.tdrs_url_not_found += 1
            stats.tdrs_url_found -= 1  # undo: URL looked present but was empty
            base_result.status = STATUS_NO_TDR
            return base_result
        declared_format: str | None = str(doc.get("format") or "") or None
        doc_title = str(doc.get("title") or "documento")

        # ---------------------------------------------------------------
        # Build output path + download
        # ---------------------------------------------------------------
        slug = _slugify(ocid)
        sector_dir = self.output_dir / change.sector / slug
        sector_dir.mkdir(parents=True, exist_ok=True)

        filename = safe_filename(doc_title, fallback=slug)
        tentative_path = sector_dir / f"{filename}.pdf"

        result: DownloadResult = download_document(
            url=url,
            output_path=tentative_path,
            timeout=60,
            retries=3,
            declared_format=declared_format,
        )

        time.sleep(self.rate_limit_seconds)

        if result.status != "downloaded" or result.output_path is None:
            stats.tdrs_download_failed += 1
            base_result.status = STATUS_DOWNLOAD_ERROR
            base_result.tdr_url = url
            base_result.error = result.error
            return base_result

        stats.tdrs_downloaded += 1
        tdr_path = result.output_path
        base_result.tdr_url = url

        # ---------------------------------------------------------------
        # Must be a PDF to parse
        # ---------------------------------------------------------------
        if tdr_path.suffix.lower() != ".pdf":
            stats.tdrs_not_pdf += 1
            base_result.status = STATUS_NOT_PDF
            base_result.tdr_path = str(tdr_path)
            return base_result

        # ---------------------------------------------------------------
        # Verify digital text layer
        # ---------------------------------------------------------------
        usability = inspect_pdf_text_layer(tdr_path)

        pages: list[Any]
        total_pages: int
        coverage_pct: float
        if not usability["is_usable"]:
            stats.tdrs_needs_ocr += 1
            if not self.enable_ocr_fallback:
                base_result.status = STATUS_NEEDS_OCR
                base_result.tdr_path = str(tdr_path)
                base_result.pages = usability["total_pages"]
                base_result.coverage_pct = usability["coverage_pct"]
                return base_result

            try:
                ocr_manifest = asyncio.run(
                    self.ocr_processor.process_pdf(
                        pdf_path=tdr_path,
                        ocid=ocid,
                        force=False,
                        dry_run=False,
                        workers=self.ocr_workers,
                    )
                )
            except Exception as exc:
                base_result.status = STATUS_NEEDS_OCR
                base_result.tdr_path = str(tdr_path)
                base_result.pages = usability["total_pages"]
                base_result.coverage_pct = usability["coverage_pct"]
                base_result.error = f"ocr_error:{exc}"
                return base_result

            if ocr_manifest.status == OcrDocumentStatus.FAILED:
                base_result.status = STATUS_NEEDS_OCR
                base_result.tdr_path = str(tdr_path)
                base_result.pages = ocr_manifest.pages_total
                base_result.coverage_pct = ocr_manifest.coverage_after_pct
                base_result.error = "ocr_failed"
                return base_result

            ocr_pages_path = Path(ocr_manifest.output_dir) / "ocr_pages.jsonl"
            if not ocr_pages_path.exists():
                base_result.status = STATUS_NEEDS_OCR
                base_result.tdr_path = str(tdr_path)
                base_result.pages = ocr_manifest.pages_total
                base_result.coverage_pct = ocr_manifest.coverage_after_pct
                base_result.error = "missing_ocr_pages_output"
                return base_result

            pages = _load_ocr_pages_jsonl(ocr_pages_path, tdr_id=ocid)
            if not pages:
                base_result.status = STATUS_NEEDS_OCR
                base_result.tdr_path = str(tdr_path)
                base_result.pages = ocr_manifest.pages_total
                base_result.coverage_pct = ocr_manifest.coverage_after_pct
                base_result.error = "empty_ocr_pages_output"
                return base_result

            stats.tdrs_processed_with_ocr += 1
            total_pages = len(pages)
            coverage_pct = ocr_manifest.coverage_after_pct
        else:
            stats.tdrs_available += 1
            total_pages = usability["total_pages"]
            coverage_pct = usability["coverage_pct"]
            pages = [p.model_dump(mode="json") for p in extract_pdf_pages(tdr_path, tdr_id=ocid)]

        # ---------------------------------------------------------------
        # Full analysis pipeline
        # ---------------------------------------------------------------
        tdr_pages = [TdrPage.model_validate(p) for p in pages]
        chunks = chunk_pages(tdr_pages, max_chars=self.max_chars, overlap_chars=self.overlap_chars)
        flags = detect_flags_in_pages(tdr_pages)

        dossier = generate_dossier(
            pdf_path=tdr_path,
            sector=change.sector,
            ocid=ocid,
            entity_name=entity,
            procedure_code=_procedure_code(record),
            monto=monto,
            coverage_pct=coverage_pct,
            total_pages=total_pages,
            pages=tdr_pages,
            chunks=chunks,
            flags=flags,
        )

        # ---------------------------------------------------------------
        # Neo4j graph enrichment (obligatorio when RUC data is available)
        # ---------------------------------------------------------------
        s_ruc = _supplier_ruc(record)
        b_ruc = _buyer_ruc(record)
        if s_ruc:
            dossier = enrich_dossier_with_graph(
                dossier=dossier,
                supplier_ruc=s_ruc,
                buyer_ruc=b_ruc,
            )
            stats.dossiers_graph_enriched += 1

        # Write outputs
        result_dir = self.output_dir / slug
        result_dir.mkdir(parents=True, exist_ok=True)

        pages_path = result_dir / "pages.json"
        pages_path.write_text(
            json.dumps(
                {"ocid": ocid, "pages": [p.model_dump(mode="json") for p in tdr_pages]},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        chunks_path = result_dir / "chunks.json"
        chunks_path.write_text(
            json.dumps(
                {"ocid": ocid, "chunks": [c.model_dump(mode="json") for c in chunks]},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        flags_path = result_dir / "flags.json"
        flags_path.write_text(
            json.dumps(
                {"ocid": ocid, "flags": [f.model_dump(mode="json") for f in flags]},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        dossier_json_path = result_dir / "dossier.json"
        dossier_json_path.write_text(
            json.dumps(dossier, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        md = render_dossier_markdown(dossier)
        # Append graph findings section if enrichment ran
        graph_findings = dossier.get("graph_findings") or {}
        graph_md = render_graph_findings_markdown(graph_findings)
        if graph_md:
            md = md + graph_md
        dossier_md_path = result_dir / "dossier.md"
        dossier_md_path.write_text(md, encoding="utf-8")

        risk_level: str = str(dossier["risk_summary"]["risk_level"])
        stats.dossiers_generated += 1
        if flags:
            stats.dossiers_with_flags += 1
        else:
            stats.dossiers_no_flags += 1

        base_result.status = STATUS_DOSSIER_GENERATED
        base_result.tdr_path = str(tdr_path)
        base_result.pages = total_pages
        base_result.coverage_pct = coverage_pct
        base_result.chunks = len(chunks)
        base_result.flags = len(flags)
        base_result.risk_level = risk_level
        base_result.dossier_path = str(dossier_md_path)
        return base_result
