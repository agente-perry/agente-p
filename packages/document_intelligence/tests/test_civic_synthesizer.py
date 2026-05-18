"""CivicSynthesizerAgent: legal-safe citizen-facing output generation."""

from __future__ import annotations

from document_intelligence.agents.civic_synthesizer import CivicSynthesizerAgent
from document_intelligence.schemas.analysis import FlagRecord
from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem


def _flag(
    flag_code: str = "OBSOLETE_PHYSICAL_FORMAT",
    flag_name: str = "Entregable exclusivamente fisico",
    severity: str = "medium",
    confidence: float = 0.6,
    page: int = 3,
) -> FlagRecord:
    return FlagRecord(
        flag_code=flag_code,
        flag_name=flag_name,
        severity=severity,
        tdr_evidence=EvidenceItem(
            chunk_id="chunk001",
            page_number=page,
            quote="debera presentarse impreso en formato A3",
            cluster="Entregables",
        ),
        doctrine_anchor=DoctrineAnchor(
            source="OCP Red Flags Guide (stub paraphrase)",
            section="Implementation phase",
            page=48,
            quote="Outputs required exclusively in printed form.",
            flag_code=flag_code,
        ),
        explanation="Test explanation.",
        confidence=confidence,
    )


def test_synthesizer_produces_analysis_result() -> None:
    flags = [_flag()]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(
        document="test.pdf",
        question="Hay senales de riesgo?",
        clusters_inspected=["Entregables"],
        flags=flags,
    )
    assert result.document == "test.pdf"
    assert result.question == "Hay senales de riesgo?"
    assert len(result.flags) == 1
    assert result.flags[0].flag_code == "OBSOLETE_PHYSICAL_FORMAT"


def test_synthesizer_includes_disclaimer() -> None:
    flags = [_flag()]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert "acusacion" in result.disclaimer.lower()
    assert "senales" in result.disclaimer.lower()


def test_synthesizer_generates_questions() -> None:
    flags = [_flag(flag_code="OBSOLETE_PHYSICAL_FORMAT")]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert result.questions_for_authority
    assert any("fisica" in q.lower() or "fisico" in q.lower() for q in result.questions_for_authority)


def test_synthesizer_returns_empty_when_no_flags() -> None:
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=[])
    assert len(result.flags) == 0
    assert result.confidence == "low"
    assert result.missing_data


def test_synthesizer_no_banned_language() -> None:
    forbidden = ["corrupto", "fraude", "culpable", "ilegal", "delito"]
    flags = [_flag()]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    combined = result.summary + " " + " ".join(result.questions_for_authority)
    combined_lower = combined.lower()
    for term in forbidden:
        assert term not in combined_lower


def test_synthesizer_computes_medium_confidence() -> None:
    flags = [_flag(confidence=0.5)]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert result.confidence == "medium"


def test_synthesizer_computes_high_confidence() -> None:
    flags = [_flag(confidence=0.7)]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert result.confidence == "high"


def test_synthesizer_does_not_exceed_max_questions() -> None:
    flags = [
        _flag(flag_code=code)
        for code in [
            "OBSOLETE_PHYSICAL_FORMAT",
            "LOW_TRACEABILITY_OUTPUT",
            "SUBJECTIVE_EVALUATION_CRITERIA",
        ]
    ]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert len(result.questions_for_authority) <= 5


def test_synthesizer_generates_risk_explanation() -> None:
    flags = [_flag(flag_code="LOW_TRACEABILITY_OUTPUT", flag_name="Entregable sin dataset estructurado")]
    agent = CivicSynthesizerAgent()
    result = agent.synthesize(flags=flags)
    assert "LOW_TRACEABILITY_OUTPUT" in result.summary