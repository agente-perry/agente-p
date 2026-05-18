"""CivicSynthesizerAgent — legal-safe citizen-facing synthesis.

Converts accepted flags into an ``AnalysisResult`` with plain-language
summary, risk explanation, and concrete questions for the procuring
authority. Operates in mock mode by default with no LLM dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

from document_intelligence.schemas.analysis import AnalysisResult, Confidence, FlagRecord

_QUESTIONS_BY_FLAG: dict[str, list[str]] = {
    "LOW_TRACEABILITY_OUTPUT": [
        "Por que no se exige un entregable en formato estructurado o base de datos?",
        "Como se garantizara la trazabilidad de los resultados del servicio?",
    ],
    "OBSOLETE_PHYSICAL_FORMAT": [
        "Cual es el sustento tecnico para exigir entrega exclusivamente fisica?",
        "Se ha considerado un formato digital alternativo que permita mayor transparencia?",
    ],
    "EXCESSIVE_DOCUMENT_REQUIREMENT": [
        "Se ha evaluado si la cantidad de documentos exigidos es proporcional al objeto del servicio?",
        "Que estudios de mercado respaldan estos requisitos documentales?",
    ],
    "SPECIFIC_EQUIPMENT_REQUIREMENT": [
        "Por que se especifica una marca o modelo unico sin alternativa equivalente?",
        "Existe un estudio tecnico que justifique esta especificacion exclusiva?",
    ],
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": [
        "Las certificaciones exigidas son proporcionales al valor del contrato?",
        "Existen al menos tres proveedores en el mercado que puedan cumplir estos requisitos?",
    ],
    "SUBJECTIVE_EVALUATION_CRITERIA": [
        "Como se garantizara la objetividad en la evaluacion si no hay rubricas medibles?",
        "Que pesos especificos tiene cada criterio de evaluacion?",
    ],
    "UNREALISTIC_DEADLINE": [
        "El plazo de presentacion permite una participacion plural de postores?",
        "Se ha comparado este plazo con el estandar del mercado para servicios similares?",
    ],
    "OVER_SPECIFIED_EXPERIENCE": [
        "Cuantos proveidores en el mercado cumplen con los anos de experiencia exigidos?",
        "Existe un sustento objetivo para el monto acumulado minimo requerido?",
    ],
}

_FLAG_RISK_EXPLANATIONS: dict[str, str] = {
    "LOW_TRACEABILITY_OUTPUT": "Entregables sin formato estructurado o digital reducen la capacidad de supervision y auditoria.",
    "OBSOLETE_PHYSICAL_FORMAT": "La entrega exclusivamente fisica limita el acceso publico y la trazabilidad de los resultados.",
    "EXCESSIVE_DOCUMENT_REQUIREMENT": "Una carga documental alta puede desincentivar la participacion de postores pequenos o especializados.",
    "SPECIFIC_EQUIPMENT_REQUIREMENT": "Especificaciones tecnicas restrictivas pueden reducir la competencia y favorecer a un proveedor determinado.",
    "EXCESSIVE_CERTIFICATION_REQUIREMENT": "Certificaciones desproporcionadas crean barreras de entrada artificiales que limitan el numero de postores.",
    "SUBJECTIVE_EVALUATION_CRITERIA": "Criterios sin rubricas medibles permiten decisiones discrecionales en la adjudicacion.",
    "UNREALISTIC_DEADLINE": "Plazos cortos pueden excluir a postores que requieren tiempo para preparar propuestas de calidad.",
    "OVER_SPECIFIED_EXPERIENCE": "Requisitos de experiencia muy especificos pueden estar disenados para un proveedor en particular.",
}


@dataclass(frozen=True)
class SynthesizerConfig:
    max_questions: int = 5


class CivicSynthesizerAgent:
    """Generate citizen-facing analysis output from accepted flags."""

    def __init__(self, config: SynthesizerConfig | None = None) -> None:
        self._config = config or SynthesizerConfig()

    def synthesize(
        self,
        *,
        document: str = "",
        question: str = "",
        clusters_inspected: list[str] | None = None,
        flags: list[FlagRecord],
    ) -> AnalysisResult:
        if not flags:
            return AnalysisResult(
                document=document,
                question=question,
                clusters_inspected=clusters_inspected or [],
                flags=[],
                summary=self._empty_summary(),
                questions_for_authority=[],
                missing_data=["No se encontraron senales de riesgo en el documento analizado."],
                confidence="low",
            )

        questions = self._collect_questions(flags)
        summary = self._build_summary(flags)
        risk_text = self._build_risk_explanation(flags)
        confidence = self._compute_confidence(flags)

        return AnalysisResult(
            document=document,
            question=question,
            clusters_inspected=clusters_inspected or [],
            flags=flags,
            summary=summary + "\n\n" + risk_text,
            questions_for_authority=questions[: self._config.max_questions],
            missing_data=[],
            confidence=confidence,
        )

    def _empty_summary(self) -> str:
        return (
            "No se encontro evidencia suficiente para sostener senales de riesgo "
            "bajo los criterios evaluados. El documento no presenta patrones "
            "atipicos en las secciones analizadas."
        )

    def _build_summary(self, flags: list[FlagRecord]) -> str:
        n = len(flags)
        codes = ", ".join(f.flag_code for f in flags)
        return (
            f"Se identificaron {n} senales de riesgo en el documento analizado "
            f"({codes}). Cada senal esta respaldada por evidencia textual "
            f"extraida del documento y contrastada con la metodologia de "
            f"referencia (OCP Red Flags Guide / OECD). "
            f"Se recomienda revision humana de las clausulas senaladas."
        )

    def _build_risk_explanation(self, flags: list[FlagRecord]) -> str:
        parts: list[str] = []
        for flag in flags:
            explanation = _FLAG_RISK_EXPLANATIONS.get(flag.flag_code, "")
            page = flag.tdr_evidence.page_number
            parts.append(f"- {flag.flag_name}: {explanation} (pag. {page})")
        return "Detalle de las senales:\n" + "\n".join(parts)

    def _collect_questions(self, flags: list[FlagRecord]) -> list[str]:
        collected: list[str] = []
        seen: set[str] = set()
        for flag in flags:
            for q in _QUESTIONS_BY_FLAG.get(flag.flag_code, []):
                if q not in seen:
                    collected.append(q)
                    seen.add(q)
        return collected

    @staticmethod
    def _compute_confidence(flags: list[FlagRecord]) -> Confidence:
        if not flags:
            return "low"
        avg = sum(f.confidence for f in flags) / len(flags)
        if avg >= 0.65:
            return "high"
        if avg >= 0.40:
            return "medium"
        return "low"