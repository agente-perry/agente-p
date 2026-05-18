from __future__ import annotations

from pathlib import Path

import fitz
from click.testing import CliRunner

from agenteperry.cli import main
from agenteperry.ocr import cli as ocr_cli
from agenteperry.ocr.models import OcrDocumentStatus, OcrManifest


def _make_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


def test_ocr_help() -> None:
    result = CliRunner().invoke(main, ["ocr", "--help"])
    assert result.exit_code == 0
    assert "classify" in result.output
    assert "run" in result.output
    assert "bridge" in result.output
    assert "prepare-analyzer" in result.output
    assert "prepare-loader" in result.output
    assert "load-ready" in result.output
    assert "run-all" in result.output


def test_ocr_classify_command(tmp_path: Path) -> None:
    _make_pdf(tmp_path / "a.pdf", ["hello" * 20])
    result = CliRunner().invoke(main, ["ocr", "classify", "--input", str(tmp_path), "--recursive"])
    assert result.exit_code == 0
    assert "OCR classification" in result.output
    assert "textual" in result.output


def test_ocr_run_dry_run(monkeypatch, tmp_path: Path) -> None:
    _make_pdf(tmp_path / "a.pdf", ["", ""])

    async def _fake_process_many(*args, **kwargs):  # type: ignore[no-untyped-def]
        out_dir = tmp_path / "out" / "doc"
        out_dir.mkdir(parents=True, exist_ok=True)
        return [
            OcrManifest(
                document_id="doc",
                ocid=None,
                source_pdf_path=str(tmp_path / "a.pdf"),
                source_pdf_sha256="abc",
                ocr_provider="minimax",
                ocr_model="MiniCPM-v2",
                pages_total=2,
                pages_attempted=0,
                pages_succeeded=0,
                pages_failed=0,
                status=OcrDocumentStatus.SKIPPED,
                coverage_before_pct=0.0,
                coverage_after_pct=0.0,
                output_dir=str(out_dir),
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:00+00:00",
                errors_count=0,
            )
        ]

    monkeypatch.setattr(ocr_cli, "process_many", _fake_process_many)
    result = CliRunner().invoke(
        main,
        [
            "ocr",
            "run",
            "--input",
            str(tmp_path),
            "--dry-run",
            "--limit",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "OCR run summary" in result.output


def test_ocr_load_ready_dry_run(tmp_path: Path) -> None:
    bridge_root = tmp_path / "bridge"
    bridge_root.mkdir(parents=True, exist_ok=True)
    (bridge_root / "loader_input_manifest.json").write_text(
        '{"bundles":[{"document_id":"doc-1","manifest_jsonl":"/tmp/m1.jsonl","chunks_json":"/tmp/c1.json","flags_json":"/tmp/f1.json"}]}\n',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        [
            "ocr",
            "load-ready",
            "--input",
            str(bridge_root),
            "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "OCR load-ready summary" in result.output
    assert "dry-run" in result.output


def test_ocr_run_all_dry_load(monkeypatch, tmp_path: Path) -> None:
    input_dir = tmp_path / "in"
    input_dir.mkdir(parents=True, exist_ok=True)
    _make_pdf(input_dir / "a.pdf", ["texto"])

    contracts = tmp_path / "contracts.jsonl"
    contracts.write_text('{"ocid":"ocds-dgv273-seacev3-1"}\n', encoding="utf-8")

    async def _fake_process_many(*args, **kwargs):  # type: ignore[no-untyped-def]
        out_dir = tmp_path / "ocr" / "doc"
        out_dir.mkdir(parents=True, exist_ok=True)
        return [
            OcrManifest(
                document_id="doc",
                ocid="ocds-dgv273-seacev3-1",
                source_pdf_path=str(input_dir / "a.pdf"),
                source_pdf_sha256="abc",
                ocr_provider="minimax",
                ocr_model="MiniCPM-v2",
                pages_total=1,
                pages_attempted=1,
                pages_succeeded=1,
                pages_failed=0,
                status=OcrDocumentStatus.COMPLETED,
                coverage_before_pct=0.0,
                coverage_after_pct=100.0,
                output_dir=str(out_dir),
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:00+00:00",
                errors_count=0,
            )
        ]

    class _SimpleResult:
        def __init__(self, status: str):
            self.status = status

    monkeypatch.setattr(ocr_cli, "process_many", _fake_process_many)
    monkeypatch.setattr(ocr_cli, "build_ocr_bridge_bundles", lambda *a, **k: [_SimpleResult("ready")])
    monkeypatch.setattr(ocr_cli, "prepare_analyzer_bundles", lambda *a, **k: [_SimpleResult("ready")])
    monkeypatch.setattr(ocr_cli, "prepare_loader_inputs", lambda *a, **k: [_SimpleResult("ready")])
    monkeypatch.setattr(ocr_cli, "_load_ready_from_manifest", lambda *a, **k: ([("doc", "ready", 0, 0, 0, "dry_run")], 0))

    result = CliRunner().invoke(
        main,
        [
            "ocr",
            "run-all",
            "--input",
            str(input_dir),
            "--contracts-jsonl",
            str(contracts),
            "--ocr-output-dir",
            str(tmp_path / "ocr"),
            "--bridge-output-dir",
            str(tmp_path / "bridge"),
            "--load-ready",
            "--load-dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "OCR processed docs" in result.output
    assert "bridge bundles ready" in result.output
