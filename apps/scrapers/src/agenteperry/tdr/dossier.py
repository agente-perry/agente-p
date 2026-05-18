"""Generate legal-safe dossiers from TDR pipeline output.

Produces:
- dossier dict (JSON-serializable) with document metadata, flags, risk summary,
  questions for authority, and a transparency request template.
- Markdown rendering of the dossier for human review.

LEGAL NOTE: This module does NOT accuse anyone of corruption.
All language is framed as risk signals that merit review, following the
legal-safe conventions of the AgentePerry project.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteperry.tdr.models import TdrChunk, TdrFlag, TdrPage

SCHEMA_VERSION = "1.0"

DISCLAIMER = (
    "Este dossier es un analisis preventivo automatico generado por AgentePerry. "
    "No constituye acusacion de corrupcion ni declaracion de responsabilidad penal o civil. "
    "Se basa exclusivamente en evidencia textual publica extraida del documento oficial. "
    "Las senales detectadas son indicadores de riesgo que merecen revision por las "
    "autoridades competentes y la ciudadania. "
    "Toda cita es textual y referenciada por numero de pagina."
)

_RISK_LEVELS = [
    (0, "SIN_SENALES"),
    (15, "BAJO"),
    (30, "MEDIO"),
    (60, "ALTO"),
    (100, "CRITICO"),
]

_QUESTIONS_BY_FLAG: dict[str, list[str]] = {
    "EXCESSIVE_DOCUMENT_REQUIREMENT": [
        "¿Existe sustento del area usuaria que justifique el volumen documental requerido?",
        "¿Se evaluo si este requisito limitaba la cantidad de postores?",
        "¿Cuantos postores presentaron propuesta en este proceso?",
        "¿El requisito documental fue observado durante el periodo de consultas?",
    ],
    "OBSOLETE_PHYSICAL_FORMAT": [
        "¿Por que se exige entrega en formato fisico o en soporte obsoleto?",
        "¿Existe justificacion tecnica documentada para este requerimiento?",
        "¿El formato fisico dificulta la auditoria digital posterior del entregable?",
    ],
    "SPECIFIC_EQUIPMENT_REQUIREMENT": [
        "¿Por que se exige equipamiento de marca o tipo especifico en lugar de especificaciones funcionales?",
        "¿Cuantos proveedores en el mercado podian cumplir este requisito?",
        "¿El requerimiento de equipamiento fue parte del estudio de mercado?",
        "¿Quien del area usuaria definio el equipamiento especifico y con que sustento?",
    ],
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": [
        "¿Por que se exige esta certificacion internacional?",
        "¿Cuantos proveedores peruanos cuentan con esta certificacion?",
        "¿La certificacion es proporcional al objeto de la contratacion?",
        "¿El requerimiento de certificacion fue incluido en el estudio de mercado previo?",
    ],
    "LOW_TRACEABILITY_OUTPUT": [
        "¿Como se verificara y validara el cumplimiento del entregable descrito?",
        "¿Existen criterios de aceptacion e indicadores medibles para este entregable?",
        "¿Quien del area usuaria firma la conformidad del servicio y con que rubrica?",
    ],
    "SUBJECTIVE_EVALUATION_CRITERIA": [
        "¿Cual es la rubrica verificable y auditable asociada a este criterio de evaluacion?",
        "¿Existio pronunciamiento de algun postor sobre la subjetividad de este criterio?",
        "¿El comite de evaluacion documento como aplico este criterio en el acta?",
        "¿Se puede reproducir la evaluacion a partir del acta disponible?",
    ],
}

_GENERIC_QUESTIONS = [
    "¿Donde esta el requerimiento del area usuaria que origino este proceso?",
    "¿El estudio de mercado consulto al menos tres fuentes independientes?",
    "¿El valor referencial fue aprobado por el funcionario competente?",
    "¿El contrato final y la conformidad del servicio estan disponibles publicamente?",
]

_TRANSPARENCY_REQUEST_TEMPLATE = """\
Solicito copia digital del expediente de contratacion asociado al \
procedimiento {procedure_ref}, incluyendo:

1. Requerimiento del area usuaria.
2. Terminos de referencia o especificaciones tecnicas completas.
3. Estudio de mercado utilizado para determinar el valor estimado.
4. Relacion de postores registrados o que adquirieron las bases.
5. Acta de evaluacion tecnica y economica.
6. Acta de otorgamiento de buena pro.
7. Contrato suscrito con el proveedor ganador.
8. Conformidades del servicio o entrega.
9. Sustento tecnico de los requisitos observados en las paginas: {pages_ref}.
10. Cualquier informe que justifique la inclusion de certificaciones, \
equipos o condiciones especificas.\
"""


def _risk_level_for_score(score: int) -> str:
    level = "SIN_SENALES"
    for threshold, label in _RISK_LEVELS:
        if score >= threshold:
            level = label
    return level


def _sha256_of_file(pdf_path: Path) -> str:
    digest = hashlib.sha256()
    with pdf_path.open("rb") as fh:
        for block in iter(lambda: fh.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _deduplicated_questions(flags: list[TdrFlag]) -> list[str]:
    seen_codes: set[str] = set()
    questions: list[str] = []
    for flag in flags:
        if flag.flag_code not in seen_codes:
            seen_codes.add(flag.flag_code)
            questions.extend(_QUESTIONS_BY_FLAG.get(flag.flag_code, []))
    questions.extend(_GENERIC_QUESTIONS)
    # Deduplicate while preserving order
    unique: list[str] = []
    seen_q: set[str] = set()
    for q in questions:
        if q not in seen_q:
            seen_q.add(q)
            unique.append(q)
    return unique


def generate_dossier(
    *,
    pdf_path: Path,
    sector: str,
    ocid: str,
    entity_name: str | None = None,
    procedure_code: str | None = None,
    monto: float | None = None,
    coverage_pct: float = 0.0,
    total_pages: int = 0,
    pages: list[TdrPage],
    chunks: list[TdrChunk],
    flags: list[TdrFlag],
) -> dict[str, Any]:
    """Build a structured, JSON-serializable dossier dict.

    All evidence is drawn exclusively from the extracted text.
    No inference or invented evidence is included.
    """
    checksum = _sha256_of_file(pdf_path)

    high_flags = [f for f in flags if f.severity.value == "HIGH"]
    medium_flags = [f for f in flags if f.severity.value == "MEDIUM"]
    low_flags = [f for f in flags if f.severity.value == "LOW"]
    total_score = sum(f.score_contribution for f in flags)
    risk_level = _risk_level_for_score(total_score)

    flag_pages = sorted({f.page_number for f in flags})
    pages_ref = ", ".join(str(p) for p in flag_pages) if flag_pages else "N/A"
    procedure_ref = procedure_code or ocid

    questions = _deduplicated_questions(flags)

    transparency_request = _TRANSPARENCY_REQUEST_TEMPLATE.format(
        procedure_ref=procedure_ref,
        pages_ref=pages_ref,
    )

    flags_payload = [
        {
            "flag_code": f.flag_code,
            "flag_name": f.flag_name,
            "severity": f.severity.value,
            "score_contribution": f.score_contribution,
            "page_number": f.page_number,
            "evidence_quote": f.evidence_quote,
            "explanation": f.explanation,
            "detection_method": f.detection_method,
            "rule_id": f.rule_id,
        }
        for f in flags
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "document": {
            "ocid": ocid,
            "sector": sector,
            "entity_name": entity_name or "Sin dato",
            "procedure_code": procedure_code or "Sin dato",
            "monto": monto,
            "storage_path": str(pdf_path),
            "checksum": f"sha256:{checksum}",
            "parse_status": "parsed",
            "total_pages": total_pages,
            "total_chunks": len(chunks),
            "coverage_pct": coverage_pct,
        },
        "risk_summary": {
            "total_flags": len(flags),
            "high_flags": len(high_flags),
            "medium_flags": len(medium_flags),
            "low_flags": len(low_flags),
            "total_score": total_score,
            "risk_level": risk_level,
        },
        "flags": flags_payload,
        "questions_for_authority": questions,
        "transparency_request": transparency_request,
        "disclaimer": DISCLAIMER,
    }


def render_dossier_markdown(dossier: dict[str, Any]) -> str:
    """Render a dossier dict as legal-safe markdown for human review."""
    doc = dossier["document"]
    risk = dossier["risk_summary"]
    flags: list[dict[str, Any]] = dossier["flags"]

    sector_display = doc["sector"].replace("_", "/").title()
    monto_display = (
        f"S/ {doc['monto']:,.2f}" if doc.get("monto") is not None else "Sin dato"
    )

    lines: list[str] = []

    lines.append(f"# Dossier TDR — {sector_display}")
    lines.append("")
    lines.append(f"> **Generado:** {dossier['generated_at'][:10]}  ")
    lines.append(f"> **OCID:** `{doc['ocid']}`  ")
    lines.append(f"> **Nivel de riesgo:** `{risk['risk_level']}`  ")
    lines.append(f"> **Score total:** {risk['total_score']} / 100  ")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Aviso Legal")
    lines.append("")
    lines.append(f"> {dossier['disclaimer']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 1. Documento Analizado")
    lines.append("")
    lines.append("| Campo | Valor |")
    lines.append("|---|---|")
    lines.append(f"| Entidad | {doc['entity_name']} |")
    lines.append(f"| Sector | {sector_display} |")
    lines.append(f"| Procedimiento | {doc['procedure_code']} |")
    lines.append(f"| Monto estimado | {monto_display} |")
    lines.append(f"| Paginas totales | {doc['total_pages']} |")
    lines.append(f"| Paginas con texto | {doc['total_pages']} ({doc['coverage_pct']}% coverage) |")
    lines.append(f"| Chunks generados | {doc['total_chunks']} |")
    lines.append(f"| SHA-256 | `{doc['checksum']}` |")
    lines.append(f"| Estado parse | `{doc['parse_status']}` |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 2. Senales Detectadas")
    lines.append("")

    if not flags:
        lines.append(
            "No se detectaron senales de riesgo con las reglas actuales del MVP. "
            "Esto no implica ausencia de irregularidades; las reglas cubren solo "
            "un subconjunto de patrones documentales."
        )
    else:
        lines.append(
            f"Se detectaron **{risk['total_flags']} senales** "
            f"({risk['high_flags']} HIGH, {risk['medium_flags']} MEDIUM, {risk['low_flags']} LOW) "
            f"con un score acumulado de **{risk['total_score']} puntos**."
        )
        lines.append("")
        lines.append("| # | Flag | Severidad | Pagina | Score | Evidencia |")
        lines.append("|---|---|---|---:|---:|---|")
        for i, flag in enumerate(flags, 1):
            evidence_short = flag["evidence_quote"].replace("\n", " ")[:120].strip()
            if len(flag["evidence_quote"]) > 120:
                evidence_short += "..."
            lines.append(
                f"| {i} | {flag['flag_name']} | `{flag['severity']}` "
                f"| {flag['page_number']} | +{flag['score_contribution']} "
                f"| {evidence_short} |"
            )

    lines.append("")
    lines.append("---")
    lines.append("")

    if flags:
        lines.append("## 3. Detalle de Cada Senal")
        lines.append("")
        for i, flag in enumerate(flags, 1):
            lines.append(f"### {i}. {flag['flag_name']} (`{flag['flag_code']}`)")
            lines.append("")
            lines.append(f"- **Severidad:** {flag['severity']}")
            lines.append(f"- **Score:** +{flag['score_contribution']}")
            lines.append(f"- **Pagina:** {flag['page_number']}")
            lines.append(f"- **Regla:** `{flag['rule_id']}`")
            lines.append("")
            lines.append("**Evidencia textual (cita literal del documento):**")
            lines.append("")
            lines.append(f"> {flag['evidence_quote']}")
            lines.append("")
            lines.append("**Por que merece revision:**")
            lines.append("")
            lines.append(flag["explanation"])
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 4. Por Que Este Documento Merece Revision")
    lines.append("")
    if not flags:
        lines.append(
            "No se activaron senales automaticas. "
            "Se recomienda revision manual del contenido de los requisitos de experiencia, "
            "plazos de entrega y valor referencial."
        )
    else:
        lines.append(
            "El documento presenta patrones textuales que, segun las reglas del MVP de AgentePerry, "
            "pueden indicar barreras administrativas, baja trazabilidad o criterios de evaluacion "
            "poco verificables. Estas senales **no constituyen prueba de irregularidad** pero "
            "justifican una revision documental por parte de las autoridades competentes y "
            "la ciudadania interesada."
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 5. Preguntas Para la Autoridad")
    lines.append("")
    for j, question in enumerate(dossier["questions_for_authority"], 1):
        lines.append(f"{j}. {question}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 6. Solicitud de Transparencia Recomendada")
    lines.append("")
    lines.append("```")
    lines.append(dossier["transparency_request"])
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 7. Accion Ciudadana")
    lines.append("")
    lines.append(
        "Esta solicitud puede presentarse al area de Acceso a la Informacion Publica de "
        "la entidad contratante, en virtud del Texto Unico Ordenado de la Ley N° 27806, "
        "Ley de Transparencia y Acceso a la Informacion Publica. "
        "El plazo de respuesta es de 7 dias habiles prorrogables a 15."
    )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Generado por AgentePerry TDR Scanner — analisis preventivo automatico.*")
    lines.append("")

    return "\n".join(lines)



