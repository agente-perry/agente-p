"""E2E CLI smoke tests for build-pack and analyze-pack commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from document_intelligence.cli import main


def _make_text_pdf(path: Path, lines: list[str]) -> None:
    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfgen import canvas
    except ImportError:  # pragma: no cover
        pytest.skip("reportlab not installed")

    doc = canvas.Canvas(str(path), pagesize=LETTER)
    y = 740
    for line in lines:
        doc.drawString(72, y, line)
        y -= 18
        if y < 72:
            doc.showPage()
            y = 740
    doc.showPage()
    doc.save()


class TestBuildPackCLI:
    def test_build_pack_creates_all_artifact_files(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_integradas.pdf"
        _make_text_pdf(pdf, ["BASES INTEGRADAS DEL PROCESO DE SELECCIÓN"])

        out = tmp_path / "_index"
        runner = CliRunner()
        result = runner.invoke(main, [
            "build-pack", str(tmp_path),
            "--out", str(out),
            "--pretty",
        ])
        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}\nException: {result.exception}"
        assert "Pack '" in result.output

        expected = [
            "pdf_inventory.json",
            "document_manifest.json",
            "process_document_pack.json",
            "document_pack_graph.json",
            "clusters.json",
            "chunks.jsonl",
            "parse_report.json",
            "pack_summary.md",
        ]
        for name in expected:
            assert (out / name).exists(), f"{name} not found after build-pack"

    def test_build_pack_exits_nonzero_on_missing_directory(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(main, [
            "build-pack", str(tmp_path / "nonexistent"),
        ])
        assert result.exit_code != 0

    def test_build_pack_with_max_docs(self, tmp_path: Path) -> None:
        for i in range(5):
            pdf = tmp_path / f"doc_{i}.pdf"
            _make_text_pdf(pdf, [f"Documento {i}"])

        out = tmp_path / "_index"
        runner = CliRunner()
        result = runner.invoke(main, [
            "build-pack", str(tmp_path),
            "--out", str(out),
            "--max-docs", "3",
        ])
        assert result.exit_code == 0
        manifest = json.loads((out / "document_manifest.json").read_text(encoding="utf-8"))
        assert len(manifest) == 3


class TestAnalyzePackCLI:
    def test_analyze_pack_exits_zero_with_mock_mode(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, ["TÉRMINOS DE REFERENCIA"])

        out = tmp_path / "_index"
        runner = CliRunner()
        build_result = runner.invoke(main, [
            "build-pack", str(tmp_path), "--out", str(out),
        ])
        assert build_result.exit_code == 0

        analyze_result = runner.invoke(main, [
            "analyze-pack", str(tmp_path),
            "--question", "Detecta senales de baja trazabilidad",
            "--mode", "mock",
            "--out", str(out),
        ])
        assert analyze_result.exit_code == 0, (
            f"analyze-pack failed with exit code {analyze_result.exit_code}\n"
            f"Output: {analyze_result.output}\n"
            f"Exception: {analyze_result.exception}"
        )

    def test_analyze_pack_returns_json_with_schema_version(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf, ["BASES DEL PROCESO"])

        out = tmp_path / "_index"
        runner = CliRunner()
        _ = runner.invoke(main, ["build-pack", str(tmp_path), "--out", str(out)])

        result = runner.invoke(main, [
            "analyze-pack", str(tmp_path),
            "--question", "Detecta senales de baja trazabilidad",
            "--mode", "mock",
            "--out", str(out),
        ])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "schema_version" in payload, f"schema_version missing from output keys: {list(payload.keys())}"
        assert payload["schema_version"] == "1.1"
        assert "pack_id" in payload
        assert "all_results" in payload

    def test_analyze_pack_with_pretty_flag(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, ["TÉRMINOS DE REFERENCIA"])

        out = tmp_path / "_index"
        runner = CliRunner()
        _ = runner.invoke(main, ["build-pack", str(tmp_path), "--out", str(out)])

        result = runner.invoke(main, [
            "analyze-pack", str(tmp_path),
            "--question", "Detecta senales",
            "--mode", "mock",
            "--out", str(out),
            "--pretty",
        ])
        assert result.exit_code == 0
        assert "\n" in result.output

    def test_analyze_pack_with_max_docs(self, tmp_path: Path) -> None:
        for i in range(3):
            pdf = tmp_path / f"doc_{i}.pdf"
            _make_text_pdf(pdf, [f"Documento {i}"])

        out = tmp_path / "_index"
        runner = CliRunner()
        _ = runner.invoke(main, ["build-pack", str(tmp_path), "--out", str(out)])

        result = runner.invoke(main, [
            "analyze-pack", str(tmp_path),
            "--question", "Detecta senales",
            "--mode", "mock",
            "--out", str(out),
            "--max-docs", "2",
        ])
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "pack_id" in payload
        assert isinstance(payload["total_documents"], int)
        assert isinstance(payload["documents_analyzed"], int)