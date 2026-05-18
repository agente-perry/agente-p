"""Debug-only aggregate risk score (PR #10).

This module computes ``ScoreBreakdown`` and ``GraphRAGActivation`` for an
``AnalysisResult``. **It never triggers GraphRAG**. Computation only.

Formula (initial, simple; will be refined when Fase 3 lands):

    flag low      → +10
    flag medium   → +20
    flag high     → +30
    doctrine_anchor present per accepted flag → +15 (capped 1× per result)
    evidence_quote with page per accepted flag → +15 (capped 1× per result)
    primary key available (supplier_ruc or entity_ruc or ocid) → +10

Capped at 100. Activation gate fires only when:

- score >= 75, AND
- at least one accepted flag, AND
- no blockers (no anchor / no quote / no primary key).
"""

from __future__ import annotations

from dataclasses import dataclass

from document_intelligence.schemas.analysis import (
    AnalysisResult,
    FlagRecord,
    GraphRAGActivation,
    ScoreBreakdown,
)

_LOW_POINTS = 10
_MEDIUM_POINTS = 20
_HIGH_POINTS = 30
_DOCTRINE_BONUS = 15
_EVIDENCE_BONUS = 15
_PRIMARY_KEY_BONUS = 10
_ACTIVATION_THRESHOLD = 75
_MAX_SCORE = 100


@dataclass(frozen=True)
class ScoringContext:
    """Primary keys available alongside the analysis (modo investigativo)."""

    supplier_ruc: str | None = None
    entity_ruc: str | None = None
    ocid: str | None = None

    @property
    def has_primary_key(self) -> bool:
        return bool(self.supplier_ruc or self.entity_ruc or self.ocid)


def _points_for_severity(flag: FlagRecord) -> tuple[int, str]:
    if flag.severity == "high":
        return _HIGH_POINTS, "high"
    if flag.severity == "medium":
        return _MEDIUM_POINTS, "medium"
    return _LOW_POINTS, "low"


def compute_score(
    flags: list[FlagRecord],
    context: ScoringContext | None = None,
) -> tuple[int, ScoreBreakdown, GraphRAGActivation]:
    """Compute aggregate score + breakdown + activation gate.

    GraphRAG is **never triggered** by this function; the activation field is
    a debug-only audit so the team can verify the gate.
    """
    ctx = context or ScoringContext()
    breakdown = ScoreBreakdown()
    blockers: list[str] = []

    if not flags:
        blockers.append("no_accepted_flags")
        return 0, breakdown, GraphRAGActivation(
            activation=False,
            threshold=_ACTIVATION_THRESHOLD,
            blockers=blockers,
        )

    breakdown_data: dict[str, int] = {
        "flag_low_points": 0,
        "flag_medium_points": 0,
        "flag_high_points": 0,
        "doctrine_anchor_points": 0,
        "evidence_quote_points": 0,
        "primary_key_points": 0,
    }

    has_doctrine_anchor = False
    has_evidence_quote = False
    for flag in flags:
        points, bucket = _points_for_severity(flag)
        breakdown_data[f"flag_{bucket}_points"] += points
        if flag.doctrine_anchor.source.strip() and flag.doctrine_anchor.quote.strip():
            has_doctrine_anchor = True
        if flag.tdr_evidence.quote.strip() and flag.tdr_evidence.page_number >= 1:
            has_evidence_quote = True

    if has_doctrine_anchor:
        breakdown_data["doctrine_anchor_points"] = _DOCTRINE_BONUS
    else:
        blockers.append("no_doctrine_anchor")

    if has_evidence_quote:
        breakdown_data["evidence_quote_points"] = _EVIDENCE_BONUS
    else:
        blockers.append("no_evidence_quote")

    if ctx.has_primary_key:
        breakdown_data["primary_key_points"] = _PRIMARY_KEY_BONUS
    else:
        blockers.append("no_primary_key")

    raw_score = sum(breakdown_data.values())
    score = min(raw_score, _MAX_SCORE)

    breakdown = ScoreBreakdown(**breakdown_data)
    activation = GraphRAGActivation(
        activation=(score >= _ACTIVATION_THRESHOLD and not blockers),
        threshold=_ACTIVATION_THRESHOLD,
        blockers=blockers,
    )
    return score, breakdown, activation


def apply_score(
    result: AnalysisResult,
    context: ScoringContext | None = None,
) -> AnalysisResult:
    """Return a copy of ``result`` with score/breakdown/graph_rag populated."""
    score, breakdown, activation = compute_score(list(result.flags), context)
    return result.model_copy(
        update={
            "score": score,
            "score_breakdown": breakdown,
            "graph_rag": activation,
        }
    )
