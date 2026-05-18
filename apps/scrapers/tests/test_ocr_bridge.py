from __future__ import annotations

import json
from pathlib import Path

from agenteperry.ocr.bridge import (
    build_ocr_bridge_bundles,
    prepare_analyzer_bundles,
    prepare_loader_inputs,
)


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_build_bridge_bundle_with_contract_context(tmp_path: Path) -> None:
    ocr_doc = tmp_path / "ocr" / "ocds_dgv273_seacev3_123_a1b2c3d4"
    _write(
        ocr_doc / "ocr_manifest.json",
        {
            "document_id": "ocds_dgv273_seacev3_123_a1b2c3d4",
            "ocid": "ocds-dgv273-seacev3-123",
            "source_pdf_path": "/tmp/doc.pdf",
            "source_pdf_sha256": "abc",
            "ocr_provider": "minimax",
            "ocr_model": "MiniCPM-v2",
            "pages_total": 2,
            "pages_attempted": 1,
            "pages_succeeded": 1,
            "pages_failed": 0,
            "status": "completed",
            "coverage_before_pct": 0.0,
            "coverage_after_pct": 100.0,
            "output_dir": str(ocr_doc),
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:10+00:00",
            "errors_count": 0,
        },
    )
    _write_jsonl(
        ocr_doc / "ocr_pages.jsonl",
        [
            {"page_number": 1, "status": "ok", "text": "hola", "text_length": 4, "provider": "x", "model": "y", "latency_ms": 1, "error": None},
            {"page_number": 2, "status": "ok", "text": "mundo", "text_length": 5, "provider": "x", "model": "y", "latency_ms": 1, "error": None},
        ],
    )
    (ocr_doc / "ocr_text.txt").write_text("texto", encoding="utf-8")

    contracts = tmp_path / "contracts.jsonl"
    _write_jsonl(
        contracts,
        [
            {
                "ocid": "ocds-dgv273-seacev3-123",
                "entity_name": "ESSALUD",
                "supplier_name": "Proveedor SAC",
                "supplier_ruc": "20123456789",
                "monto": 1000,
                "documents": [{"title": "Bases", "url": "https://example.com/bases.pdf", "format": "pdf"}],
            }
        ],
    )

    results = build_ocr_bridge_bundles(tmp_path / "ocr", tmp_path / "bridge", contracts_jsonl=contracts)
    assert len(results) == 1
    assert results[0].status == "ready"

    bundle_dir = Path(results[0].bundle_dir or "")
    assert (bundle_dir / "pages.json").exists()
    assert (bundle_dir / "contract_context.json").exists()
    assert (bundle_dir / "provenance.json").exists()


def test_build_bridge_bundle_normalizes_ocid_for_contract_match(tmp_path: Path) -> None:
    ocr_doc = tmp_path / "ocr" / "doc_a"
    _write(
        ocr_doc / "ocr_manifest.json",
        {
            "document_id": "doc_a",
            "ocid": "OCDS_DGV273_SEACEV3_ABC-123",
            "source_pdf_path": "/tmp/doc_a.pdf",
        },
    )
    _write_jsonl(ocr_doc / "ocr_pages.jsonl", [{"page_number": 1, "text": "hola"}])
    (ocr_doc / "ocr_text.txt").write_text("texto", encoding="utf-8")

    contracts = tmp_path / "contracts.jsonl"
    _write_jsonl(
        contracts,
        [
            {
                "ocid": "ocds-dgv273-seacev3-abc-123",
                "entity_name": "Entidad",
                "documents": [],
            }
        ],
    )

    results = build_ocr_bridge_bundles(tmp_path / "ocr", tmp_path / "bridge", contracts_jsonl=contracts, strict=True)
    assert len(results) == 1
    assert results[0].status == "ready"


def test_prepare_analyzer_bundles_creates_chunks_flags_and_manifest(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge" / "doc_1"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    _write(
        bridge_dir / "bundle_manifest.json",
        {
            "document_id": "doc_1",
            "ocid": "ocds-dgv273-seacev3-123",
            "outputs": {
                "pages_json": str(bridge_dir / "pages.json"),
                "contract_context_json": str(bridge_dir / "contract_context.json"),
                "provenance_json": str(bridge_dir / "provenance.json"),
            },
        },
    )
    _write(
        bridge_dir / "pages.json",
        {
            "pages": [
                {"tdr_id": "doc_1", "page_number": 1, "text_content": "Se solicita informe de 300 paginas."},
                {"tdr_id": "doc_1", "page_number": 2, "text_content": "Formato A3 en entrega fisica."},
            ]
        },
    )
    _write(bridge_dir / "contract_context.json", {"document_id": "doc_1"})
    _write(bridge_dir / "provenance.json", {"document_id": "doc_1"})

    results = prepare_analyzer_bundles(tmp_path / "bridge")
    assert len(results) == 1
    assert results[0].status == "ready"
    assert results[0].chunks_count > 0
    assert (bridge_dir / "chunks.json").exists()
    assert (bridge_dir / "flags.json").exists()
    assert (tmp_path / "bridge" / "analyzer_input_manifest.json").exists()


def test_prepare_analyzer_bundles_strict_requires_context_files(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge" / "doc_2"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    _write(
        bridge_dir / "bundle_manifest.json",
        {
            "document_id": "doc_2",
            "ocid": "ocds-dgv273-seacev3-999",
            "outputs": {
                "pages_json": str(bridge_dir / "pages.json"),
                "contract_context_json": str(bridge_dir / "missing_contract_context.json"),
                "provenance_json": str(bridge_dir / "missing_provenance.json"),
            },
        },
    )
    _write(
        bridge_dir / "pages.json",
        {
            "pages": [
                {"tdr_id": "doc_2", "page_number": 1, "text_content": "texto base"},
            ]
        },
    )

    results = prepare_analyzer_bundles(tmp_path / "bridge", strict=True)
    assert len(results) == 1
    assert results[0].status == "skipped"
    assert results[0].reason == "missing_bridge_context"


def test_prepare_loader_inputs_creates_manifest_jsonl_and_index(tmp_path: Path) -> None:
    bridge_dir = tmp_path / "bridge" / "doc_3"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    _write(
        bridge_dir / "bundle_manifest.json",
        {
            "document_id": "doc_3",
            "ocid": "ocds-dgv273-seacev3-321",
            "outputs": {
                "pages_json": str(bridge_dir / "pages.json"),
                "contract_context_json": str(bridge_dir / "contract_context.json"),
                "provenance_json": str(bridge_dir / "provenance.json"),
            },
        },
    )
    _write(
        bridge_dir / "contract_context.json",
        {
            "document_id": "doc_3",
            "contract_context": {
                "entity_name": "Entidad Demo",
                "monto": 1234.5,
                "source_url": "https://example.org/ocid/321",
            },
        },
    )
    _write(bridge_dir / "provenance.json", {"document_id": "doc_3"})
    _write(bridge_dir / "chunks.json", {"chunks": []})
    _write(bridge_dir / "flags.json", {"flags": []})

    results = prepare_loader_inputs(tmp_path / "bridge", strict=True)
    assert len(results) == 1
    assert results[0].status == "ready"
    assert (bridge_dir / "tdr_manifest.jsonl").exists()
    assert (tmp_path / "bridge" / "loader_input_manifest.json").exists()
