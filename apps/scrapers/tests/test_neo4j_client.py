"""Unit tests for Neo4jClient — SPEC-0012.

All tests use unittest.mock to avoid requiring a real Neo4j connection.
The tests verify:
- Credential validation at construction time
- execute_read / execute_write call the driver correctly
- execute_write_batch batches correctly
- verify_connection returns True/False appropriately
- Context manager protocol works
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agenteperry.graph.neo4j_client import Neo4jClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_client(uri: str = "neo4j+s://test.databases.neo4j.io") -> Neo4jClient:
    """Build a Neo4jClient with a mocked underlying driver."""
    with patch("agenteperry.graph.neo4j_client.GraphDatabase") as mock_gdb:
        mock_driver = MagicMock()
        mock_gdb.driver.return_value = mock_driver
        client = Neo4jClient(uri=uri, username="neo4j", password="s3cr3t")
    # Attach mock driver for assertions in tests
    client._driver = mock_driver  # type: ignore[attr-defined]
    return client


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_raises_if_uri_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO4J_URI", raising=False)
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="NEO4J_URI"):
        Neo4jClient(username="neo4j", password="pw")


def test_raises_if_password_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with patch("agenteperry.graph.neo4j_client.GraphDatabase"):
        with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
            Neo4jClient(uri="neo4j+s://x.io", username="neo4j")


def test_reads_credentials_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEO4J_URI", "neo4j+s://env.io")
    monkeypatch.setenv("NEO4J_USERNAME", "myuser")
    monkeypatch.setenv("NEO4J_PASSWORD", "mypw")
    monkeypatch.setenv("NEO4J_DATABASE", "mydb")
    with patch("agenteperry.graph.neo4j_client.GraphDatabase") as mock_gdb:
        mock_gdb.driver.return_value = MagicMock()
        client = Neo4jClient()
    assert client._uri == "neo4j+s://env.io"
    assert client._username == "myuser"
    assert client._password == "mypw"
    assert client._database == "mydb"


# ---------------------------------------------------------------------------
# execute_read
# ---------------------------------------------------------------------------


def test_execute_read_returns_data() -> None:
    client = _make_client()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.data.return_value = [{"test": 1}, {"test": 2}]
    mock_session.run.return_value = mock_result
    # Mock session context manager
    client._driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    client._driver.session.return_value.__exit__ = MagicMock(return_value=False)

    rows = client.execute_read("RETURN 1 AS test")

    assert rows == [{"test": 1}, {"test": 2}]
    mock_session.run.assert_called_once_with("RETURN 1 AS test", {})


def test_execute_read_passes_parameters() -> None:
    client = _make_client()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.data.return_value = []
    mock_session.run.return_value = mock_result
    client._driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    client._driver.session.return_value.__exit__ = MagicMock(return_value=False)

    client.execute_read("MATCH (c:Company {ruc: $ruc})", {"ruc": "20123456789"})

    mock_session.run.assert_called_once_with(
        "MATCH (c:Company {ruc: $ruc})", {"ruc": "20123456789"}
    )


# ---------------------------------------------------------------------------
# execute_write
# ---------------------------------------------------------------------------


def test_execute_write_calls_session_run() -> None:
    client = _make_client()
    mock_session = MagicMock()
    mock_result = MagicMock()
    mock_result.data.return_value = []
    mock_session.run.return_value = mock_result
    client._driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    client._driver.session.return_value.__exit__ = MagicMock(return_value=False)

    client.execute_write("MERGE (c:Company {ruc: $ruc})", {"ruc": "20123456789"})

    mock_session.run.assert_called_once()


# ---------------------------------------------------------------------------
# execute_write_batch
# ---------------------------------------------------------------------------


def test_execute_write_batch_sends_correct_batches() -> None:
    client = _make_client()
    calls: list[dict] = []

    def fake_write(query: str, params: dict | None) -> list:
        if params:
            calls.append(params)
        return []

    client.execute_write = fake_write  # type: ignore[method-assign]

    rows = [{"ruc": str(i)} for i in range(12)]
    total = client.execute_write_batch("UNWIND $rows AS row MERGE (c:Company {ruc: row.ruc})", rows, batch_size=5)

    assert total == 12
    # 12 rows / batch_size 5 → 3 calls: 5+5+2
    assert len(calls) == 3
    assert len(calls[0]["rows"]) == 5
    assert len(calls[1]["rows"]) == 5
    assert len(calls[2]["rows"]) == 2


def test_execute_write_batch_empty_rows_does_nothing() -> None:
    client = _make_client()
    write_calls = []
    client.execute_write = lambda q, p=None: write_calls.append(p) or []  # type: ignore[method-assign]

    total = client.execute_write_batch("UNWIND $rows AS row MERGE (c:Company)", [], batch_size=500)

    assert total == 0
    assert write_calls == []


# ---------------------------------------------------------------------------
# verify_connection
# ---------------------------------------------------------------------------


def test_verify_connection_returns_true_on_correct_response() -> None:
    client = _make_client()
    client.execute_read = MagicMock(return_value=[{"test": 1}])  # type: ignore[method-assign]

    assert client.verify_connection() is True


def test_verify_connection_returns_false_on_wrong_response() -> None:
    client = _make_client()
    client.execute_read = MagicMock(return_value=[{"test": 0}])  # type: ignore[method-assign]

    assert client.verify_connection() is False


def test_verify_connection_returns_false_on_exception() -> None:
    client = _make_client()
    client.execute_read = MagicMock(side_effect=RuntimeError("connection refused"))  # type: ignore[method-assign]

    assert client.verify_connection() is False


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager_calls_close() -> None:
    client = _make_client()
    client._driver.close = MagicMock()

    with client:
        pass

    client._driver.close.assert_called_once()


def test_close_delegates_to_driver() -> None:
    client = _make_client()
    client._driver.close = MagicMock()

    client.close()

    client._driver.close.assert_called_once()
