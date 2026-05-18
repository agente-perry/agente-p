from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


validate_script = _load_script("validate_scraping_delivery")
build_script = _load_script("build_process_document_packs")
select_script = _load_script("select_golden_candidates")


PROCESS_COLUMNS = [
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
]

DOCUMENT_COLUMNS = [
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
]

AWARD_COLUMNS = [
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
]


def test_valid_scraping_delivery_passes(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path)

    report = validate_script.validate_delivery(base_dir, check_pdf_open=False)

    assert report.ok
    assert report.to_dict()["documents_total"] == 1
    assert report.to_dict()["ocr"]["textual"] == 1


def test_missing_required_column_fails(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path, process_columns=PROCESS_COLUMNS[:-1])

    report = validate_script.validate_delivery(base_dir, check_pdf_open=False)

    assert not report.ok
    assert any("processes.csv: missing columns: scraped_at" in error for error in report.errors)


def test_missing_document_file_fails(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path, file_exists=False)

    report = validate_script.validate_delivery(base_dir, check_pdf_open=False)

    assert not report.ok
    assert any("file_path does not exist" in error for error in report.errors)


def test_award_without_quote_fails(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path, award_quote="")

    report = validate_script.validate_delivery(base_dir, check_pdf_open=False)
    assert not report.ok
    assert any("supplier_name requires award_source_quote" in error for error in report.errors)


def test_build_process_document_packs_outputs_jsonl(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path)

    output = build_script.build_process_document_packs(base_dir)
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["process_id"] == "proc-1"
    assert rows[0]["procedure_code"] == "AS-SM-1-2025"
    assert rows[0]["documents"][0]["ocr_required"] is False
    assert rows[0]["award"]["supplier_ruc"] == "20123456789"


def test_select_golden_candidates_filters_usable_processes(tmp_path: Path) -> None:
    base_dir = _write_delivery_fixture(tmp_path)
    output_path = tmp_path / "golden" / "metadata.csv"

    output = select_script.select_golden_candidates(base_dir, output_path)

    with output.open("r", encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    assert len(rows) == 1
    assert rows[0]["process_id"] == "proc-1"
    assert rows[0]["document_type"] == "bases_integradas"


def _write_delivery_fixture(
    tmp_path: Path,
    *,
    process_columns: list[str] | None = None,
    file_exists: bool = True,
    award_quote: str = "Se adjudica al proveedor ganador",
) -> Path:
    base_dir = tmp_path / "data" / "scraped" / "seace_salud"
    pdf_dir = base_dir / "pdfs" / "proc-1"
    pdf_dir.mkdir(parents=True)
    document_path = pdf_dir / "bases.pdf"
    file_bytes = b"fake pdf bytes for metadata validation"
    if file_exists:
        document_path.write_bytes(file_bytes)
    sha256 = hashlib.sha256(file_bytes).hexdigest()

    _write_csv(
        base_dir / "processes.csv",
        process_columns or PROCESS_COLUMNS,
        [
            {
                "process_id": "proc-1",
                "ocid": "ocds-1",
                "seace_code": "AS-SM-1-2025",
                "sector": "salud",
                "entity_name": "Hospital Demo",
                "entity_ruc": "20500000001",
                "procedure_type": "Adjudicacion Simplificada",
                "object_description": "Compra de equipos medicos",
                "status": "adjudicado",
                "amount_estimated": "1000.50",
                "currency": "PEN",
                "publication_date": "2025-01-01",
                "award_date": "2025-01-10",
                "source_url": "https://example.test/process",
                "scraped_at": "2026-05-17T00:00:00Z",
            }
        ],
    )
    _write_csv(
        base_dir / "documents.csv",
        DOCUMENT_COLUMNS,
        [
            {
                "document_id": "doc-1",
                "process_id": "proc-1",
                "document_type": "bases_integradas",
                "file_name": "bases.pdf",
                "file_path": str(document_path),
                "file_url": "https://example.test/bases.pdf",
                "source_url": "https://example.test/process",
                "mime_type": "application/pdf",
                "file_size_bytes": str(len(file_bytes)),
                "sha256": sha256,
                "pages_total": "2",
                "pages_with_text": "2",
                "pages_needing_ocr": "0",
                "text_coverage_ratio": "0.95",
                "ocr_class": "textual",
                "ocr_required": "false",
                "ocr_status": "not_needed",
                "downloaded_at": "2026-05-17T00:00:00Z",
                "parse_status": "parsed",
                "error_message": "",
            }
        ],
    )
    _write_csv(
        base_dir / "awards.csv",
        AWARD_COLUMNS,
        [
            {
                "award_id": "award-1",
                "process_id": "proc-1",
                "supplier_name": "Proveedor Demo SAC",
                "supplier_ruc": "20123456789",
                "award_amount": "950.25",
                "award_currency": "PEN",
                "award_date": "2025-01-10",
                "award_document_id": "doc-1",
                "award_source_quote": award_quote,
                "award_source_page": "1",
                "confidence": "high",
            }
        ],
    )
    return base_dir


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
