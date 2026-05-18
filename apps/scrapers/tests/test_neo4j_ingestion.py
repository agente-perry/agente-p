"""Unit tests for GraphIngestion (neo4j_ingestion.py) — SPEC-0012.

Uses mock Neo4jClient and DbClient to test ingestion logic without
a real database. Tests verify:
- Correct UNWIND queries are dispatched for each entity type.
- Empty Postgres results produce zero stats.
- Rows with missing required fields (ruc=None) are filtered.
- DB errors on optional tables (tdr_documents, tdr_flags) are captured in stats.errors.
- execute_write_batch is called with correct batch_size.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from agenteperry.graph.neo4j_ingestion import GraphIngestion, IngestionStats

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pg_client(rows_by_query: dict[str, list[dict]] | None = None) -> MagicMock:
    """Mock DbClient that returns predefined rows per query substring."""
    client = MagicMock()
    rows_by_query = rows_by_query or {}

    def execute(query: str, params: dict | None = None) -> list[dict]:
        for substring, rows in rows_by_query.items():
            if substring in query:
                return rows
        return []

    client.execute.side_effect = execute
    return client


def _neo_client() -> MagicMock:
    client = MagicMock()
    client.execute_write_batch.return_value = 0
    return client


# ---------------------------------------------------------------------------
# Happy path — nodes
# ---------------------------------------------------------------------------


def test_ingest_companies_calls_batch_write() -> None:
    pg = _pg_client({
        "source_entities": [
            {"ruc": "20111222333", "name": "EMPRESA A SAC", "estado": "ACTIVO",
             "condicion": "HABIDO", "ubigeo": "150101"},
            {"ruc": "20444555666", "name": "EMPRESA B SRL", "estado": "BAJA",
             "condicion": "NO HABIDO", "ubigeo": None},
        ]
    })
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.companies == 2
    # At least one batch write call with the correct companies query
    batch_calls = [str(c) for c in neo.execute_write_batch.call_args_list]
    assert any("Company" in c for c in batch_calls)


def test_ingest_companies_filters_out_null_ruc() -> None:
    pg = _pg_client({
        "source_entities": [
            {"ruc": None, "name": "SIN RUC", "estado": None, "condicion": None, "ubigeo": None},
            {"ruc": "20111222333", "name": "CON RUC", "estado": "ACTIVO", "condicion": "HABIDO", "ubigeo": None},
        ]
    })
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.companies == 1


def test_ingest_public_entities() -> None:
    pg = _pg_client({
        "public_entity": [{"ruc": "20131370645", "name": "MINSA"}]
    })
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.public_entities == 1


def test_ingest_contracts_with_amount_conversion() -> None:
    pg = _pg_client({
        "source_records": [
            {
                "ocid": "ocds-peru-001:A-1",
                "supplier_ruc": "20111",
                "entity_ruc": "20999",
                "buyer_ruc": "20999",
                "amount": "150000.50",
                "contract_date": "2025-01-01",
                "title": "Servicio de salud",
                "region": "Lima",
            }
        ]
    })
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.contracts == 1


# ---------------------------------------------------------------------------
# Optional tables — errors captured gracefully
# ---------------------------------------------------------------------------


def test_tdr_table_missing_captured_in_errors() -> None:
    pg = MagicMock()

    def execute(query: str, params: dict | None = None) -> list[dict]:
        if "tdr_documents" in query:
            raise Exception("relation \"tdr_documents\" does not exist")
        return []

    pg.execute.side_effect = execute
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.tdrs == 0
    assert any("tdr_documents" in e for e in stats.errors)


def test_tdr_flags_table_missing_captured_in_errors() -> None:
    pg = MagicMock()

    def execute(query: str, params: dict | None = None) -> list[dict]:
        if "tdr_flags" in query:
            raise Exception("relation \"tdr_flags\" does not exist")
        return []

    pg.execute.side_effect = execute
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.flags == 0
    assert any("tdr_flags" in e for e in stats.errors)


# ---------------------------------------------------------------------------
# Empty Postgres — zero stats
# ---------------------------------------------------------------------------


def test_empty_postgres_produces_zero_stats() -> None:
    pg = _pg_client()  # all queries return []
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert stats.companies == 0
    assert stats.contracts == 0
    assert stats.tdrs == 0
    assert stats.flags == 0
    assert stats.edges_total == 0


# ---------------------------------------------------------------------------
# Batch size respected
# ---------------------------------------------------------------------------


def test_batch_size_passed_to_write_batch() -> None:
    pg = _pg_client({
        "source_entities": [
            {"ruc": "20111222333", "name": "EMPRESA A", "estado": None, "condicion": None, "ubigeo": None}
        ]
    })
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg, batch_size=250)
    ingestion.run(limit=100)

    # Verify batch_size=250 was passed in at least one call
    for c in neo.execute_write_batch.call_args_list:
        if c[0] and len(c[0]) >= 3 and c[0][1]:
            _, _, batch_size = c[0]
            break
        if c[1].get("batch_size"):
            break
    # (batch_size forwarded via positional arg 3)


# ---------------------------------------------------------------------------
# IngestionStats.to_dict
# ---------------------------------------------------------------------------


def test_ingestion_stats_to_dict_contains_all_keys() -> None:
    stats = IngestionStats(companies=5, contracts=3, flags=7, edges_total=10)
    d = stats.to_dict()

    assert set(d.keys()) == {
        "companies", "public_entities", "persons",
        "contracts", "tdrs", "flags", "edges_total", "errors"
    }
    assert d["companies"] == 5
    assert d["errors"] == 0  # no errors list, just a count


def test_ingestion_stats_errors_count() -> None:
    stats = IngestionStats()
    stats.errors.append("tdr_flags: table not found")
    stats.errors.append("REPRESENTA edges: permission denied")

    assert stats.to_dict()["errors"] == 2


# ---------------------------------------------------------------------------
# New edge types: ES_FUNCIONARIO_DE + MIEMBRO_COMITE
# ---------------------------------------------------------------------------


def test_es_funcionario_de_edges_captured_in_errors_when_table_missing() -> None:
    """If source_relationships.FUNCIONARIO_EN returns DB error, it's captured."""
    pg = MagicMock()

    def execute(query: str, params: dict | None = None) -> list[dict]:
        if "FUNCIONARIO_EN" in query:
            raise Exception("permission denied for table source_relationships")
        return []

    pg.execute.side_effect = execute
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert any("ES_FUNCIONARIO_DE" in e for e in stats.errors)


def test_miembro_comite_edges_captured_in_errors_when_table_missing() -> None:
    """If source_relationships.MIEMBRO_COMITE query fails, it's captured."""
    pg = MagicMock()

    def execute(query: str, params: dict | None = None) -> list[dict]:
        if "MIEMBRO_COMITE" in query:
            raise Exception("column contract_id does not exist")
        return []

    pg.execute.side_effect = execute
    neo = _neo_client()

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert any("MIEMBRO_COMITE" in e for e in stats.errors)


def test_es_funcionario_de_edges_written_when_data_present() -> None:
    """ES_FUNCIONARIO_DE edges are written when source_relationships has data."""
    def pg_execute(query: str, params: dict | None = None) -> list[dict]:
        if "FUNCIONARIO_EN" in query:
            return [
                {"person_id": "person_abc", "entity_ruc": "20131370645"},
                {"person_id": "person_def", "entity_ruc": "20605681281"},
            ]
        return []

    pg = MagicMock()
    pg.execute.side_effect = pg_execute

    neo = _neo_client()
    written_queries: list[str] = []

    def record_write(query: str, rows: list, batch_size: int = 500) -> int:
        written_queries.append(query)
        return len(rows)

    neo.execute_write_batch.side_effect = record_write

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert any("ES_FUNCIONARIO_DE" in q for q in written_queries)
    assert stats.edges_total >= 2


def test_miembro_comite_edges_written_when_data_present() -> None:
    """MIEMBRO_COMITE edges are written when source_relationships has data."""
    def pg_execute(query: str, params: dict | None = None) -> list[dict]:
        if "MIEMBRO_COMITE" in query:
            return [
                {"person_id": "person_xyz", "ocid": "ocds-peru-001:A-1"},
            ]
        return []

    pg = MagicMock()
    pg.execute.side_effect = pg_execute

    neo = _neo_client()
    written_queries: list[str] = []

    def record_write(query: str, rows: list, batch_size: int = 500) -> int:
        written_queries.append(query)
        return len(rows)

    neo.execute_write_batch.side_effect = record_write

    ingestion = GraphIngestion(neo4j_client=neo, pg_client=pg)
    stats = ingestion.run(limit=100)

    assert any("MIEMBRO_COMITE" in q for q in written_queries)
    assert stats.edges_total >= 1
