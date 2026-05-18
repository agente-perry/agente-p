"""Rule-based TDR signals with direct evidence."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from agenteperry.tdr.models import TdrFlag, TdrPage, TdrSeverity


@dataclass(frozen=True)
class TdrFlagRule:
    rule_id: str
    flag_code: str
    flag_name: str
    severity: TdrSeverity
    score_contribution: int
    explanation: str
    patterns: tuple[re.Pattern[str], ...]
    max_hits: int = 3


RULES: tuple[TdrFlagRule, ...] = (
    TdrFlagRule(
        "TDR-R001",
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        "Requisito documental excesivo",
        TdrSeverity.MEDIUM,
        15,
        "El TDR exige un volumen documental alto; merece revision por posible barrera administrativa.",
        (re.compile(r"\b\d{3,}\s*(?:paginas|folios)\b"), re.compile(r"\binforme\s+de\s+\d{3,}\s*(?:paginas|folios)\b")),
    ),
    TdrFlagRule(
        "TDR-R002",
        "OBSOLETE_PHYSICAL_FORMAT",
        "Formato fisico u obsoleto",
        TdrSeverity.LOW,
        10,
        "El TDR menciona formatos fisicos u obsoletos que pueden reducir trazabilidad digital.",
        (re.compile(r"\bformato\s+a3\b"), re.compile(r"\b(?:cd|dvd|usb)\b"), re.compile(r"\b(?:entrega|presentacion)\s+(?:en\s+)?fisic[ao]\b"), re.compile(r"\bimpreso\b")),
    ),
    TdrFlagRule(
        "TDR-R003",
        "SPECIFIC_EQUIPMENT_REQUIREMENT",
        "Equipamiento especifico",
        TdrSeverity.MEDIUM,
        15,
        "El TDR exige equipamiento especifico; merece revision si no esta justificado por el servicio.",
        (re.compile(r"\b(?:camioneta|vehiculo\s+4x4|dron|drone)\b"), re.compile(r"\bmarca\s+especifica\b"), re.compile(r"\blaptop\s+(?:core\s+i[579]|macbook)\b")),
    ),
    TdrFlagRule(
        "TDR-R004",
        "EXCESSIVE_CERTIFICATION_REQUIREMENT",
        "Certificacion posiblemente restrictiva",
        TdrSeverity.MEDIUM,
        15,
        "El TDR exige certificaciones que podrian limitar competencia si no son proporcionales.",
        (re.compile(r"\biso\s*(?:9001|14001|27001|37001|45001)\b"), re.compile(r"\bcertificacion\s+internacional\b")),
    ),
    TdrFlagRule(
        "TDR-R005",
        "LOW_TRACEABILITY_OUTPUT",
        "Entregable de baja trazabilidad",
        TdrSeverity.LOW,
        10,
        "El entregable descrito parece poco estructurado; puede dificultar verificacion posterior.",
        (re.compile(r"\binforme\s+final\b"), re.compile(r"\b(?:powerpoint|ppt|presentacion)\b"), re.compile(r"\bentregable\s+unico\b")),
    ),
    TdrFlagRule(
        "TDR-R006",
        "SUBJECTIVE_EVALUATION_CRITERIA",
        "Criterio de evaluacion subjetivo",
        TdrSeverity.MEDIUM,
        15,
        "El TDR usa criterios amplios o subjetivos que deberian tener una rubrica verificable.",
        (re.compile(r"\ba\s+criterio\s+del\s+comite\b"), re.compile(r"\bcalidad\s+de\s+la\s+propuesta\b"), re.compile(r"\bmejor\s+propuesta\s+tecnica\b")),
    ),
    TdrFlagRule(
        "TDR-R007",
        "PHYSICAL_PRESENTATION_REQUIRED",
        "Requisito de presentacion fisica",
        TdrSeverity.MEDIUM,
        15,
        "El proceso requiere presentacion o entrega fisica de documentacion; puede generar barreras de entrada para postores de regiones o con recursos limitados.",
        (
            re.compile(r"\bpresent(?:ar|e)\s+(?:la\s+)?documentaci\w+\s+(?:en\s+)?(?:forma\s+)?f[ií]sica\b"),
            re.compile(r"\bmesa\s+de\s+partes\s+(?:virtual|electronica)\b"),
            re.compile(r"\bdebe(?:r)?\s+present\w+\s+(?:la\s+)?documentaci\w+\s+(?:en\s+)?(?:forma\s+)?f[ií]sica\b"),
            re.compile(r"\bdomicilio\s+(?:de\s+)?presentaci\w+\b"),
            re.compile(r"\bforma\s+f[ií]sica\b"),
            re.compile(r"\bpf[ií]sica\b"),
        ),
    ),
    TdrFlagRule(
        "TDR-R008",
        "SINGLE_SUPPLIER_CONTEXT",
        "Posible proveedor unico identificado",
        TdrSeverity.MEDIUM,
        15,
        "El proceso refiere especificaciones que solo un proveedor conocido podria cumplir; merece revision de posible restrictividad.",
        (
            re.compile(r"\bsolo\s+(?:podran\s+)?participar\s+(?:empresas?\s+)?con\s+(?:experiencia\s+en\s+)?(?:el\s+)?sector\s+(?:salud|privado)\b"),
            re.compile(r"\bexperiencia\s+(?:m[ií]nima\s+)?de\s+(?:\d+\s+)?años?\s+(?:en\s+)?(?:el\s+)?sector\b"),
            re.compile(r"\bcontrat(?:o|ación)\s+(?:anterior\s+)?con\s+(?:ESSALUD|Minsa|ministerio)\b"),
            re.compile(r"\bcalificado\s+(?:proveedor\s+)?de\s+(?:salud|servicios?\s+m[eé]dicos?)\b"),
        ),
    ),
)


def detect_flags_in_pages(pages: list[TdrPage]) -> list[TdrFlag]:
    """Detect initial MVP flags with evidence quote and page number."""
    flags: list[TdrFlag] = []
    hits_by_rule: dict[str, int] = {rule.rule_id: 0 for rule in RULES}

    for page in pages:
        normalized = _normalize_for_match(page.text_content)
        if not normalized:
            continue
        for rule in RULES:
            if hits_by_rule[rule.rule_id] >= rule.max_hits:
                continue
            for pattern in rule.patterns:
                match = pattern.search(normalized)
                if not match:
                    continue
                flags.append(
                    TdrFlag(
                        tdr_id=page.tdr_id,
                        flag_code=rule.flag_code,
                        flag_name=rule.flag_name,
                        severity=rule.severity,
                        score_contribution=rule.score_contribution,
                        evidence_quote=_quote_context(page.text_content, match.start(), match.end()),
                        page_number=page.page_number,
                        explanation=rule.explanation,
                        rule_id=rule.rule_id,
                    )
                )
                hits_by_rule[rule.rule_id] += 1
                break
    return flags


def _normalize_for_match(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", ascii_text)


def _quote_context(text: str, start: int, end: int, *, radius: int = 120) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    quote_start = max(start - radius, 0)
    quote_end = min(end + radius, len(compact))
    return compact[quote_start:quote_end].strip()
