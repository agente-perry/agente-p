"""Tests for sync/loader.py using mocked DbClient."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from agenteperry.sync.loader import (
    _load_jsonl,
    _make_upsert_sql,
    _normalize_record,
    run_full_sync,
    upsert_entities,
    upsert_relationships,
    upsert_source_records,
)


class TestMakeUpsertSql:
    def test_basic_upsert_sql(self) -> None:
        sql = _make_upsert_sql("source_records", ["external_id", "title", "monto"], on_conflict="external_id")
        assert "INSERT INTO source_records" in sql
        assert "ON CONFLICT (external_id)" in sql
        assert "EXCLUDED.external_id" in sql
        assert "EXCLUDED.monto" in sql

    def test_upsert_sql_set_clause(self) -> None:
        sql = _make_upsert_sql("source_entities", ["canonical_id", "display_name"], on_conflict="canonical_id")
        assert "canonical_id = EXCLUDED.canonical_id" in sql
        assert "display_name = EXCLUDED.display_name" in sql


class TestNormalizeRecord:
    def test_passes_through_common_fields(self) -> None:
        record = {"external_id": "TDR-001", "title": "Consultoria", "source_code": "seace_oece", "category": "contratos"}
        normalized = _normalize_record(record)
        assert normalized["external_id"] == "TDR-001"
        assert normalized["title"] == "Consultoria"
        assert normalized["source_code"] == "seace_oece"

    def test_json_dumps_raw_data_and_parsed_data(self) -> None:
        record = {
            "external_id": "TDR-001",
            "raw_data": {"original": "text"},
            "parsed_data": {"cleaned": "text"},
            "metadata": {"portal": "OECE"},
        }
        normalized = _normalize_record(record)
        assert isinstance(normalized["raw_data"], str)
        assert json.loads(normalized["raw_data"]) == {"original": "text"}
        assert isinstance(normalized["parsed_data"], str)
        assert json.loads(normalized["parsed_data"]) == {"cleaned": "text"}

    def test_json_dumps_lists(self) -> None:
        record = {"external_id": "TDR-001", "sources": ["src1", "src2"], "red_flags": ["proveedor_recurrente"]}
        normalized = _normalize_record(record)
        assert isinstance(normalized["sources"], str)
        assert json.loads(normalized["sources"]) == ["src1", "src2"]

    def test_monto_converts_to_float(self) -> None:
        record = {"external_id": "TDR-001", "monto": "150000.50"}
        normalized = _normalize_record(record)
        assert normalized["monto"] == 150000.50

    def test_skips_none_values(self) -> None:
        record = {"external_id": "TDR-001", "title": None, "monto": None}
        normalized = _normalize_record(record)
        assert "title" not in normalized
        assert "monto" not in normalized


class TestLoadJsonl:
    def test_loads_records(self, tmp_path: Path) -> None:
        path = tmp_path / "records.jsonl"
        path.write_text('{"external_id": "A"}\n{"external_id": "B"}\n', encoding="utf-8")
        records = _load_jsonl(path)
        assert len(records) == 2
        assert records[0]["external_id"] == "A"
        assert records[1]["external_id"] == "B"

    def test_skips_empty_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "records.jsonl"
        path.write_text('{"external_id": "A"}\n\n{"external_id": "B"}\n', encoding="utf-8")
        records = _load_jsonl(path)
        assert len(records) == 2


class TestUpsertSourceRecords:
    @patch("agenteperry.sync.loader.db")
    def test_calls_execute_batch(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()

        path = Path("/tmp/records.jsonl")
        path.write_text('{"external_id": "R1", "title": "Test", "source_code": "test"}\n', encoding="utf-8")

        count = upsert_source_records(path)

        assert count == 1
        mock_db.execute_batch.assert_called_once()
        call_args = mock_db.execute_batch.call_args
        query = call_args[0][0]
        params = call_args[0][1]
        assert "INSERT INTO source_records" in query
        assert params[0]["external_id"] == "R1"

    @patch("agenteperry.sync.loader.db")
    def test_returns_zero_for_empty_file(self, mock_db: MagicMock) -> None:
        path = Path("/tmp/empty.jsonl")
        path.write_text("\n\n", encoding="utf-8")
        count = upsert_source_records(path)
        assert count == 0
        mock_db.execute_batch.assert_not_called()


class TestUpsertEntities:
    @patch("agenteperry.sync.loader.db")
    def test_upserts_entities_from_graph_json(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()

        graph_path = Path("/tmp/graph.json")
        graph_path.write_text(
            json.dumps({
                "entities": [
                    {
                        "entity_type": "company",
                        "canonical_id": "CANONICAL-1",
                        "display_name": "Proveedor ABC SAC",
                        "metadata": {"ruc": "20987654321"},
                        "sources": ["seace_oece"],
                    }
                ],
                "relationships": [],
            }),
            encoding="utf-8",
        )

        count = upsert_entities(graph_path)
        assert count == 1
        mock_db.execute_batch.assert_called_once()
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["canonical_id"] == "CANONICAL-1"

    @patch("agenteperry.sync.loader.db")
    def test_returns_zero_when_no_entities(self, mock_db: MagicMock) -> None:
        path = Path("/tmp/empty_graph.json")
        path.write_text(json.dumps({"entities": [], "relationships": []}), encoding="utf-8")
        count = upsert_entities(path)
        assert count == 0


class TestUpsertRelationships:
    @patch("agenteperry.sync.loader.db")
    def test_upserts_relationships_from_graph_json(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()
        mock_db.execute = MagicMock(return_value=[
            {"id": "11111111-1111-1111-1111-111111111111", "canonical_id": "ENT-1"},
            {"id": "22222222-2222-2222-2222-222222222222", "canonical_id": "ENT-2"},
        ])

        graph_path = Path("/tmp/graph.json")
        graph_path.write_text(
            json.dumps({
                "entities": [],
                "relationships": [
                    {
                        "source_canonical_id": "ENT-1",
                        "target_canonical_id": "ENT-2",
                        "rel_type": "GANO_CONTRATO",
                        "properties": {"monto": 50000, "year": 2026},
                        "data_source": "seace_oece",
                    }
                ],
            }),
            encoding="utf-8",
        )

        count = upsert_relationships(graph_path)
        assert count == 1
        mock_db.execute_batch.assert_called_once()
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["rel_type"] == "GANO_CONTRATO"
        assert params[0]["source_id"] == "11111111-1111-1111-1111-111111111111"
        assert params[0]["target_id"] == "22222222-2222-2222-2222-222222222222"


class TestRunFullSync:
    def test_runs_all_stages_mocked(self, tmp_path: Path) -> None:
        records_path = tmp_path / "records.jsonl"
        records_path.write_text('{"external_id": "R1", "title": "Test", "source_code": "test"}\n', encoding="utf-8")
        graph_path = tmp_path / "graph.json"
        graph_path.write_text(
            json.dumps({
                "entities": [{"entity_type": "company", "canonical_id": "E1", "display_name": "Test"}],
                "relationships": [],
            }),
            encoding="utf-8",
        )
        with patch("agenteperry.sync.loader.upsert_source_records", return_value=10) as m1, \
             patch("agenteperry.sync.loader.upsert_entities", return_value=5) as m2, \
             patch("agenteperry.sync.loader.upsert_relationships", return_value=7) as m3:
            counts = run_full_sync(records_path, graph_path)
        assert counts["source_records"] == 10
        assert counts["source_entities"] == 5
        assert counts["source_relationships"] == 7
        m1.assert_called_once_with(records_path)
        m2.assert_called_once_with(graph_path)
        m3.assert_called_once_with(graph_path)

    def test_skips_graph_when_none(self, tmp_path: Path) -> None:
        records_path = tmp_path / "records.jsonl"
        records_path.write_text('{"external_id": "R1"}\n', encoding="utf-8")
        with patch("agenteperry.sync.loader.upsert_source_records", return_value=3):
            counts = run_full_sync(records_path, graph_json=None)
        assert counts["source_records"] == 3
        assert "source_entities" not in counts
        assert "source_relationships" not in counts