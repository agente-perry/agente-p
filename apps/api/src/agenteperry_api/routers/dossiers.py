"""Dossier endpoints — read from gs://agente-perry-data-prod/scraped/results/."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from agenteperry_api.config import get_settings
from agenteperry_api.schemas.models import DossierIndexItem
from agenteperry_api.services import gcs

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


def _ocid_to_prefix(ocid: str) -> str:
    """OCDS ids contain ':' which is unsafe in GCS object names.

    The compañero's pipeline stores dossiers under
    ``scraped/results/<slug>/`` where ``<slug>`` replaces ``-`` and ``:``
    with ``_``. Match that convention.
    """
    slug = ocid.replace("-", "_").replace(":", "_")
    return f"{get_settings().gcs_results_prefix}{slug}/"


@router.get("", response_model=list[DossierIndexItem])
def list_dossiers(limit: int = 50) -> list[DossierIndexItem]:
    """List every OCID with a dossier directory under
    ``scraped/results/`` and the artefacts present."""
    settings = get_settings()
    directories = gcs.list_directories(settings.gcs_results_prefix)
    items: list[DossierIndexItem] = []
    for slug in directories[: max(limit, 0)]:
        prefix = f"{settings.gcs_results_prefix}{slug}/"
        names = gcs.list_blobs(prefix, max_results=20)
        names_set = {n.rsplit("/", 1)[-1] for n in names}
        ocid = slug.replace("_", "-", 3) if slug.startswith("ocds_") else slug
        items.append(
            DossierIndexItem(
                ocid=ocid,
                has_dossier_json="dossier.json" in names_set,
                has_dossier_md="dossier.md" in names_set,
                has_flags_json="flags.json" in names_set,
                has_pages_json="pages.json" in names_set,
                has_chunks_json="chunks.json" in names_set,
            )
        )
    return items


@router.get("/{ocid}", response_model=dict)
def get_dossier(ocid: str) -> dict[str, Any]:
    """Return the JSON dossier for a given OCID."""
    prefix = _ocid_to_prefix(ocid)
    blob_path = f"{prefix}dossier.json"
    payload = gcs.read_json(blob_path)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"dossier not found: {gcs.gcs_uri(blob_path)}")
    return payload


@router.get("/{ocid}/flags", response_model=list)
def get_flags(ocid: str) -> list[Any]:
    prefix = _ocid_to_prefix(ocid)
    blob_path = f"{prefix}flags.json"
    payload = gcs.read_json(blob_path)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"flags.json not found: {gcs.gcs_uri(blob_path)}")
    # flags.json may be a list or a dict — normalise to a list.
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "flags" in payload:
        return list(payload["flags"])
    return [payload]


@router.get("/{ocid}/markdown")
def get_markdown(ocid: str) -> dict[str, str]:
    prefix = _ocid_to_prefix(ocid)
    blob_path = f"{prefix}dossier.md"
    text = gcs.read_text(blob_path)
    if text is None:
        raise HTTPException(status_code=404, detail=f"dossier.md not found: {gcs.gcs_uri(blob_path)}")
    return {"ocid": ocid, "markdown": text, "source": gcs.gcs_uri(blob_path)}
