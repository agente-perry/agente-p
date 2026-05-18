"""RiskAnalysisAgent — rule-based flag detection from retrieval hits.

Converts ``RetrievalResult`` records into ``FlagCandidate`` records using
keyword-based detection patterns per flag code. Operates purely on the
retrieved text; no LLM calls, no API keys.
"""
# pyright: reportMissingTypeArgument=false, reportUnknownVariableType=false, reportUnknownMemberType=false, reportUnknownParameterType=false

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import cast

from document_intelligence.doctrine import DoctrineIndex
from document_intelligence.schemas.analysis import FlagCandidate, Severity
from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem
from document_intelligence.schemas.plan import RetrievalResult

_FLAG_DEFINITIONS: dict[str, tuple[str, str, float]] = {
    "LOW_TRACEABILITY_OUTPUT": (
        "Entregable sin dataset estructurado",
        "medium",
        0.55,
    ),
    "OBSOLETE_PHYSICAL_FORMAT": (
        "Entregable exclusivamente fisico",
        "medium",
        0.60,
    ),
    "EXCESSIVE_DOCUMENT_REQUIREMENT": (
        "Documentacion administrativa excesiva",
        "medium",
        0.55,
    ),
    "SPECIFIC_EQUIPMENT_REQUIREMENT": (
        "Especificacion de marca o modelo unico",
        "high",
        0.65,
    ),
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": (
        "Certificaciones desproporcionadas",
        "medium",
        0.50,
    ),
    "SUBJECTIVE_EVALUATION_CRITERIA": (
        "Criterios de evaluacion subjetivos",
        "high",
        0.60,
    ),
    "UNREALISTIC_DEADLINE": (
        "Plazo de presentacion atipicamente corto",
        "medium",
        0.55,
    ),
    "OVER_SPECIFIED_EXPERIENCE": (
        "Experiencia previa restrictiva",
        "high",
        0.65,
    ),
}

_EVIDENCE_PATTERNS: dict[str, tuple[re.Pattern, ...]] = {
    "LOW_TRACEABILITY_OUTPUT": (
        re.compile(r"entregable\s+(?:en\s+)?(?:sin\s+)?(?:formato\s+)?(?:estructurado|digital|maquina)", re.IGNORECASE),
        re.compile(r"no\s+se\s+exige\s+(?:ningun\s+)?(?:formato\s+)?digital", re.IGNORECASE),
        re.compile(r"sin\s+(?:dataset|base\s+de\s+datos|formato\s+estructurado)", re.IGNORECASE),
        re.compile(r"trazabilidad", re.IGNORECASE),
    ),
    "OBSOLETE_PHYSICAL_FORMAT": (
        re.compile(r"exclusivamente\s+fisico", re.IGNORECASE),
        re.compile(r"formato\s+A3", re.IGNORECASE),
        re.compile(r"presentar\s+(?:en\s+)?(?:formato\s+)?(?:impreso|fisico)", re.IGNORECASE),
        re.compile(r"ejemplar(?:es)?\s+original(?:es)?", re.IGNORECASE),
        re.compile(r"medio\s+fisico", re.IGNORECASE),
    ),
    "EXCESSIVE_DOCUMENT_REQUIREMENT": (
        re.compile(r"copias?\s+legalizada", re.IGNORECASE),
        re.compile(r"notarial", re.IGNORECASE),
        re.compile(r"fedatead", re.IGNORECASE),
        re.compile(r"foliad", re.IGNORECASE),
        re.compile(r"visado", re.IGNORECASE),
        re.compile(r"original\s+y\s+copia", re.IGNORECASE),
        re.compile(r"tres\s+juegos", re.IGNORECASE),
        re.compile(r"sobre\s+cerrado", re.IGNORECASE),
        re.compile(r"entrega\s+f[íi]sica\s+obligatoria", re.IGNORECASE),
        re.compile(r"documentos?\s+(?:f[íi]sicos?|adicionales)\s+(?:exigidos?|solicitados?|obligatorios?)", re.IGNORECASE),
        re.compile(r"lista\s+extensa\s+de\s+documentos", re.IGNORECASE),
        re.compile(r"presentar\s+(?:los\s+)?(?:siguientes\s+)?\d+\s+(?:documentos?|copias?|anexos?|formatos?|formularios?)", re.IGNORECASE),
        re.compile(r"no\s+menor\s+a\s+(?:\d+\s+)?(?:documentos?|copias?|p[áa]ginas?)", re.IGNORECASE),
        # PR #9 medium pattern (evidence: tdr_ambiente_001 p13 / tdr_ambiente_positive_001 p13).
        # Captures the notarial signature burden on consortium members. Requires the
        # "ante notari(o|al)" anchor so plain "firma digital" / "firma electronica"
        # boilerplate does not match.
        re.compile(r"firmas?\s+legalizadas?\s+ante\s+notari", re.IGNORECASE),
    ),
    "SPECIFIC_EQUIPMENT_REQUIREMENT": (
        re.compile(r"marca\s+(?:unic|exclu)", re.IGNORECASE),
        re.compile(r"modelo\s+(?:unic|especif|exclu)", re.IGNORECASE),
        re.compile(r"equipo\s+(?:de\s+)?(?:marca|modelo)\s+(?:unic|exclu)", re.IGNORECASE),
        re.compile(r"proveedor\s+(?:unic|propiet|exclu)", re.IGNORECASE),
    ),
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": (
        re.compile(r"certificacion(?:es)?\s+(?:de\s+)?(?:iso|nf|une)", re.IGNORECASE),
        re.compile(r"acreditacion(?:es)?\s+(?:de\s+)?(?:iso|nf|une)", re.IGNORECASE),
        re.compile(r"homologacion(?:es)?\s+(?:de\s+)?(?:iso|nf|une)", re.IGNORECASE),
        re.compile(r"iso\s+\d{4}", re.IGNORECASE),
    ),
    "SUBJECTIVE_EVALUATION_CRITERIA": (
        re.compile(r"juicio\s+del\s+comite", re.IGNORECASE),
        re.compile(r"criterios?\s+subjetivos?", re.IGNORECASE),
        re.compile(r"discrecional(?:es)?", re.IGNORECASE),
        re.compile(r"afinidad\s+(?:institucional|del\s+comite)", re.IGNORECASE),
    ),
    "UNREALISTIC_DEADLINE": (
        re.compile(r"plazo\s+(?:muy\s+)?(?:corto|apretado)", re.IGNORECASE),
        re.compile(r"cronograma\s+(?:muy\s+)?ajustado", re.IGNORECASE),
        re.compile(r"entrega\s+en\s+(?:\d+\s+)?dias\s+(?:habiles)?", re.IGNORECASE),
    ),
    "OVER_SPECIFIED_EXPERIENCE": (
        re.compile(r"experiencia\s+minima\s+de\s+\d+\s+an", re.IGNORECASE),
        re.compile(r"experiencia\s+minima\s+de\s+\w+\s+an", re.IGNORECASE),
        re.compile(r"experiencia\s+especifica\s+(?:de\s+)?\d+\s+an", re.IGNORECASE),
        re.compile(r"experiencia\s+especifica\s+restrictiva", re.IGNORECASE),
        re.compile(r"experiencia\s+especifica\s+del\s+mismo\s+sector", re.IGNORECASE),
        re.compile(r"monto\s+acumulado\s+minimo", re.IGNORECASE),
        re.compile(r"contratos?\s+(?:del|mismo)\s+sector\s+(?:con\s+)?(?:experiencia\s+)?(?:previa\s+)?(?:minima\s+)?(?:de\s+)?\d+", re.IGNORECASE),
        # PR #9 medium pattern (evidence: tdr_ambiente_positive_001 p52, also
        # mineria p52). Requires the structural anchor "establecida|requerida|
        # exigida|definida en las bases|el procedimiento" so plain "experiencia
        # especifica" alone never fires.
        re.compile(
            r"experiencia\s+espec[ií]fica\s+(?:establecida|requerida|exigida|definida)"
            r"\s+en\s+(?:las\s+bases|el\s+procedimiento)",
            re.IGNORECASE,
        ),
        # PR #9 medium pattern (evidence: tdr_salud_pliego_001 p206). Catches
        # "servicios iguales o similares al objeto de convocatoria" — narrow-scope
        # qualification clause. Requires the lead noun (contratos|servicios|
        # experiencia) so isolated "similar al objeto" never fires.
        re.compile(
            r"(?:contratos?|servicios?|experiencia)\s+(?:iguales?\s+o\s+)?"
            r"similares\s+al\s+objeto",
            re.IGNORECASE,
        ),
    ),
}


@dataclass(frozen=True)
class RiskAnalysisConfig:
    min_confidence: float = 0.30


class RiskAnalysisAgent:
    """Rule-based flag detection from retrieval results."""

    def __init__(
        self,
        doctrine_index: DoctrineIndex | None = None,
        config: RiskAnalysisConfig | None = None,
    ) -> None:
        self._doctrine = doctrine_index
        self._config = config or RiskAnalysisConfig()

    def analyze(self, results: list[RetrievalResult]) -> list[FlagCandidate]:
        """Convert retrieval results into flag candidates.

        Only emits a candidate when at least one evidence pattern for the
        flag code matches a hit's text excerpt.
        Uses ``doctrine_anchor_id`` from each result (if available) to look
        up the correct doctrine anchor, rather than constructing a NL query
        from the flag code string.
        """
        candidates: list[FlagCandidate] = []
        seen_quotes: set[str] = set()

        for result in results:
            flag_code = result.flag_code
            if flag_code not in _FLAG_DEFINITIONS:
                continue

            patterns = _EVIDENCE_PATTERNS.get(flag_code, ())
            flag_name, severity_str, base_confidence = _FLAG_DEFINITIONS[flag_code]

            anchor: DoctrineAnchor | None = None
            if self._doctrine is not None and result.doctrine_anchor_id:
                anchor = self._lookup_anchor_by_id(result.doctrine_anchor_id, flag_code)
            elif self._doctrine is not None:
                anchor = self._lookup_anchor_by_id(None, flag_code)

            for hit in result.hits:
                excerpt = hit.text_excerpt
                matched = any(p.search(excerpt) for p in patterns)
                if not matched:
                    continue

                quote = _extract_quote(excerpt, patterns)
                if quote in seen_quotes:
                    continue
                seen_quotes.add(quote)

                # Severity tuning (PR #10): when the matched quote is template-
                # like (no numbers, no narrowing anchors, cluster is "Otros"),
                # downgrade to ``low`` severity and reduce confidence. The flag
                # still surfaces as a pointer for human review but does not
                # inflate the aggregate score.
                effective_severity = cast("Severity", severity_str)
                effective_confidence = base_confidence
                if _is_weak_signal(flag_code, quote, hit.cluster_hint):
                    effective_severity = "low"
                    effective_confidence = min(base_confidence, 0.45)

                if effective_confidence < self._config.min_confidence:
                    continue

                candidates.append(
                    FlagCandidate(
                        flag_code=flag_code,
                        flag_name=flag_name,
                        severity=effective_severity,
                        tdr_evidence=EvidenceItem(
                            chunk_id=hit.chunk_id,
                            page_number=hit.page_start,
                            quote=quote,
                            cluster=hit.cluster_hint,
                        ),
                        explanation=_build_explanation(flag_code, quote),
                        confidence=round(effective_confidence, 2),
                        doctrine_anchor=anchor,
                    )
                )

        return _semantic_dedup(candidates)

    def _lookup_anchor_by_id(
        self,
        doctrine_anchor_id: str | None,
        flag_code: str,
    ) -> DoctrineAnchor | None:
        """Look up doctrine anchor by chunk_id; fall back to flag_code text query."""
        if self._doctrine is None:
            return None
        if doctrine_anchor_id:
            hits = self._doctrine.query_by_ids([doctrine_anchor_id])
            if hits:
                hit = hits[0]
                return DoctrineAnchor(
                    source=hit.source,
                    section=hit.section,
                    page=hit.page,
                    quote=hit.quote,
                    flag_code=flag_code,
                )
        # Preferred fallback: deterministic lookup by flag_code. This is more
        # accurate than a natural-language top-k query, especially when the
        # doctrine is in English and the user question is in Spanish.
        hit = self._doctrine.first_by_flag_code(flag_code)
        if hit is not None:
            return DoctrineAnchor(
                source=hit.source,
                section=hit.section,
                page=hit.page,
                quote=hit.quote,
                flag_code=flag_code,
            )

        # Last-resort fallback: natural-language query. Kept for backwards
        # compatibility with the stub corpus where flag_code was always set
        # and the first-match logic suffices.
        natural = flag_code.replace("_", " ").lower()
        hits = self._doctrine.query(natural, top_k=5)
        for hit in hits:
            if hit.flag_code == flag_code:
                return DoctrineAnchor(
                    source=hit.source,
                    section=hit.section,
                    page=hit.page,
                    quote=hit.quote,
                    flag_code=flag_code,
                )
        if hits:
            top = hits[0]
            return DoctrineAnchor(
                source=top.source,
                section=top.section,
                page=top.page,
                quote=top.quote,
                flag_code=flag_code,
            )
        return None


def _extract_quote(text: str, patterns: tuple[re.Pattern, ...]) -> str:
    """Return the matching line or a window around the first pattern match.

    The returned quote must be a literal substring of the source chunk so
    that ``EvidenceCriticAgent`` can verify it. The retrieval layer appends
    ``"..."`` to ``text_excerpt`` when it truncates; we strip that suffix
    here so it never becomes part of an evidence quote.
    """
    haystack = text.rstrip()
    if haystack.endswith("..."):
        haystack = haystack[:-3].rstrip()
    for pat in patterns:
        match = pat.search(haystack)
        if match:
            start = max(match.start() - 40, 0)
            end = min(match.end() + 80, len(haystack))
            return haystack[start:end].strip()
    return haystack[:150].strip()


def _normalize_for_dedup(text: str) -> str:
    """Normalize text for semantic dedup: lowercase, accent-fold, remove punctuation, collapse whitespace."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]


def _semantic_dedup(candidates: list[FlagCandidate]) -> list[FlagCandidate]:
    """Deduplicate FlagCandidates: keep one per flag_code + normalized_quote_signature group.

    When two candidates share the same flag_code and their normalized quotes have
    Jaccard similarity >= 0.7, keep only the one with higher confidence.
    Uses a greedy merge strategy: scan in descending confidence order and
    suppress any later candidate whose normalized quote is within threshold.
    """
    if not candidates:
        return []
    sorted_candidates = sorted(candidates, key=lambda c: c.confidence, reverse=True)
    kept: list[FlagCandidate] = []
    for candidate in sorted_candidates:
        sig = _normalize_for_dedup(candidate.tdr_evidence.quote)
        suppressed = False
        for kept_candidate in kept:
            if kept_candidate.flag_code != candidate.flag_code:
                continue
            kept_sig = _normalize_for_dedup(kept_candidate.tdr_evidence.quote)
            if _jaccard(sig, kept_sig) >= 0.7:
                suppressed = True
                break
        if not suppressed:
            kept.append(candidate)
    return kept


def _jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity between two whitespace-tokenized strings."""
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _build_explanation(flag_code: str, quote: str) -> str:
    explanations: dict[str, str] = {
        "LOW_TRACEABILITY_OUTPUT": (
            "El documento no exige un entregable estructurado o trazable. "
            "La ausencia de datasets, formatos digitales o registros "
            "maquina-legibles reduce la capacidad de supervision ciudadana."
        ),
        "OBSOLETE_PHYSICAL_FORMAT": (
            "Se requiere entrega exclusivamente fisica o impresa, sin "
            "contraparte digital. Esto limita la trazabilidad y el acceso "
            "publico a los resultados del contrato."
        ),
        "EXCESSIVE_DOCUMENT_REQUIREMENT": (
            "La cantidad de documentos administrativos exigidos es "
            "alta en relacion al objeto del servicio, lo que puede "
            "desincentivar la participacion de postores pequenos."
        ),
        "SPECIFIC_EQUIPMENT_REQUIREMENT": (
            "Se especifica una marca, modelo o equipo unico sin clausula "
            "de equivalente. Esto restringe la competencia y puede "
            "favorecer a un proveedor predeterminado."
        ),
        "EXCESSIVE_CERTIFICATION_REQUIREMENT": (
            "Las certificaciones exigidas parecen desproporcionadas para "
            "el valor y alcance del contrato, creando barreras de entrada "
            "artificiales."
        ),
        "SUBJECTIVE_EVALUATION_CRITERIA": (
            "Los criterios de evaluacion dependen del juicio del comite "
            "sin rubricas medibles ni pesos definidos, lo que permite "
            "decisiones discrecionales en la adjudicacion."
        ),
        "UNREALISTIC_DEADLINE": (
            "El plazo de presentacion de ofertas es atipicamente corto, "
            "lo que puede excluir postores que requieran mas tiempo para "
            "preparar una propuesta competitiva."
        ),
        "OVER_SPECIFIED_EXPERIENCE": (
            "Los requisitos de experiencia parecen disenados a la medida "
            "de un proveedor historico especifico, reduciendo el numero "
            "de postores habilitados."
        ),
    }
    explanation = explanations.get(flag_code, "Senal detectada en el texto del documento.")
    return f"{explanation} Texto de referencia: \"{quote[:200]}\""

# Patterns of "narrowing anchors" — when one of these appears near the matched
# regex, the signal is treated as strong (real number, restrictive condition,
# specific scope, equivalent banned, etc.). Otherwise the candidate is treated
# as a weak/template pointer and downgraded to ``severity="low"``.
_NARROWING_ANCHORS_BY_FLAG: dict[str, tuple[re.Pattern[str], ...]] = {
    "OVER_SPECIFIED_EXPERIENCE": (
        # Year anchors — covers:
        #   "8 anios" / "10 años"
        #   "8 (ocho) anios" / "10 (diez) años"
        #   "(08) anios" / "(5) años"
        #   "anios (08)" / "años (5)"
        re.compile(
            r"\b\d+\s*(?:\([^)]{1,24}\))?\s*(?:an[oó]s?|a[nñ]os?|anios?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\(\s*\d+\s*\)\s*(?:an[oó]s?|a[nñ]os?|anios?)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:an[oó]s?|a[nñ]os?|anios?)\s*\(\s*\d+\s*\)",
            re.IGNORECASE,
        ),
        re.compile(r"monto\s+(?:acumulado|m[ií]nimo|no\s+menor)", re.IGNORECASE),
        re.compile(r"S/\s*[\d.,]+", re.IGNORECASE),
        re.compile(r"objeto\s+similar(?:es)?", re.IGNORECASE),
        re.compile(r"similar(?:es)?\s+al\s+objeto", re.IGNORECASE),
        re.compile(r"mismo\s+sector", re.IGNORECASE),
        re.compile(r"restrictiv", re.IGNORECASE),
        re.compile(r"sin\s+equivalente", re.IGNORECASE),
    ),
    "EXCESSIVE_DOCUMENT_REQUIREMENT": (
        re.compile(r"\b\d+\s+(?:documentos?|copias?|p[áa]ginas?|anexos?|formularios?)\b", re.IGNORECASE),
        re.compile(r"tres\s+juegos", re.IGNORECASE),
        re.compile(r"sobre\s+cerrado", re.IGNORECASE),
        re.compile(r"original\s+y\s+copia", re.IGNORECASE),
        re.compile(r"obligatori", re.IGNORECASE),
    ),
}

# Cluster labels that indicate the chunk is NOT in a meaningful section
# (boilerplate, footers, generic "Otros"). When the match lands here AND no
# narrowing anchor is present, the signal is considered weak.
_NEUTRAL_CLUSTERS: frozenset[str] = frozenset({
    "Otros",
    "Confidencialidad y propiedad",
    "",
})


def _is_weak_signal(flag_code: str, quote: str, cluster_hint: str | None) -> bool:
    """True when the quote looks like template boilerplate.

    A weak signal is one where the regex matched but:

    - the chunk's cluster is neutral (``Otros`` or similar), AND
    - the quote does NOT contain any of the flag's narrowing anchors
      (concrete number of years, monto, "del mismo sector", etc.).

    Such candidates are kept (they may be useful pointers for human review)
    but downgraded to ``severity="low"`` so they do not inflate the aggregate
    score in PR #10's scoring layer.
    """
    cluster = cluster_hint or ""
    if cluster not in _NEUTRAL_CLUSTERS:
        return False
    anchors = _NARROWING_ANCHORS_BY_FLAG.get(flag_code, ())
    if not anchors:
        return False
    if any(pat.search(quote) for pat in anchors):
        return False
    return True


# Re-export for tests.
__all__ = [
    "RiskAnalysisAgent",
    "RiskAnalysisConfig",
]
