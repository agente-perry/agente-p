"""Tests for document_pack/classifier.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.document_pack.classifier import (
    _probe_text,
    _score_filename,
    _score_text,
    classify_document,
)
from document_intelligence.document_pack.schemas import DocumentType


class TestFilenameScoring:
    def test_bases_integradas_by_name(self) -> None:
        scores = _score_filename("bases_integradas.pdf")
        assert scores[DocumentType.BASES_INTEGRADAS] > 0

    def test_bases_by_name(self) -> None:
        scores = _score_filename("bases_del_proceso.pdf")
        assert scores[DocumentType.BASES] > 0
        assert scores[DocumentType.BASES_INTEGRADAS] == 0

    def test_tdr_by_name(self) -> None:
        scores = _score_filename("TDR_Servicios_Consultoria.pdf")
        assert scores[DocumentType.TDR] > 0

    def test_buena_pro_by_name(self) -> None:
        scores = _score_filename("buena_pro_2024.pdf")
        assert scores[DocumentType.BUENA_PRO] > 0

    def test_contrato_by_name(self) -> None:
        scores = _score_filename("contrato_ejecucion.pdf")
        assert scores[DocumentType.CONTRATO] > 0

    def test_unknown_for_random_name(self) -> None:
        scores = _score_filename("documento_feligreseado_xyz.pdf")
        assert all(s == 0 for s in scores.values())


class TestTextScoring:
    def test_bases_integradas_keyword(self) -> None:
        text = "BASES INTEGRADAS DEL PROCESO DE SELECCIÓN"
        scores = _score_text(text)
        assert scores[DocumentType.BASES_INTEGRADAS] > 0

    def test_tdr_keyword(self) -> None:
        text = "TÉRMINOS DE REFERENCIA — Servicio de consultoría"
        scores = _score_text(text)
        assert scores[DocumentType.TDR] > 0

    def test_buena_pro_keyword(self) -> None:
        text = "Se declara LA BUENA PRO a favor del postor ganador."
        scores = _score_text(text)
        assert scores[DocumentType.BUENA_PRO] > 0

    def test_absolucion_keyword(self) -> None:
        text = "ABSOLUCIÓN DE CONSULTAS — Pregunta número 1"
        scores = _score_text(text)
        assert scores[DocumentType.ABSOLUCION_CONSULTAS] > 0

    def test_empty_text_returns_zero(self) -> None:
        scores = _score_text("")
        assert all(s == 0.0 for s in scores.values())


class TestClassifyDocument:
    def test_bases_integradas_takes_priority_over_bases(self) -> None:
        from document_intelligence.document_pack.classifier import _merge_scores

        fname_scores = dict.fromkeys(DocumentType, 0.0)
        fname_scores[DocumentType.BASES_INTEGRADAS] = 1.0
        fname_scores[DocumentType.BASES] = 1.0
        text_scores = dict.fromkeys(DocumentType, 0.0)

        dtype, signals = _merge_scores(fname_scores, text_scores)
        assert dtype == DocumentType.BASES_INTEGRADAS

    def test_buena_pro_takes_priority_over_adjudicacion(self) -> None:
        from document_intelligence.document_pack.classifier import _merge_scores

        fname_scores = dict.fromkeys(DocumentType, 0.0)
        fname_scores[DocumentType.BUENA_PRO] = 1.0
        fname_scores[DocumentType.ADJUDICACION] = 1.0
        text_scores = dict.fromkeys(DocumentType, 0.0)

        dtype, signals = _merge_scores(fname_scores, text_scores)
        assert dtype == DocumentType.BUENA_PRO

    def test_unknown_when_no_signals(self) -> None:
        from document_intelligence.document_pack.classifier import _merge_scores

        zero = dict.fromkeys(DocumentType, 0.0)
        dtype, _ = _merge_scores(zero, zero)
        assert dtype == DocumentType.UNKNOWN

    def test_classify_document_returns_type_and_signals(self, tmp_path: Path) -> None:
        try:
            from reportlab.lib.pagesizes import LETTER
            from reportlab.pdfgen import canvas
        except ImportError:  # pragma: no cover
            pytest.skip("reportlab not installed")

        pdf = tmp_path / "bases_integradas.pdf"
        doc = canvas.Canvas(str(pdf), pagesize=LETTER)
        doc.drawString(72, 740, "BASES INTEGRADAS DEL PROCESO")
        doc.showPage()
        doc.save()

        dtype, signals = classify_document(pdf)
        assert dtype == DocumentType.BASES_INTEGRADAS
        assert "filename_signals" in signals
        assert "text_signals" in signals


def test_probe_text_returns_empty_on_parse_error(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_pdf.pdf"
    bad.write_bytes(b"not a real pdf")
    result = _probe_text(bad)
    assert result == ""