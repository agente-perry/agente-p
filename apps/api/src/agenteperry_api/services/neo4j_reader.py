"""Read-only Neo4j driver against the AuraDB graph populated by the
ingest pipeline (compañero's ``ingest/main.py``). Connection is lazy and
gracefully degrades when ``NEO4J_URI`` is not configured."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from neo4j import Driver, GraphDatabase

from agenteperry_api.config import get_settings


@lru_cache(maxsize=1)
def _driver() -> Driver | None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        return None
    return GraphDatabase.driver(
        settings.neo4j_uri,  # type: ignore[arg-type]
        auth=(settings.neo4j_user, settings.neo4j_password),  # type: ignore[arg-type]
    )


def is_enabled() -> bool:
    return _driver() is not None


def run_query(cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    driver = _driver()
    if driver is None:
        return []
    settings = get_settings()
    with driver.session(database=settings.neo4j_database) as session:
        result = session.run(cypher, params or {})  # type: ignore[arg-type]
        return [r.data() for r in result]


def close() -> None:
    driver = _driver()
    if driver is not None:
        driver.close()
        _driver.cache_clear()
