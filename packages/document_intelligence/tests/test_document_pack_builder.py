"""Tests for document_pack/pack_builder.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from document_intelligence.document_pack.pack_builder import build_pack
from document_intelligence.document_pack.schemas import (
    DocumentType,
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


class TestBuildPack:
    def test_build_pack_produces_pack_id(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_integradas.pdf"
        _make_text_pdf(pdf, ["BASES INTEGRADAS DEL PROCESO DE SELECCIÓN"])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out)
        assert pack.pack_id.endswith("_pack_001")

    def test_build_pack_sets_preventive_mode_when_bases_no_winner(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf, ["BASES DEL PROCESO DE SELECCIÓN"])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out)
        assert pack.mode == PackMode.PREVENTIVE
        assert pack.has_tdr_or_bases is True
        assert pack.has_award_document is False

    def test_build_pack_sets_investigative_mode_with_buena_pro(self, tmp_path: Path) -> None:
        bases = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(bases, ["BASES DEL PROCESO DE SELECCIÓN"])
        buena = tmp_path / "buena_pro.pdf"
        _make_text_pdf(buena, ["SE DECLARA LA BUENA PRO a favor del postor."])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out)
        assert pack.mode == PackMode.INVESTIGATIVE
        assert pack.has_tdr_or_bases is True
        assert pack.has_award_document is True

    def test_build_pack_sets_unknown_mode_when_no_bases(self, tmp_path: Path) -> None:
        doc = tmp_path / "random_document.pdf"
        _make_text_pdf(doc, ["Un documento sin señal clara."])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out)
        assert pack.mode == PackMode.UNKNOWN
        assert pack.has_tdr_or_bases is False

    def test_build_pack_detects_missing_award_document(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_del_proceso.pdf"
        _make_text_pdf(pdf, ["BASES DEL PROCESO"])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out)
        assert "award_document" in pack.missing_for_graphrag

    def test_build_pack_writes_all_artifact_files(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_integradas.pdf"
        _make_text_pdf(pdf, ["BASES INTEGRADAS"])

        out = tmp_path / "_index"
        build_pack(tmp_path, out)

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
            assert (out / name).exists(), f"{name} not found"

    def test_build_pack_manifest_has_document_type(self, tmp_path: Path) -> None:
        pdf = tmp_path / "bases_integradas.pdf"
        _make_text_pdf(pdf, ["BASES INTEGRADAS"])

        out = tmp_path / "_index"
        build_pack(tmp_path, out)

        manifest = json.loads((out / "document_manifest.json").read_text(encoding="utf-8"))
        assert len(manifest) == 1
        assert manifest[0]["document_type"] == DocumentType.BASES_INTEGRADAS.value

    def test_build_pack_inventory_json_is_valid(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, ["TÉRMINOS DE REFERENCIA"])

        out = tmp_path / "_index"
        build_pack(tmp_path, out)

        data = json.loads((out / "pdf_inventory.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert "sha256" in data[0]
        assert "pages_total" in data[0]

    def test_build_pack_clusters_json_is_valid(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, [
            "OBJETO DEL SERVICIO",
            "EXPERIENCIA DEL POSTOR",
            "ENTREGABLES",
            "CRITERIOS DE EVALUACION",
        ])

        out = tmp_path / "_index"
        build_pack(tmp_path, out)

        clusters = json.loads((out / "clusters.json").read_text(encoding="utf-8"))
        assert isinstance(clusters, list)

    def test_build_pack_chunks_jsonl_is_valid(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, [
            "OBJETO DEL SERVICIO — Consulta aquí",
            "EXPERIENCIA DEL POSTOR — Verificar",
            "ENTREGABLES — Recibir",
        ])

        out = tmp_path / "_index"
        build_pack(tmp_path, out)

        lines = (out / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        if lines:
            first = json.loads(lines[0])
            assert "chunk_id" in first or "document_id" in first

    def test_build_pack_respects_max_docs(self, tmp_path: Path) -> None:
        for i in range(5):
            pdf = tmp_path / f"doc_{i}.pdf"
            _make_text_pdf(pdf, [f"Documento {i}"])

        out = tmp_path / "_index"
        pack = build_pack(tmp_path, out, max_docs=3)
        assert pack.total_documents == 3

    def test_build_pack_respects_pretty_flag(self, tmp_path: Path) -> None:
        pdf = tmp_path / "tdr.pdf"
        _make_text_pdf(pdf, ["TÉRMINOS DE REFERENCIA"])

        out_pretty = tmp_path / "_pretty"
        out_raw = tmp_path / "_raw"
        build_pack(tmp_path, out_pretty, pretty=True)
        build_pack(tmp_path, out_raw, pretty=False)

        pretty_size = (out_pretty / "process_document_pack.json").stat().st_size
        raw_size = (out_raw / "process_document_pack.json").stat().st_size
        assert pretty_size >= raw_size