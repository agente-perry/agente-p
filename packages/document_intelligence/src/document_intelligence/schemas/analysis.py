"""Final analysis output schema and intermediate risk/critique schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

Severity = Literal["low", "medium", "high"]
Confidence = Literal["low", "medium", "high"]


class FlagRecord(BaseModel):
    """A red flag emitted with mandatory dual evidence."""

    model_config = ConfigDict(extra="forbid")

    flag_code: str
    flag_name: str
    severity: Severity
    tdr_evidence: EvidenceItem
    doctrine_anchor: DoctrineAnchor
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class FlagCandidate(BaseModel):
    """Intermediate flag representation before full evidence critique.

    ``doctrine_anchor`` is optional at this stage — the EvidenceCriticAgent
    will enforce dual evidence where required.
    """

    model_config = ConfigDict(extra="forbid")

    flag_code: str
    flag_name: str
    severity: Severity
    tdr_evidence: EvidenceItem
    doctrine_anchor: DoctrineAnchor | None = None
    explanation: str
    confidence: float = Field(ge=0.0, le=1.0)


class CriticCritique(BaseModel):
    """Output of the EvidenceCriticAgent.

    ``needs_replan`` is set to True when all candidates were rejected, signaling
    the orchestrator to retry with a reformed plan (max 1 retry per spec).
    ``rejected`` holds the original ``FlagCandidate`` objects (not promoted to
    ``FlagRecord``) so downstream consumers cannot treat rejected flags as valid.
    """

    model_config = ConfigDict(extra="forbid")

    accepted: list[FlagRecord] = Field(default_factory=lambda: [])
    rejected: list[FlagCandidate] = Field(default_factory=lambda: [])
    summary: str = ""
    needs_replan: bool = Field(
        default=False,
        description="True when all candidates were rejected and a retry with a reformed plan should be attempted.",
    )
    reject_reasons: list[str] = Field(
        default_factory=lambda: [],
        description=(
            "Parallel to ``rejected``: per-candidate reason string explaining why "
            "the EvidenceCriticAgent dropped the flag (e.g. 'quote no encontrado "
            "literalmente'). Internal diagnostic — never shown to end users."
        ),
    )


class ScoreBreakdown(BaseModel):
    """Per-component contribution to the aggregate risk score.

    Debug-only field. The aggregate score is **not** used for any automatic
    decision in PR #10; it only documents how the system would compute the
    GraphRAG activation gate when Fase 3 lands.
    """

    model_config = ConfigDict(extra="forbid")

    flag_low_points: int = 0
    flag_medium_points: int = 0
    flag_high_points: int = 0
    doctrine_anchor_points: int = 0
    evidence_quote_points: int = 0
    primary_key_points: int = 0


class GraphRAGActivation(BaseModel):
    """Debug-only audit of whether GraphRAG *would* be activated.

    PR #10 only computes this; it never triggers GraphRAG. The field exists
    so the team can verify the activation gate against real documents.
    """

    model_config = ConfigDict(extra="forbid")

    activation: bool = False
    threshold: int = 75
    blockers: list[str] = Field(default_factory=lambda: [])


class AnalysisResult(BaseModel):
    """Top-level orchestrator output."""

    model_config = ConfigDict(extra="forbid")

    document: str
    question: str
    clusters_inspected: list[str] = Field(default_factory=lambda: [])
    flags: list[FlagRecord] = Field(default_factory=lambda: [])
    summary: str = ""
    questions_for_authority: list[str] = Field(default_factory=lambda: [])
    missing_data: list[str] = Field(default_factory=lambda: [])
    confidence: Confidence = "low"
    disclaimer: str = (
        "Este analisis no constituye acusacion. Identifica senales con evidencia textual "
        "que requieren revision humana."
    )
    score: int = Field(
        default=0,
        ge=0,
        le=100,
        description=(
            "Debug-only aggregate risk score (0-100). Not used to take any "
            "automatic decision in PR #10. Documents how Fase 3 would gate "
            "GraphRAG activation."
        ),
    )
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    graph_rag: GraphRAGActivation = Field(default_factory=GraphRAGActivation)
    pack_id: str | None = Field(
        default=None,
        description="ProcessDocumentPack pack_id when analysis was run on a document pack.",
    )
    pack_mode: str | None = Field(
        default=None,
        description="Mode of the pack: preventive | investigative | unknown.",
    )
    document_type: str | None = Field(
        default=None,
        description="Heuristic document type from classifier (tdr, bases, buena_pro, etc.).",
    )
