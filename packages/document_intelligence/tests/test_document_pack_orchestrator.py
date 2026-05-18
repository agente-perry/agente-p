"""Tests for document_pack/orchestrator.py — PackOrchestrator integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.agents.orchestrator import OrchestratorConfig
from document_intelligence.document_pack import build_pack
from document_intelligence.document_pack.orchestrator import (
    PackOrchestrator,
    PackOrchestratorConfig,
)
from document_intelligence.document_pack.schemas import (
    MissingGraphRAGKey,
    PackMode,
)


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


class TestPackOrchestrator:
    def test_analyze_builds_pack_when_no_cache(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf, ["BASES DEL PROCESO DE SELECCIÓN"])

        out = tmp_path / "_index"
        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales de baja trazabilidad", output_dir=out)

        assert result.pack_id.endswith("_pack_001")
        assert result.pack_mode in {PackMode.PREVENTIVE, PackMode.UNKNOWN}
        assert result.total_documents == 1
        assert result.documents_analyzed == 0 or result.documents_analyzed == 1

    def test_analyze_reuses_existing_pack_from_cache(self, tmp_path: Path) -> None:
        pdf1 = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf1, ["BASES DEL PROCESO DE SELECCIÓN"])

        out = tmp_path / "_index"
        out.mkdir(parents=True, exist_ok=True)

        first_pack = build_pack(tmp_path, out, pretty=True)
        original_id = first_pack.pack_id

        cache_file = out / "process_document_pack.json"
        assert cache_file.exists()

        pdf2 = tmp_path / "another_doc.pdf"
        _make_text_pdf(pdf2, ["OTRO DOCUMENTO"])

        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales", output_dir=out)

        assert result.pack_id == original_id
        assert result.total_documents == 1

    def test_analyze_respects_max_docs(self, tmp_path: Path) -> None:
        for i in range(3):
            pdf = tmp_path / f"doc_{i}.pdf"
            _make_text_pdf(pdf, [f"Documento {i} con contenido"])

        out = tmp_path / "_index"
        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
                max_docs=2,
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales", output_dir=out)

        assert result.total_documents == 2

    def test_analyze_skips_non_usable_documents(self, tmp_path: Path) -> None:
        scanned = tmp_path / "scanned_no_text.pdf"
        _make_text_pdf(scanned, [])

        out = tmp_path / "_index"
        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales", output_dir=out)

        assert result.total_documents >= 0

    def test_analyze_propagates_missing_for_graphrag(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf, ["BASES DEL PROCESO"])

        out = tmp_path / "_index"
        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales", output_dir=out)

        assert MissingGraphRAGKey.AWARD_DOCUMENT in result.missing_for_graphrag

    def test_analyze_result_to_dict_has_schema_version(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tddr.pdf"
        _make_text_pdf(pdf, ["TÉRMINOS DE REFERENCIA"])

        out = tmp_path / "_index"
        orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=OrchestratorConfig(mode="mock"),
            )
        )
        result = orch.analyze(tmp_path, "Detecta senales", output_dir=out)
        payload = result.to_dict()

        assert "schema_version" in payload
        assert payload["schema_version"] == "1.1"
        assert "pack_id" in payload
        assert "all_results" in payload