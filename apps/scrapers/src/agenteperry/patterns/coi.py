"""Conflict-of-interest detection using graph relationships in Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CoiSignal:
    """Conflict-of-interest signal derived from graph relationship type."""
    rel_type: str
    score: int
    explanation: str
    evidence: str


COI_PATTERNS: tuple[CoiSignal, ...] = (
    CoiSignal(
        rel_type="MIEMBRO_COMITE",
        score=25,
        explanation="Un miembro del comite de seleccion参与了 la empresa ganadora del contrato.",
        evidence="El proveedor gano un contrato donde un miembro de su organo de administracion fue parte del comite evaluador.",
    ),
    CoiSignal(
        rel_type="REPRESENTANTE_DE",
        score=20,
        explanation="La persona es representante legal de la empresa ganadora y a la vez tiene vinculo laboral con la entidad.",
        evidence="Existe un vinculo representativo entre el proveedor y una persona vinculada a la entidad contratante.",
    ),
    CoiSignal(
        rel_type="FAMILIAR_DE",
        score=30,
        explanation="Un familiar directo del funcionario evaluador representa a la empresa ganadora.",
        evidence="Se detecto vinculo familiar entre un agentepublico y el representante de la empresa.",
    ),
    CoiSignal(
        rel_type="MONOPOLIO_PROVEEDOR",
        score=15,
        explanation="La empresa concentra mas del 70% del gasto de la entidad en los ultimos 3 anos.",
        evidence="Patron de concentracion atipica en la contratacion publica de esta entidad.",
    ),
    CoiSignal(
        rel_type="DIRECCION_COMPARTIDA",
        score=10,
        explanation="Empresas con mismo domicilio fiscal han ganado como unicopostor en la misma entidad.",
        evidence="Direccion fiscal compartida sugiere posible fachada empresarial.",
    ),
)


def compute_coi_score(signals: list[str]) -> int:
    """Compute cumulative COI score from signal types."""
    score = 0
    for sig in signals:
        for pattern in COI_PATTERNS:
            if pattern.rel_type == sig:
                score += pattern.score
                break
    return min(score, 100)


def flag_coi_signals_from_rels(
    rels: list[dict[str, Any]],
) -> list[CoiSignal]:
    """Detect COI signals from a list of relationship records."""
    signals: list[CoiSignal] = []
    seen_types: set[str] = set()

    for rel in rels:
        rel_type: str = rel.get("rel_type") or ""
        for pattern in COI_PATTERNS:
            if rel_type == pattern.rel_type and rel_type not in seen_types:
                signals.append(pattern)
                seen_types.add(rel_type)

    return signals