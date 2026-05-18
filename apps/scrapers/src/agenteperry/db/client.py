"""Database client for AgentePerry."""

from __future__ import annotations

import os
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row


class DbClient:
    """Minimal Supabase/Postgres client for AgentePerry."""

    def __init__(self, connection_url: str | None = None) -> None:
        self.url = connection_url or os.environ.get("DATABASE_URL")

    def _connection_url(self) -> str:
        if self.url is None:
            raise ValueError("DATABASE_URL environment variable not set")
        return self.url

    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Context manager for database connections."""
        with psycopg.connect(self._connection_url(), row_factory=cast(Any, dict_row)) as conn:
            yield conn

    def execute(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a query and return results as a list of dicts."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(cast(Any, query), params)
                if cur.description:
                    rows = cast(list[Mapping[str, Any]], cur.fetchall())
                    return [dict(row) for row in rows]
                return []

    def execute_batch(
        self,
        query: str,
        params_list: Sequence[Sequence[Any] | Mapping[str, Any]],
    ) -> None:
        """Execute a batch of queries."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(cast(Any, query), params_list)
            conn.commit()


# Global client instance
db = DbClient()
