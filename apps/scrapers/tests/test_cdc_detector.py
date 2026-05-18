"""Tests for the CDC detector and pipeline (Activity 7 — automated pipeline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agenteperry.cdc.detector import (
    SEACEChangeDetector,
    compute_record_hash,
    detect_sector,
    is_priority,
    load_known_hashes,
    save_known_hashes,
)
from agenteperry.cdc.pipeline import (
    STATUS_DOSSIER_GENERATED,
    STATUS_DRY_RUN,
    CDCPipeline,
)
from agenteperry.ocr.models import OcrManifest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def hash_file(tmp_path: Path) -> Path:
    return tmp_path / "hashes.json"


@pytest.fixture()
def salud_record() -> dict[str, Any]:
    return {
        "ocid": "ocds-dgv273-seacev3-988512",
        "external_id": "ocds-dgv273-seacev3-988512:988512-1",
        "entity": "SEGURO SOCIAL DE SALUD",
        "entity_ruc": "20131257750",
        "monto": 195383235.96,
        "fecha": "2024-02-14",
        "modalidad": "Adjudicación Simplificada",
        "proveedor_ruc": "20605681281",
        "documents": [
            {
                "title": "Bases Integradas",
                "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=abc123",
                "format": "pdf",
            }
        ],
    }


@pytest.fixture()
def ambiente_record() -> dict[str, Any]:
    return {
        "ocid": "ocds-dgv273-seacev3-1157442",
        "external_id": "ocds-dgv273-seacev3-1157442:1",
        "entity": "AUTORIDAD NACIONAL DEL AGUA (ANA)",
        "monto": 2995887.60,
        "fecha": "2024-08-08",
        "modalidad": "Adjudicación Simplificada",
        "proveedor_ruc": "20123456789",
        "documents": [],
    }


@pytest.fixture()
def non_priority_record() -> dict[str, Any]:
    return {
        "ocid": "ocds-dgv273-seacev3-999999",
        "entity": "MUNICIPALIDAD DISTRITAL DE MIRAFLORES",
        "monto": 50000.00,
        "fecha": "2024-01-15",
        "modalidad": "Adjudicación Simplificada",
        "proveedor_ruc": "20999999999",
        "documents": [],
    }


# ---------------------------------------------------------------------------
# Unit: compute_record_hash
# ---------------------------------------------------------------------------

def test_compute_record_hash_is_deterministic(salud_record: dict[str, Any]) -> None:
    h1 = compute_record_hash(salud_record)
    h2 = compute_record_hash(salud_record)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_record_hash_changes_on_monto(salud_record: dict[str, Any]) -> None:
    h1 = compute_record_hash(salud_record)
    modified = {**salud_record, "monto": 200_000_000.00}
    h2 = compute_record_hash(modified)
    assert h1 != h2


def test_compute_record_hash_changes_on_supplier(salud_record: dict[str, Any]) -> None:
    h1 = compute_record_hash(salud_record)
    modified = {**salud_record, "proveedor_ruc": "20111111111"}
    h2 = compute_record_hash(modified)
    assert h1 != h2


def test_compute_record_hash_ignores_documents(salud_record: dict[str, Any]) -> None:
    """Document URLs changing should NOT trigger a change — only contract terms matter."""
    h1 = compute_record_hash(salud_record)
    modified = {**salud_record, "documents": [{"title": "Other doc", "url": "https://new.url"}]}
    h2 = compute_record_hash(modified)
    assert h1 == h2


# ---------------------------------------------------------------------------
# Unit: detect_sector / is_priority
# ---------------------------------------------------------------------------

def test_detect_sector_salud(salud_record: dict[str, Any]) -> None:
    assert detect_sector(salud_record) == "salud"


def test_detect_sector_ambiente(ambiente_record: dict[str, Any]) -> None:
    assert detect_sector(ambiente_record) == "ambiente"


def test_detect_sector_otros(non_priority_record: dict[str, Any]) -> None:
    assert detect_sector(non_priority_record) == "otros"


def test_is_priority_salud(salud_record: dict[str, Any]) -> None:
    assert is_priority(salud_record) is True


def test_is_priority_ambiente(ambiente_record: dict[str, Any]) -> None:
    assert is_priority(ambiente_record) is True


def test_is_priority_other(non_priority_record: dict[str, Any]) -> None:
    assert is_priority(non_priority_record) is False


# ---------------------------------------------------------------------------
# Unit: hash registry persistence
# ---------------------------------------------------------------------------

def test_save_and_load_hashes(tmp_path: Path) -> None:
    hashes = {"ocid-1": "abc", "ocid-2": "def"}
    path = tmp_path / "hashes.json"
    save_known_hashes(hashes, path)
    loaded = load_known_hashes(path)
    assert loaded == hashes


def test_load_hashes_missing_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "nonexistent.json"
    assert load_known_hashes(path) == {}


def test_load_hashes_corrupt_file_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not valid json", encoding="utf-8")
    assert load_known_hashes(path) == {}


# ---------------------------------------------------------------------------
# Unit: SEACEChangeDetector
# ---------------------------------------------------------------------------

def test_first_run_emits_all_as_new(
    hash_file: Path,
    salud_record: dict[str, Any],
    ambiente_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    events = list(detector.detect_changes([salud_record, ambiente_record]))
    assert len(events) == 2
    assert all(e.change_type == "new" for e in events)


def test_second_run_emits_no_changes(
    hash_file: Path,
    salud_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    list(detector.detect_changes([salud_record]))
    detector.commit()

    detector2 = SEACEChangeDetector(hash_file=hash_file)
    events = list(detector2.detect_changes([salud_record]))
    assert events == []


def test_modified_record_emits_modified_event(
    hash_file: Path,
    salud_record: dict[str, Any],
) -> None:
    # First run — register
    d1 = SEACEChangeDetector(hash_file=hash_file)
    list(d1.detect_changes([salud_record]))
    d1.commit()

    # Second run with different monto
    modified = {**salud_record, "monto": 200_000_000.00}
    d2 = SEACEChangeDetector(hash_file=hash_file)
    events = list(d2.detect_changes([modified]))
    assert len(events) == 1
    assert events[0].change_type == "modified"
    assert events[0].ocid == salud_record["ocid"]


def test_sector_filter_excludes_other_sectors(
    hash_file: Path,
    salud_record: dict[str, Any],
    ambiente_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    events = list(
        detector.detect_changes(
            [salud_record, ambiente_record],
            sector_filter="salud",
        )
    )
    assert len(events) == 1
    assert events[0].sector == "salud"


def test_priority_only_excludes_non_priority(
    hash_file: Path,
    salud_record: dict[str, Any],
    non_priority_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    events = list(
        detector.detect_changes(
            [salud_record, non_priority_record],
            priority_only=True,
        )
    )
    assert all(e.is_priority for e in events)
    assert len(events) == 1


def test_commit_persists_hashes(
    hash_file: Path,
    salud_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    list(detector.detect_changes([salud_record]))
    assert detector.total_updated == 1
    detector.commit()
    assert hash_file.exists()

    data: dict[str, str] = json.loads(hash_file.read_text(encoding="utf-8"))
    assert salud_record["ocid"] in data


def test_change_event_fields(
    hash_file: Path,
    salud_record: dict[str, Any],
) -> None:
    detector = SEACEChangeDetector(hash_file=hash_file)
    events = list(detector.detect_changes([salud_record]))
    assert len(events) == 1
    e = events[0]
    assert e.ocid == salud_record["ocid"]
    assert e.change_type == "new"
    assert e.is_priority is True
    assert e.sector == "salud"
    assert e.previous_hash is None
    assert len(e.current_hash) == 64
    assert "detected_at" in e.__dataclass_fields__


def test_reset_clears_registry(hash_file: Path, salud_record: dict[str, Any]) -> None:
    d = SEACEChangeDetector(hash_file=hash_file)
    list(d.detect_changes([salud_record]))
    d.commit()
    assert d.total_known == 1

    d.reset()
    assert d.total_known == 0

    # After reset, same record appears as "new" again
    d2 = SEACEChangeDetector(hash_file=hash_file)
    events = list(d2.detect_changes([salud_record]))
    assert len(events) == 1
    assert events[0].change_type == "new"


# ---------------------------------------------------------------------------
# Unit: CDCPipeline dry_run
# ---------------------------------------------------------------------------

def test_cdc_pipeline_dry_run_does_not_download(
    hash_file: Path,
    salud_record: dict[str, Any],
    tmp_path: Path,
) -> None:
    pipeline = CDCPipeline(
        sector_filter="salud",
        limit=5,
        dry_run=True,
        output_dir=tmp_path / "results",
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    stats, results = pipeline.run([salud_record], detector)

    assert stats.total_evaluated == 1
    assert stats.priority_contracts >= 1
    # In dry_run, no files should be created
    assert not (tmp_path / "results").exists() or not any(
        (tmp_path / "results").iterdir()
    )


def test_cdc_pipeline_dry_run_reports_tdr_url(
    hash_file: Path,
    salud_record: dict[str, Any],
    tmp_path: Path,
) -> None:
    pipeline = CDCPipeline(
        sector_filter="salud",
        limit=5,
        dry_run=True,
        output_dir=tmp_path / "results",
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    _stats, results = pipeline.run([salud_record], detector)

    assert len(results) >= 1
    r = results[0]
    assert r.status == STATUS_DRY_RUN
    assert r.tdr_url is not None  # record has documents
    assert "seace" in r.tdr_url.lower()


def test_cdc_pipeline_dry_run_no_documents_reports_no_tdr(
    hash_file: Path,
    tmp_path: Path,
) -> None:
    record: dict[str, Any] = {
        "ocid": "ocds-test-no-docs",
        "entity": "SEGURO SOCIAL DE SALUD",
        "monto": 1_000_000.0,
        "fecha": "2024-01-01",
        "proveedor_ruc": "20111111111",
        "documents": [],
    }
    pipeline = CDCPipeline(
        sector_filter=None,
        limit=5,
        dry_run=True,
        output_dir=tmp_path / "results",
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    _stats, results = pipeline.run([record], detector)

    assert len(results) >= 1
    r = results[0]
    # No documents → dry_run returns status with no URL
    assert r.tdr_url is None or r.tdr_url == ""


def test_cdc_pipeline_limit_respected(
    hash_file: Path,
    tmp_path: Path,
) -> None:
    records: list[dict[str, Any]] = [
        {
            "ocid": f"ocds-test-{i:04d}",
            "entity": "SEGURO SOCIAL DE SALUD",
            "monto": float(i * 1000),
            "fecha": "2024-01-01",
            "proveedor_ruc": "20111111111",
            "documents": [],
        }
        for i in range(20)
    ]
    pipeline = CDCPipeline(
        sector_filter="salud",
        limit=3,
        dry_run=True,
        output_dir=tmp_path / "results",
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    _stats, results = pipeline.run(records, detector)

    assert len(results) <= 3


# ---------------------------------------------------------------------------
# Integration: full dossier pipeline with real PDF (minimal fixture)
# ---------------------------------------------------------------------------

def test_cdc_pipeline_generates_dossier_for_available_pdf(
    hash_file: Path,
    tmp_path: Path,
) -> None:
    """End-to-end: fake document with local PDF → dossier generated."""
    import fitz

    # Create a minimal PDF with text
    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Bases integradas iso 9001 certificacion internacional entregable unico")
    doc.save(str(pdf_path))
    doc.close()

    # Build a record that points to a local file:// URL
    pdf_url = pdf_path.as_uri()
    record: dict[str, Any] = {
        "ocid": "ocds-test-integration",
        "entity": "SEGURO SOCIAL DE SALUD",
        "monto": 1_000_000.0,
        "fecha": "2024-01-01",
        "proveedor_ruc": "20111111111",
        "documents": [
            {"title": "Bases Integradas", "url": pdf_url, "format": "pdf"}
        ],
    }
    out_dir = tmp_path / "results"
    pipeline = CDCPipeline(
        sector_filter=None,
        limit=5,
        dry_run=False,
        output_dir=out_dir,
        rate_limit_seconds=0.0,
        pdf_only=True,
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    stats, results = pipeline.run([record], detector)

    assert stats.dossiers_generated == 1
    assert len(results) == 1
    r = results[0]
    assert r.status == STATUS_DOSSIER_GENERATED
    assert r.pages > 0
    assert r.chunks > 0
    assert r.dossier_path is not None
    assert Path(r.dossier_path).exists()

    # Verify dossier.json is valid
    result_dir = Path(r.dossier_path).parent
    dossier_json = json.loads((result_dir / "dossier.json").read_text(encoding="utf-8"))
    assert dossier_json["document"]["ocid"] == "ocds-test-integration"
    assert dossier_json["schema_version"] == "1.0"
    assert isinstance(dossier_json["flags"], list)


def test_cdc_pipeline_uses_ocr_fallback_for_scanned_pdf(
    hash_file: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fitz

    pdf_path = tmp_path / "scanned.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "texto minimo")
    doc.save(str(pdf_path))
    doc.close()

    pdf_url = pdf_path.as_uri()
    record: dict[str, Any] = {
        "ocid": "ocds-test-ocr-fallback",
        "entity": "SEGURO SOCIAL DE SALUD",
        "monto": 1000.0,
        "fecha": "2024-01-01",
        "proveedor_ruc": "20111111111",
        "documents": [{"title": "Bases", "url": pdf_url, "format": "pdf"}],
    }

    monkeypatch.setattr(
        "agenteperry.cdc.pipeline.inspect_pdf_text_layer",
        lambda _path: {"is_usable": False, "total_pages": 1, "coverage_pct": 0.0, "tdr_status": "needs_ocr"},
    )

    async def _fake_process_pdf(self, pdf_path: Path, ocid: str | None = None, **kwargs: Any) -> OcrManifest:  # type: ignore[no-untyped-def]
        out_dir = tmp_path / "ocr" / "doc_ocr"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ocr_pages.jsonl").write_text(
            json.dumps({"page_number": 1, "status": "ok", "text": "entregables impresos en A3"}) + "\n",
            encoding="utf-8",
        )
        return OcrManifest(
            document_id="doc_ocr",
            ocid=ocid,
            source_pdf_path=str(pdf_path),
            source_pdf_sha256="abc",
            ocr_provider="minimax",
            ocr_model="MiniCPM-v2",
            pages_total=1,
            pages_attempted=1,
            pages_succeeded=1,
            pages_failed=0,
            status="completed",
            coverage_before_pct=0.0,
            coverage_after_pct=100.0,
            output_dir=str(out_dir),
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            errors_count=0,
        )

    monkeypatch.setattr("agenteperry.ocr.processor.OcrProcessor.process_pdf", _fake_process_pdf)

    out_dir = tmp_path / "results"
    pipeline = CDCPipeline(
        sector_filter=None,
        limit=5,
        dry_run=False,
        output_dir=out_dir,
        rate_limit_seconds=0.0,
        pdf_only=True,
        enable_ocr_fallback=True,
        ocr_output_dir=tmp_path / "ocr",
        ocr_workers=1,
    )
    detector = SEACEChangeDetector(hash_file=hash_file)
    stats, results = pipeline.run([record], detector)

    assert stats.tdrs_needs_ocr == 1
    assert stats.tdrs_processed_with_ocr == 1
    assert stats.dossiers_generated == 1
    assert len(results) == 1
    assert results[0].status == STATUS_DOSSIER_GENERATED
