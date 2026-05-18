"""Tests for tdr/loader.py — pipeline sync to Postgres."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from agenteperry.tdr.loader import (
    _load_jsonl,
    load_pipeline_json,
    upsert_tdr_chunks,
    upsert_tdr_document,
    upsert_tdr_embeddings,
    upsert_tdr_flags,
    upsert_tdr_pages,
)
from agenteperry.tdr.models import TdrChunk, TdrDocumentMetadata, TdrFlag, TdrPage, TdrSeverity


class TestLoadJsonl:
    def test_loads_records(self, tmp_path: Path) -> None:
        path = tmp_path / "records.jsonl"
        path.write_text('{"external_id": "TDR-001"}\n{"external_id": "TDR-002"}\n', encoding="utf-8")
        records = _load_jsonl(path)
        assert len(records) == 2
        assert records[0]["external_id"] == "TDR-001"


class TestUpsertTdrDocument:
    @patch("agenteperry.tdr.loader.db")
    def test_returns_uuid(self, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": "uuid-123"}]
        meta = TdrDocumentMetadata(external_id="TDR-001", title="Consultoria")
        result = upsert_tdr_document(meta)
        assert result == "uuid-123"

    @patch("agenteperry.tdr.loader.db")
    def test_calls_execute_not_execute_batch(self, mock_db: MagicMock) -> None:
        mock_db.execute.return_value = [{"id": "uuid-123"}]
        meta = TdrDocumentMetadata(external_id="TDR-001", title="Test")
        upsert_tdr_document(meta)
        mock_db.execute.assert_called_once()
        mock_db.execute_batch.assert_not_called()


class TestUpsertTdrPages:
    @patch("agenteperry.tdr.loader.db")
    def test_calls_execute_batch(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()
        pages = [
            TdrPage(page_number=1, text_content="Page 1 text"),
            TdrPage(page_number=2, text_content="Page 2 text"),
        ]
        count = upsert_tdr_pages("uuid-123", pages)
        assert count == 2
        mock_db.execute_batch.assert_called_once()
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["page_number"] == 1
        assert params[1]["page_number"] == 2

    @patch("agenteperry.tdr.loader.db")
    def test_returns_zero_for_empty(self, mock_db: MagicMock) -> None:
        count = upsert_tdr_pages("uuid-123", [])
        assert count == 0
        mock_db.execute_batch.assert_not_called()


class TestUpsertTdrChunks:
    @patch("agenteperry.tdr.loader.db")
    def test_serializes_metadata_as_json(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()
        chunks = [
            TdrChunk(
                tdr_id="uuid-123",
                chunk_index=0,
                page_start=1,
                page_end=1,
                text="Test chunk",
                metadata={"char_start": 0, "char_end": 50},
            )
        ]
        upsert_tdr_chunks("uuid-123", chunks)
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["metadata"] == '{"char_start": 0, "char_end": 50}'


class TestUpsertTdrFlags:
    @patch("agenteperry.tdr.loader.db")
    def test_maps_all_fields(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()
        flags = [
            TdrFlag(
                tdr_id="uuid-123",
                flag_code="EXCESSIVE_DOCUMENT_REQUIREMENT",
                flag_name="Requisito documental excesivo",
                severity=TdrSeverity.MEDIUM,
                score_contribution=15,
                evidence_quote="El documento exige 500 paginas",
                page_number=1,
                explanation="Requiere revision",
                detection_method="rule",
                rule_id="TDR-R001",
            )
        ]
        count = upsert_tdr_flags("uuid-123", flags)
        assert count == 1
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["flag_code"] == "EXCESSIVE_DOCUMENT_REQUIREMENT"
        assert params[0]["severity"] == "MEDIUM"


class TestUpsertTdrEmbeddings:
    @patch("agenteperry.tdr.loader.db")
    def test_converts_embedding_list_to_string(self, mock_db: MagicMock) -> None:
        mock_db.execute_batch = MagicMock()
        embeds = [{"chunk_id": "chunk-uuid", "embedding": [0.1, 0.2, 0.3]}]
        upsert_tdr_embeddings(embeds)
        params = mock_db.execute_batch.call_args[0][1]
        assert params[0]["embedding"] == "[0.1,0.2,0.3]"


class TestLoadPipelineJson:
    def test_loads_all_stages(self, tmp_path: Path) -> None:
        manifest = tmp_path / "manifest.jsonl"
        manifest.write_text('{"external_id": "TDR-001", "title": "Test"}\n', encoding="utf-8")

        pages_file = tmp_path / "pages.json"
        pages_file.write_text(json.dumps({"pages": [{"page_number": 1, "text_content": "p1"}]}), encoding="utf-8")

        chunks_file = tmp_path / "chunks.json"
        chunks_file.write_text(
            json.dumps({"chunks": [{"chunk_index": 0, "page_start": 1, "page_end": 1, "text": "c1", "metadata": {}}]}),
            encoding="utf-8",
        )

        flags_file = tmp_path / "flags.json"
        flags_file.write_text(
            json.dumps({"flags": [
                {"flag_code": "R001", "flag_name": "X", "severity": "MEDIUM",
                 "score_contribution": 15, "evidence_quote": "x", "page_number": 1,
                 "explanation": "x", "rule_id": "R001", "tdr_id": "uuid-123"}
            ]}),
            encoding="utf-8",
        )

        with patch("agenteperry.tdr.loader.upsert_tdr_document", return_value="uuid-123") as m_doc, \
             patch("agenteperry.tdr.loader.upsert_tdr_pages", return_value=1) as m_pages, \
             patch("agenteperry.tdr.loader.upsert_tdr_chunks", return_value=3) as m_chunks, \
             patch("agenteperry.tdr.loader.upsert_tdr_flags", return_value=1) as m_flags:
            counts = load_pipeline_json(
                manifest,
                pages_json=pages_file,
                chunks_json=chunks_file,
                flags_json=flags_file,
            )

        assert counts["tdr_documents"] == 1
        assert counts["tdr_pages"] == 1
        assert counts["tdr_chunks"] == 3
        assert counts["tdr_flags"] == 1
        assert m_doc.call_count == 4
        assert m_pages.call_count == 1
        assert m_chunks.call_count == 1
        assert m_flags.call_count == 1