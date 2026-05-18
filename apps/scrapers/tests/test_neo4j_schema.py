"""Unit tests for GraphSchema (neo4j_schema.py) — SPEC-0012.

Tests verify that setup_schema:
- Calls execute_write for each constraint and index.
- Is idempotent (handles "already exists" errors gracefully).
- Raises on unexpected errors.
- Returns the correct summary dict.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agenteperry.graph.neo4j_schema import setup_schema

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_client(side_effects: list | None = None) -> MagicMock:
    """Return a mock Neo4jClient whose execute_write behaves as specified."""
    client = MagicMock()
    if side_effects:
        client.execute_write.side_effect = side_effects
    else:
        client.execute_write.return_value = []
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_setup_schema_calls_execute_write_for_all_ddl() -> None:
    client = _mock_client()

    result = setup_schema(client=client)

    # 6 constraints + 6 indexes = 12 DDL statements
    assert client.execute_write.call_count == 12
    assert result["total"] == 12
    assert result["created"] == 12
    assert result["skipped"] == 0


def test_setup_schema_calls_contain_if_not_exists() -> None:
    client = _mock_client()
    setup_schema(client=client)

    for call_args in client.execute_write.call_args_list:
        ddl = call_args[0][0]
        assert "IF NOT EXISTS" in ddl, f"Missing IF NOT EXISTS in: {ddl}"


def test_setup_schema_includes_all_node_labels() -> None:
    client = _mock_client()
    setup_schema(client=client)

    all_ddl = " ".join(str(c) for c in client.execute_write.call_args_list)
    for label in ("Contract", "Company", "Person", "PublicEntity", "TDR", "Flag"):
        assert label in all_ddl, f"Label {label} missing from schema DDL"


# ---------------------------------------------------------------------------
# Idempotence — "already exists" errors are swallowed
# ---------------------------------------------------------------------------


def test_setup_schema_skips_existing_constraints() -> None:
    # Simulate all DDL succeeding except 3 that raise "already exists"
    def side_effect(ddl: str) -> list:
        if "constraint" in ddl.lower() and "company" in ddl.lower():
            raise Exception("An equivalent constraint already exists")
        return []

    client = MagicMock()
    client.execute_write.side_effect = side_effect

    result = setup_schema(client=client)

    assert result["skipped"] >= 1
    assert result["created"] + result["skipped"] == 12


def test_setup_schema_skips_equivalent_index() -> None:
    def side_effect(ddl: str) -> list:
        if "INDEX" in ddl and "amount" in ddl:
            raise Exception("There already exists an index called contract_amount_idx")
        return []

    client = MagicMock()
    client.execute_write.side_effect = side_effect

    result = setup_schema(client=client)
    assert result["skipped"] >= 1


# ---------------------------------------------------------------------------
# Error propagation — unexpected errors do raise
# ---------------------------------------------------------------------------


def test_setup_schema_raises_on_unexpected_error() -> None:
    def side_effect(ddl: str) -> list:
        raise Exception("Connection refused: database is down")

    client = MagicMock()
    client.execute_write.side_effect = side_effect

    with pytest.raises(RuntimeError, match="Schema setup completed with"):
        setup_schema(client=client)


# ---------------------------------------------------------------------------
# Return value structure
# ---------------------------------------------------------------------------


def test_setup_schema_return_keys() -> None:
    client = _mock_client()

    result = setup_schema(client=client)

    assert set(result.keys()) == {"created", "skipped", "total"}
    assert result["total"] == result["created"] + result["skipped"]
