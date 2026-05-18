"""PR #10 aggregate score (debug-only)."""

from __future__ import annotations

from document_intelligence.agents.score import (
    ScoringContext,
    apply_score,
    compute_score,
)
from document_intelligence.schemas.analysis import (
    AnalysisResult,
    FlagRecord,
)
from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem


def _flag(
    severity: str = "medium",
    confidence: float = 0.6,
    doctrine_source: str = "OCP Red Flags",
    doctrine_quote: str = "lorem",
    quote: str = "evidence",
    page: int = 5,
) -> FlagRecord:
    return FlagRecord(
        flag_code="OVER_SPECIFIED_EXPERIENCE",
        flag_name="X",
        severity=severity,  # type: ignore[arg-type]
        tdr_evidence=EvidenceItem(chunk_id="c1", page_number=page, quote=quote),
        doctrine_anchor=DoctrineAnchor(source=doctrine_source, quote=doctrine_quote),
        explanation="e",
        confidence=confidence,
    )


def test_score_zero_when_no_flags() -> None:
    score, breakdown, activation = compute_score([])
    assert score == 0
    assert breakdown.flag_low_points == 0
    assert breakdown.flag_medium_points == 0
    assert breakdown.flag_high_points == 0
    assert activation.activation is False
    assert "no_accepted_flags" in activation.blockers


def test_score_single_medium_flag_with_evidence_and_doctrine() -> None:
    flags = [_flag(severity="medium")]
    score, breakdown, activation = compute_score(flags)
    # 20 (medium) + 15 (doctrine) + 15 (evidence) = 50
    assert score == 50
    assert breakdown.flag_medium_points == 20
    assert breakdown.doctrine_anchor_points == 15
    assert breakdown.evidence_quote_points == 15
    assert breakdown.primary_key_points == 0
    assert activation.activation is False
    assert "no_primary_key" in activation.blockers


def test_score_high_flag_with_full_context_activates() -> None:
    flags = [_flag(severity="high"), _flag(severity="high"), _flag(severity="medium")]
    ctx = ScoringContext(supplier_ruc="20100904315")
    score, breakdown, activation = compute_score(flags, ctx)
    # 30 + 30 + 20 + 15 + 15 + 10 = 120 → capped at 100
    assert score == 100
    assert breakdown.flag_high_points == 60
    assert breakdown.flag_medium_points == 20
    assert breakdown.primary_key_points == 10
    assert activation.activation is True
    assert activation.blockers == []


def test_score_low_flags_only_below_threshold() -> None:
    flags = [_flag(severity="low"), _flag(severity="low")]
    ctx = ScoringContext(supplier_ruc="20100904315")
    score, _breakdown, activation = compute_score(flags, ctx)
    # 10 + 10 + 15 + 15 + 10 = 60 — under 75
    assert score == 60
    assert activation.activation is False
    assert activation.blockers == []  # no blockers, only below threshold


def test_score_missing_doctrine_anchor_blocks_activation() -> None:
    flags = [_flag(severity="high", doctrine_source="  ", doctrine_quote="  ")]
    ctx = ScoringContext(supplier_ruc="20100904315")
    score, breakdown, activation = compute_score(flags, ctx)
    assert breakdown.doctrine_anchor_points == 0
    assert "no_doctrine_anchor" in activation.blockers
    assert activation.activation is False


def test_score_missing_evidence_blocks_activation() -> None:
    flags = [_flag(severity="high", quote="   ")]
    ctx = ScoringContext(supplier_ruc="20100904315")
    _score, breakdown, activation = compute_score(flags, ctx)
    assert breakdown.evidence_quote_points == 0
    assert "no_evidence_quote" in activation.blockers
    assert activation.activation is False


def test_score_threshold_exactly_75_activates_when_clean() -> None:
    # 30 (high) + 20 (medium) + 15 + 15 - 5 = 75 — need exactly 75
    # 30 + 20 + 15 + 15 = 80 already, plus PK = 90. Tweak: only severities.
    flags = [_flag(severity="medium"), _flag(severity="medium")]
    ctx = ScoringContext(supplier_ruc="20100904315")
    score, _b, activation = compute_score(flags, ctx)
    # 20 + 20 + 15 + 15 + 10 = 80
    assert score == 80
    assert activation.activation is True


def test_apply_score_returns_copy_with_fields_populated() -> None:
    result = AnalysisResult(
        document="x.pdf",
        question="q",
        flags=[_flag(severity="high")],
        confidence="medium",
    )
    enriched = apply_score(result, ScoringContext(ocid="ocds-x"))
    assert enriched is not result  # model_copy returns new instance
    assert enriched.score > 0
    assert enriched.graph_rag.threshold == 75
    assert "no_primary_key" not in enriched.graph_rag.blockers


def test_apply_score_no_flags_zero_score() -> None:
    result = AnalysisResult(document="x.pdf", question="q", flags=[])
    enriched = apply_score(result)
    assert enriched.score == 0
    assert enriched.graph_rag.activation is False
    assert "no_accepted_flags" in enriched.graph_rag.blockers


def test_scoring_context_has_primary_key_detection() -> None:
    assert ScoringContext().has_primary_key is False
    assert ScoringContext(supplier_ruc="20100904315").has_primary_key is True
    assert ScoringContext(entity_ruc="20131370645").has_primary_key is True
    assert ScoringContext(ocid="ocds-x").has_primary_key is True


def test_graph_rag_never_activates_without_primary_key() -> None:
    """Hard invariant: even with 100 score, no primary key → no activation."""
    flags = [_flag(severity="high"), _flag(severity="high"), _flag(severity="high")]
    score, _b, activation = compute_score(flags, ScoringContext())  # no keys
    assert score >= 75
    assert activation.activation is False
    assert "no_primary_key" in activation.blockers
