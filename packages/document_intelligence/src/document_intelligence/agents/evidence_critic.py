"""EvidenceCriticAgent — validates that every flag is backed by literal evidence.

Gate that enforces the dual-evidence principle: each flag must carry a
verbatim quote from the TDR (anti-hallucination guard), a page number,
a valid chunk reference, and (in full mode) a doctrine anchor.
Flags that fail any check are rejected with a reason.

The critique() method accepts an optional tdr_chunks map so it can verify
that the claimed quote appears literally in the source document. This is the
anti-hallucination guard required by spec invariant #3:
  assert flag.tdr_evidence.quote in tdr_chunks_text
"""

from __future__ import annotations

from dataclasses import dataclass

from document_intelligence.schemas.analysis import CriticCritique, FlagCandidate, FlagRecord
from document_intelligence.schemas.evidence import DoctrineAnchor


@dataclass(frozen=True)
class CriticConfig:
    require_dual_evidence: bool = True
    min_confidence: float = 0.20


class EvidenceCriticAgent:
    """Validate flag candidates against evidence criteria."""

    def __init__(self, config: CriticConfig | None = None) -> None:
        self._config = config or CriticConfig()

    def critique(
        self,
        candidates: list[FlagCandidate],
        tdr_chunks: dict[str, str] | None = None,
    ) -> CriticCritique:
        """Evaluate flag candidates.

        Parameters
        ----------
        candidates:
            List of FlagCandidate produced by RiskAnalysisAgent.
        tdr_chunks:
            Optional map of chunk_id -> full chunk text. When provided, each
            candidate's tdr_evidence.quote is checked for literal presence
            in the corresponding chunk (anti-hallucination guard, spec #3).

        Returns
        -------
        CriticCritique with accepted FlagRecord[] and rejected FlagCandidate[].
        ``needs_replan`` is True when all candidates were rejected so the
        orchestrator can retry with a reformed plan.
        """
        accepted: list[FlagRecord] = []
        rejected: list[FlagCandidate] = []
        reasons: list[str] = []

        for cand in candidates:
            reason = self._validate(cand, tdr_chunks)
            if reason:
                rejected.append(cand)
                reasons.append(f"{cand.flag_code}: {reason}")
            else:
                accepted.append(self._to_flag_record(cand))

        if accepted:
            summary = f"{len(accepted)} flags aceptadas."
        elif rejected:
            summary = f"{len(rejected)} flags rechazadas; se requiere reformular el plan de busqueda."
        else:
            summary = "Sin candidatos que evaluar."

        needs_replan = len(rejected) == len(candidates) and len(candidates) > 0

        return CriticCritique(
            accepted=accepted,
            rejected=rejected,
            summary=summary,
            needs_replan=needs_replan,
            reject_reasons=reasons,
        )

    def _validate(
        self,
        cand: FlagCandidate,
        tdr_chunks: dict[str, str] | None,
    ) -> str | None:
        te = cand.tdr_evidence

        if not te.quote.strip():
            return "evidence_quote vacio"

        if te.page_number < 1:
            return "sin numero de pagina valido"

        if not te.chunk_id:
            return "sin chunk_id"

        if tdr_chunks is not None and te.chunk_id in tdr_chunks:
            chunk_text = tdr_chunks[te.chunk_id]
            if te.quote not in chunk_text:
                return "quote no encontrado literalmente en el chunk del TDR (posible alucinacion)"

        if self._config.require_dual_evidence:
            da: DoctrineAnchor | None = cand.doctrine_anchor
            if da is None:
                return "sin doctrine_anchor — modo dual evidence requiere ambas citas"
            if not da.quote.strip():
                return "doctrine_anchor.quote vacio"
            if not da.source.strip():
                return "doctrine_anchor.source vacio"

        if cand.confidence < self._config.min_confidence:
            return f"confianza ({cand.confidence}) por debajo del minimo ({self._config.min_confidence})"

        return None

    @staticmethod
    def _to_flag_record(cand: FlagCandidate) -> FlagRecord:
        safe_anchor: DoctrineAnchor = (
            cand.doctrine_anchor
            if cand.doctrine_anchor is not None
            else DoctrineAnchor(
                source="No disponible",
                quote="No se encontro un ancla doctrinal para esta flag.",
            )
        )
        return FlagRecord(
            flag_code=cand.flag_code,
            flag_name=cand.flag_name,
            severity=cand.severity,
            tdr_evidence=cand.tdr_evidence,
            doctrine_anchor=safe_anchor,
            explanation=cand.explanation,
            confidence=cand.confidence,
        )
