"""Neo4j Aura client for AgentePerry — SPEC-0012.

Sync driver, follows the same pattern as db/client.py.
Credentials from environment: NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE.
"""

from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any, cast

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError as _err:
    raise ImportError(
        "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
    ) from _err


class Neo4jClient:
    """Sync client for Neo4j Aura.

    Usage::

        client = Neo4jClient()
        rows = client.execute_read("MATCH (c:Company) RETURN c.ruc LIMIT 5")
        client.close()

    Or as context manager::

        with Neo4jClient() as client:
            rows = client.execute_read("RETURN 1 AS test")
    """

    def __init__(
        self,
        uri: str | None = None,
        username: str | None = None,
        password: str | None = None,
        database: str | None = None,
    ) -> None:
        self._uri = uri or os.environ.get("NEO4J_URI")
        self._username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self._password = password or os.environ.get("NEO4J_PASSWORD")
        self._database = database or os.environ.get("NEO4J_DATABASE", "neo4j")

        if not self._uri:
            raise ValueError("NEO4J_URI not set. Add it to .env or pass uri= explicitly.")
        if not self._password:
            raise ValueError("NEO4J_PASSWORD not set. Add it to .env or pass password= explicitly.")

        self._driver = GraphDatabase.driver(  # type: ignore[reportUnknownMemberType]
            self._uri,
            auth=(self._username, self._password),
            max_connection_lifetime=3600,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def verify_connection(self) -> bool:
        """Return True if the database is reachable, False otherwise."""
        try:
            result = self.execute_read("RETURN 1 AS test")
            return bool(result) and result[0].get("test") == 1
        except ServiceUnavailable as exc:
            raise ServiceUnavailable(
                f"Neo4j unreachable at {self._uri}. "
                "Wait 60s after Aura creation or check credentials."
            ) from exc
        except Exception:  # noqa: BLE001
            return False

    def execute_write(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a write query (CREATE, MERGE, SET) and return records."""
        with self._session() as session:
            result = session.run(query, parameters or {})
            return cast(list[dict[str, Any]], result.data())

    def execute_read(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a read query (MATCH, RETURN) and return records."""
        with self._session() as session:
            result = session.run(query, parameters or {})
            return cast(list[dict[str, Any]], result.data())

    def execute_write_batch(
        self,
        query: str,
        rows: list[dict[str, Any]],
        batch_size: int = 500,
    ) -> int:
        """Execute a write query for a list of parameter dicts in batches.

        Uses UNWIND for efficiency — query must accept ``$rows`` parameter::

            UNWIND $rows AS row
            MERGE (c:Company {ruc: row.ruc})
            SET c.name = row.name

        Returns total number of rows processed.
        """
        total = 0
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            self.execute_write(query, {"rows": batch})
            total += len(batch)
        return total

    def close(self) -> None:
        """Close the underlying driver connection pool."""
        self._driver.close()

    # ------------------------------------------------------------------
    # Context manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _session(self) -> Generator[Any, None, None]:
        with self._driver.session(database=self._database) as session:  # type: ignore[reportUnknownMemberType]
            yield session


# Module-level convenience singleton — lazily created
_client: Neo4jClient | None = None


def get_client() -> Neo4jClient:
    """Return the module-level singleton Neo4jClient (created on first call)."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = Neo4jClient()
    return _client
