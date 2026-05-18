"""Demo cases for the frontend landing page. Semi-hardcoded; reads
real dossier.json files when available so flag counts stay honest."""

from __future__ import annotations

from fastapi import APIRouter

from agenteperry_api.schemas.models import DemoCase
from agenteperry_api.services import gcs

router = APIRouter(prefix="/demo", tags=["demo"])

# Hand-picked cases that exist in gs://agente-perry-data-prod/scraped/results/.
# Each entry maps a friendly title to an OCID slug used by the GCS layout.
_CASES: list[dict[str, str | None]] = [
    {
        "title": "EsSalud — Seguridad y vigilancia nacional",
        "ocid": "ocds-dgv273-seacev3-988512",
        "slug": "ocds_dgv273_seacev3_988512",
        "sector": "salud",
        "entity_name": "SEGURO SOCIAL DE SALUD (ESSALUD)",
    },
    {
        "title": "SERNANP — Seguros patrimoniales",
        "ocid": "ocds-dgv273-seacev3-1157442",
        "slug": "ocds_dgv273_seacev3_1157442",
        "sector": "ambiente",
        "entity_name": "SERNANP",
    },
    {
        "title": "ANA — Subasta Inversa Electrónica",
        "ocid": "ocds-dgv273-seacev3-2024-200254-6",
        "slug": "ocds_dgv273_seacev3_2024_200254_6",
        "sector": "ambiente_agua",
        "entity_name": "Autoridad Nacional del Agua",
    },
]


def _hydrate(case: dict[str, str | None]) -> DemoCase:
    slug = case["slug"]
    dossier_path = f"scraped/results/{slug}/dossier.json"
    payload = gcs.read_json(dossier_path)

    risk_level = "SIN_DATOS"
    score = 0
    flag_count = 0
    headline_quote: str | None = None
    headline_page: int | None = None

    if isinstance(payload, dict):
        risk_summary = payload.get("risk_summary", {})
        risk_level = str(risk_summary.get("risk_level", risk_level))
        score = int(risk_summary.get("total_score", 0))
        flag_count = int(risk_summary.get("total_flags", 0))
        flags = payload.get("flags", []) or []
        if flags:
            high = next((f for f in flags if str(f.get("severity")).upper() == "HIGH"), None)
            headline = high or flags[0]
            headline_quote = headline.get("evidence_quote")
            headline_page = headline.get("page_number")

    return DemoCase(
        ocid=str(case["ocid"]),
        title=str(case["title"]),
        sector=str(case["sector"]),
        entity_name=str(case["entity_name"]),
        risk_level=risk_level,
        score=score,
        flag_count=flag_count,
        headline_quote=headline_quote,
        headline_page=headline_page,
    )


@router.get("/cases", response_model=list[DemoCase])
def list_cases() -> list[DemoCase]:
    """Return the demo case catalogue with live counts from GCS dossiers."""
    return [_hydrate(c) for c in _CASES]
