"""On-demand AuditorGraph trigger for a single TDR/PDF stored in GCS."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agenteperry_api.config import get_settings
from agenteperry_api.schemas.models import AuditRequest, AuditResponse
from agenteperry_api.services import auditor as auditor_service
from agenteperry_api.services import gcs

router = APIRouter(prefix="/audit", tags=["audit"])


def _find_pdf_for_ocid(ocid: str) -> str | None:
    """Best-effort lookup of the canonical PDF for an OCID.

    Strategy: look under ``scraped/tdrs/**/{ocid_slug}/*.pdf`` and pick the
    first ``bases_integradas_*``, ``tdr*`` or fallback to the first PDF.
    """
    slug = ocid.replace("-", "_").replace(":", "_")
    prefixes = [
        f"scraped/tdrs/salud/{slug}/",
        f"scraped/tdrs/ambiente/{slug}/",
        f"scraped/tdrs/ambiente_mineria/{slug}/",
    ]
    for prefix in prefixes:
        names = gcs.list_blobs(prefix, max_results=20)
        pdfs = [n for n in names if n.lower().endswith(".pdf")]
        if not pdfs:
            continue
        # Priority: bases_integradas, tdr, anything else.
        for needle in ("bases_integradas", "tdr", "bases"):
            for name in pdfs:
                if needle in name.lower():
                    return name
        return pdfs[0]
    return None


@router.post("/{ocid}", response_model=AuditResponse)
def audit_ocid(ocid: str, body: AuditRequest) -> AuditResponse:
    settings = get_settings()
    if settings.api_disable_auditor:
        raise HTTPException(status_code=501, detail="auditor disabled in this deployment")
    if not auditor_service.is_available():
        raise HTTPException(
            status_code=501,
            detail=(
                "auditor stack (document_intelligence + langgraph + agenteperry) "
                "not installed in this venv. See apps/api/README.md."
            ),
        )

    blob_path = body.explicit_pdf_path or _find_pdf_for_ocid(ocid)
    if blob_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"no PDF found in GCS for {ocid}. Pass `explicit_pdf_path` to override.",
        )

    # Stream the PDF to a tempfile so the local auditor can read it.
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        from google.cloud import storage as _gcs  # type: ignore[import-untyped]

        client = _gcs.Client(project=settings.gcp_project)
        bucket = client.bucket(settings.gcs_bucket)
        bucket.blob(blob_path).download_to_filename(tmp.name)
        local_path = Path(tmp.name)

    state = auditor_service.run_auditor_on_pdf(
        pdf_path=local_path,
        sector=body.sector,
        ocid=ocid,
        entity_name=body.entity_name,
        procedure_code=body.procedure_code,
        monto=body.monto,
    )
    if state is None:
        raise HTTPException(status_code=501, detail="auditor returned no state")

    return AuditResponse(ocid=ocid, **state)
