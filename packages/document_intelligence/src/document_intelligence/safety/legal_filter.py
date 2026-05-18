"""LegalSafetyFilter — final gate that rejects or sanitises banned vocabulary.

This is the last line of defence before any text reaches the user. It scans
for terms that could be interpreted as accusatory or defamatory and either
rejects the output outright or replaces them with legal-safe alternatives.

Anti-bypass measures
--------------------
- Accent-folding: ``normalize()`` (NFKD + strip combining chars + uppercase)
  converts ``corrupción`` → ``CORRUPCION``, ``fraude`` → ``FRAUDE``.
- Stem-aware matching: pattern matches the normalized stem at a word boundary
  followed by optional trailing letters, catching plurals and conjugations
  (``corruptos``, ``delincuentes``, ``fraudes``).
- All fields scanned: summary, questions, flag_name, explanation, quote.

Invariant: legal-safe vocabulary is enforced at every stage before PR #4
adds the orchestrator retry loop (CRIT -->|retry x1| PLAN).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from re import Pattern
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from document_intelligence.agents._canonical import normalize
from document_intelligence.schemas.analysis import AnalysisResult

FilterMode = Literal["reject", "sanitize", "flag"]
_PatternPair = tuple[Pattern[str], str]

_BANNED_TERMS: dict[str, str | None] = {
    "corrupto": None,
    "corrupcion comprobada": None,
    "corrupcion": None,
    "fraude": None,
    "fraudulento": None,
    "ilegal": None,
    "ilegalidad": None,
    "delito": None,
    "delincuencia": None,
    "culpable": None,
    "colusion comprobada": None,
    "direccionamiento comprobado": None,
    "testaferro": None,
    "criminal": None,
    "criminalidad": None,
    "ladron": None,
    "ladrones": None,
    "complice": None,
    "mafioso": None,
    "delincuente": None,
    "robo": None,
}

_SAFE_REPLACEMENTS: dict[str, str] = {
    "corrupto": "que presenta senales de riesgo",
    "fraude": "patron atipico",
    "fraudulento": "irregular",
    "ilegal": "que requiere verificacion",
    "culpable": "vinculado a los hechos",
    "delincuente": "persona sujeta a investigacion",
    "robo": "apropiacion indebida",
}


@lru_cache(maxsize=1)
def _get_patterns() -> list[_PatternPair]:
    """Compile banned-term patterns once (accent-folded, stem-aware)."""
    compiled: list[_PatternPair] = []
    for term in _BANNED_TERMS:
        norm = normalize(term)
        pat = re.compile(
            r"(?<![A-ZÑa-zñ])\b" + re.escape(norm) + r"[A-ZÑ]*",
            re.IGNORECASE,
        )
        compiled.append((pat, norm))
    return compiled


@dataclass
class SafetyReport:
    passed: bool
    blocked_terms: list[str] = field(default_factory=lambda: [])
    sanitized_text: str = ""
    mode_used: FilterMode = "reject"


class BannedTermFoundError(RuntimeError):
    """Raised when the safety filter rejects output containing banned terms."""


class LegalSafetyFilter(BaseModel):
    """Scan text for banned accusatory vocabulary.

    Uses accent-folded, stem-aware regex matching so that
    ``corruptos``, ``CORRUPCION``, ``delincuentes`` etc. are all caught.
    """

    model_config = ConfigDict(extra="forbid")

    mode: FilterMode = Field(
        default="reject",
        description="reject=raise error, sanitize=replace terms, flag=pass with warning",
    )

    def check(self, text: str) -> SafetyReport:
        if not text:
            return SafetyReport(passed=True, sanitized_text=text, mode_used=self.mode)

        patterns = _get_patterns()
        norm_text = normalize(text)
        found: set[str] = set()
        sanitized = text

        for pat, norm_term in patterns:
            if pat.search(norm_text):
                found.add(norm_term)
                if self.mode == "sanitize":
                    replacement = _SAFE_REPLACEMENTS.get(norm_term.lower())
                    if replacement:
                        sanitized = pat.sub(replacement, sanitized)

        sorted_found = sorted(found, key=str.lower)

        if not sorted_found:
            return SafetyReport(passed=True, sanitized_text=text, mode_used=self.mode)

        if self.mode == "reject":
            raise BannedTermFoundError(
                f"Output bloqueado: terminos prohibidos detectados: {sorted_found}. "
                f"Use mode='sanitize' para reemplazar automaticamente."
            )

        if self.mode == "sanitize":
            return SafetyReport(
                passed=True,
                blocked_terms=sorted_found,
                sanitized_text=sanitized,
                mode_used=self.mode,
            )

        return SafetyReport(
            passed=False,
            blocked_terms=sorted_found,
            sanitized_text=sanitized,
            mode_used=self.mode,
        )

    def _scan_text(self, text: str) -> list[str]:
        if not text:
            return []
        patterns = _get_patterns()
        norm_text = normalize(text)
        found: list[str] = []
        for pat, norm_term in patterns:
            if pat.search(norm_text):
                found.append(norm_term)
        return found

    def check_analysis(self, result: AnalysisResult) -> AnalysisResult:
        """Validate every user-facing field in an AnalysisResult.

        Scans: summary, questions_for_authority, each flag's flag_name,
        explanation, and tdr_evidence.quote.
        Raises ``BannedTermFoundError`` in reject mode if any banned term
        is found in any field.
        """
        all_blocked: list[str] = []

        all_blocked.extend(self._scan_text(result.summary))

        for q in result.questions_for_authority:
            all_blocked.extend(self._scan_text(q))

        for flag in result.flags:
            all_blocked.extend(self._scan_text(flag.flag_name))
            all_blocked.extend(self._scan_text(flag.explanation))
            all_blocked.extend(self._scan_text(flag.tdr_evidence.quote))

        if all_blocked:
            unique_blocked = sorted(set(all_blocked), key=str.lower)
            if self.mode == "reject":
                raise BannedTermFoundError(
                    f"Analysis result bloqueado: terminos en campos: {unique_blocked}. "
                    f"Use mode='sanitize' para reemplazar."
                )
            if self.mode == "sanitize":
                return self._sanitize_analysis(result)
            return result

        return result

    def _sanitize_analysis(self, result: AnalysisResult) -> AnalysisResult:
        result.summary = self.check(result.summary).sanitized_text
        result.questions_for_authority = [
            self.check(q).sanitized_text for q in result.questions_for_authority
        ]
        for flag in result.flags:
            flag.flag_name = self.check(flag.flag_name).sanitized_text
            flag.explanation = self.check(flag.explanation).sanitized_text
            flag.tdr_evidence.quote = self.check(flag.tdr_evidence.quote).sanitized_text
        return result
