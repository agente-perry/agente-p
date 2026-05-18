"""Health + readiness."""

from __future__ import annotations

from fastapi import APIRouter

from agenteperry_api import __version__
from agenteperry_api.config import get_settings
from agenteperry_api.schemas.models import HealthResponse
from agenteperry_api.services import auditor as auditor_service
from agenteperry_api.services import neo4j_reader

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        api_version=__version__,
        gcs_bucket=settings.gcs_bucket,
        neo4j_enabled=neo4j_reader.is_enabled(),
        auditor_available=auditor_service.is_available(),
    )
