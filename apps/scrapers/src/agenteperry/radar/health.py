"""Lightweight health checks for registered public sources."""

from __future__ import annotations

import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agenteperry.collectors import build_collector
from agenteperry.radar.models import SourceHealthCheck
from agenteperry.sources import SourceType, build_default_registry

_LOCAL_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "ocds_peru": ("data/scraped/ocds/records.jsonl", "data/scraped/ocds/contracts_2026.jsonl"),
    "sunat_padron": ("data/scraped/collectors/sunat_padron/records.jsonl",),
    "seace_oece": ("data/scraped/collectors/oece/records.jsonl",),
    "contraloria_sanciones": ("data/scraped/collectors/contraloria_sanciones/records.jsonl",),
}


def check_source_health(source_code: str) -> SourceHealthCheck:
    """Run a non-invasive health check for one registered source."""
    checked_at = datetime.now(UTC).isoformat()
    registry = build_default_registry()
    source = registry.get(source_code)
    if source is None:
        return SourceHealthCheck(
            source_code=source_code,
            checked_at=checked_at,
            status="failed",
            url_reachable=None,
            local_data_exists=None,
            schema_valid=False,
            last_audit_exists=None,
            error=f"Unknown source: {source_code}",
        )

    details: dict[str, Any] = {
        "source_name": source.source_name,
        "source_type": source.source_type.value,
        "priority": source.priority.value,
        "status": source.status.value,
    }
    collector_available = _collector_available(source)
    local_data_exists = _local_data_exists(source_code)
    last_audit_exists = _last_audit_exists(source_code)
    url_reachable = _light_url_check(source.source_url, enabled=source.source_type != SourceType.PLAYWRIGHT)
    schema_valid = bool(source.fields or source.metadata or collector_available)
    details.update(
        {
            "collector_available": collector_available,
            "requires_playwright": source.source_type == SourceType.PLAYWRIGHT,
        }
    )

    if source.source_type == SourceType.PLAYWRIGHT:
        status = "unknown"
        error = "Playwright health checks are planned, not implemented in Activity 8A"
    elif not collector_available:
        status = "degraded"
        error = "Collector not implemented"
    elif local_data_exists is False and url_reachable is False:
        status = "degraded"
        error = "No local artifact and source URL was not reachable"
    else:
        status = "ok"
        error = None

    return SourceHealthCheck(
        source_code=source_code,
        checked_at=checked_at,
        status=status,
        url_reachable=url_reachable,
        local_data_exists=local_data_exists,
        schema_valid=schema_valid,
        last_audit_exists=last_audit_exists,
        error=error,
        details=details,
    )


def check_all_sources() -> list[SourceHealthCheck]:
    """Run health checks for every registered source."""
    return [check_source_health(source.source_code) for source in build_default_registry().list_all()]


def _collector_available(source: Any) -> bool:
    try:
        build_collector(source)
    except NotImplementedError:
        return False
    return True


def _local_data_exists(source_code: str) -> bool | None:
    candidates = _LOCAL_ARTIFACTS.get(source_code)
    if not candidates:
        return None
    return any(_resolve_repo_path(path).exists() for path in candidates)


def _last_audit_exists(source_code: str) -> bool | None:
    candidates = (
        f"data/scraped/collectors/{source_code}/audit.json",
        f"data/scraped/{source_code}/audit.json",
        f"data/runs/{source_code}/hashes.json",
    )
    return any(_resolve_repo_path(path).exists() for path in candidates)


def _light_url_check(url: str | None, *, enabled: bool) -> bool | None:
    if not enabled or not url:
        return None
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


def _resolve_repo_path(relative_path: str) -> Path:
    path = Path(relative_path)
    if path.exists():
        return path
    cwd = Path.cwd()
    for parent in (cwd, *cwd.parents):
        candidate = parent / relative_path
        if candidate.exists():
            return candidate
    return path
