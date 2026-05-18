"""ModeStrategy — maps :class:`PackMode` to per-analysis configuration knobs.

Architecture
============
The strategy is a simple dataclass that holds the configuration knobs that
should differ between ``preventive`` (pre-adjudication, TDR/bases only) and
``investigative`` (post-adjudication, includes winner/contract) modes.

The ``resolve_strategy`` factory is the single source of truth — no if/else
scattered through the orchestrator.  Call it once at the start of
``PackOrchestrator.analyze()`` and pass the resolved strategy to the
``AgentOrchestrator`` per document.
"""

from __future__ import annotations

from dataclasses import dataclass

from document_intelligence.document_pack.schemas import PackMode


@dataclass
class PackAnalysisStrategy:
    """Configuration knobs that vary by pack mode.

    Attributes
    ----------
    mode:
        The source pack mode this strategy is derived from.
    retriever_top_k:
        Number of retrieval candidates to pass to the PlannerAgent.
        Higher in investigative mode → more candidates to cross-reference.
    planner_doctrine_top_k:
        Number of doctrine chunks to retrieve for flag calibration.
    max_retries:
        Maximum retries when the PlannerAgent requests re-planning.
        Investigative mode benefits from one extra retry to catch
        weak signals in winner/contract documents.
    require_dual_evidence:
        Require two corroborating sources before accepting a flag.
        Preventive mode is stricter (fewer false positives).
    evidence_threshold:
        Minimum evidence weight (0–1) to accept a flag without retry.
        Lower in investigative mode → surface more signals.
    risk_weight_profile:
        Named profile for how aggressively to weight risk signals.
        ``conservative`` → preventive; ``exploratory`` → investigative.
    """

    mode: PackMode
    retriever_top_k: int = 5
    planner_doctrine_top_k: int = 10
    max_retries: int = 1
    require_dual_evidence: bool = True
    evidence_threshold: float = 0.5
    risk_weight_profile: str = "conservative"

    def to_config_dict(self) -> dict[str, object]:
        return {
            "retriever_top_k": self.retriever_top_k,
            "planner_doctrine_top_k": self.planner_doctrine_top_k,
            "max_retries": self.max_retries,
            "require_dual_evidence": self.require_dual_evidence,
            "evidence_threshold": self.evidence_threshold,
            "risk_weight_profile": self.risk_weight_profile,
        }


_PREVENTIVE_STRATEGY = PackAnalysisStrategy(
    mode=PackMode.PREVENTIVE,
    retriever_top_k=5,
    planner_doctrine_top_k=10,
    max_retries=1,
    require_dual_evidence=True,
    evidence_threshold=0.6,
    risk_weight_profile="conservative",
)

_INVESTIGATIVE_STRATEGY = PackAnalysisStrategy(
    mode=PackMode.INVESTIGATIVE,
    retriever_top_k=8,
    planner_doctrine_top_k=15,
    max_retries=2,
    require_dual_evidence=False,
    evidence_threshold=0.4,
    risk_weight_profile="exploratory",
)

_UNKNOWN_STRATEGY = PackAnalysisStrategy(
    mode=PackMode.UNKNOWN,
    retriever_top_k=5,
    planner_doctrine_top_k=10,
    max_retries=1,
    require_dual_evidence=True,
    evidence_threshold=0.5,
    risk_weight_profile="conservative",
)


def resolve_strategy(pack_mode: PackMode) -> PackAnalysisStrategy:
    """Return the :class:`PackAnalysisStrategy` for the given pack mode.

    This is the single entry point — call it once per ``analyze()`` run.
    """
    if pack_mode == PackMode.PREVENTIVE:
        return _PREVENTIVE_STRATEGY
    if pack_mode == PackMode.INVESTIGATIVE:
        return _INVESTIGATIVE_STRATEGY
    return _UNKNOWN_STRATEGY