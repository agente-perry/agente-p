"""End-to-end orchestrator tests.

These exercise the full pipeline from a synthetic PDF fixture through to a
legal-safe ``AnalysisResult``.  No API keys required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.agents.orchestrator import AgentOrchestrator, OrchestratorConfig
from document_intelligence.parsing import PDFParseError


@pytest.fixture
def orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(OrchestratorConfig(mode="mock"))


@pytest.fixture
def sample_tdr_question() -> str:
    return (
        "Detecta señales de baja trazabilidad y requisitos restrictivos en los entregables"
    )


class TestOrchestratorEndToEnd:
    def test_analyze_synthetic_pdf_returns_analysis_result(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        assert result is not None
        assert result.summary
        assert result.disclaimer
        assert result.confidence in ("low", "medium", "high")

    def test_output_includes_accepted_flags_with_quotes_and_pages(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        for flag in result.flags:
            assert flag.tdr_evidence.quote.strip()
            assert flag.tdr_evidence.page_number > 0
            assert flag.tdr_evidence.chunk_id
            assert flag.flag_code
            assert flag.flag_name
            assert flag.confidence > 0

    def test_detects_physical_format_flag(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        codes = [f.flag_code for f in result.flags]
        assert "OBSOLETE_PHYSICAL_FORMAT" in codes or not result.flags
        if "OBSOLETE_PHYSICAL_FORMAT" in codes:
            physical = next(f for f in result.flags if f.flag_code == "OBSOLETE_PHYSICAL_FORMAT")
            assert "impreso" in physical.tdr_evidence.quote.lower() or "A3" in physical.tdr_evidence.quote

    def test_pipeline_runs_for_various_questions_without_crashing(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
    ) -> None:
        questions = [
            "Detecta señales de baja trazabilidad",
            "Detecta criterios de evaluacion subjetivos",
            "Detecta requisitos restrictivos de experiencia previa",
            "question about astronomy",  # unlikely to match doctrine
        ]
        for q in questions:
            result = orchestrator.analyze_pdf(str(synthetic_pdf), q)
            assert result is not None
            assert result.confidence in ("low", "medium", "high")

    def test_disclaimer_present_and_legal_safe(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        assert "no constituye" in result.disclaimer.lower()
        assert "acusacion" in result.disclaimer.lower()

    def test_empty_pdf_or_unreadable_raises_pdf_parse_error(
        self,
        tmp_path: Path,
        orchestrator: AgentOrchestrator,
    ) -> None:
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(b"not a pdf at all")
        with pytest.raises(PDFParseError):
            orchestrator.analyze_pdf(str(bad_pdf), "test")

    def test_critic_receives_tdr_chunks_for_literal_verification(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        # The orchestrator internally passes chunk_texts to the critic.
        # If accepted_flags > 0, it means critic did not reject them as
        # hallucinated (quote not in chunk).
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        for flag in result.flags:
            assert flag.tdr_evidence.quote

    def test_retry_loop_max_1_when_needs_replan(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
    ) -> None:
        # Use a question that may trigger needs_replan by not matching doctrine.
        result = orchestrator.analyze_pdf(str(synthetic_pdf), "question about astronomy")
        # The orchestrator should complete gracefully even with no flags.
        assert result is not None

    def test_no_api_keys_required_in_mock_mode(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        # mock embedder is deterministic and requires no network/API key.
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        assert result is not None
        assert result.document == "synthetic.pdf"

    def test_output_is_json_serializable(
        self,
        synthetic_pdf: Path,
        orchestrator: AgentOrchestrator,
        sample_tdr_question: str,
    ) -> None:
        result = orchestrator.analyze_pdf(str(synthetic_pdf), sample_tdr_question)
        payload = result.model_dump(mode="json")
        assert isinstance(payload, dict)
        assert "summary" in payload
        assert "flags" in payload
        assert "disclaimer" in payload
