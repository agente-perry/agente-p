"""Test SUNAT non-destructive enrichment of source_entities.company."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from agenteperry.sync.loader import enrich_companies_from_sunat, merge_sunat_metadata


def test_merge_sunat_metadata_preserves_ocds_name():
    now_iso = datetime.now(UTC).isoformat()
    existing = {
        "id": "uuid-1",
        "display_name": "OCDS NAME SAC",
        "metadata": json.dumps({"source": "ocds_peru"}),
        "sources": ["ocds_peru"],
    }
    sunat_record = {
        "entity_name": "SUNAT LEGAL NAME SAC",
        "parsed_data": {
            "estado": "ACTIVO",
            "condicion": "HABIDO",
            "ubigeo": "150101",
            "domicilio_fiscal": "AV. TEST 123",
        },
    }

    result = merge_sunat_metadata(existing, sunat_record, now_iso)

    assert result["id"] == "uuid-1"
    assert result["sources"] == ["ocds_peru", "sunat_padron"]

    metadata = json.loads(result["metadata"])
    assert metadata["ocds_name"] == "OCDS NAME SAC"
    assert metadata["sunat_razon_social"] == "SUNAT LEGAL NAME SAC"
    assert metadata["sunat_estado"] == "ACTIVO"
    assert metadata["sunat_condicion"] == "HABIDO"
    assert metadata["sunat_ubigeo"] == "150101"
    assert metadata["sunat_domicilio_fiscal"] == "AV. TEST 123"
    assert metadata["sunat_last_seen_at"] == now_iso
    assert metadata["source"] == "ocds_peru"


def test_merge_sunat_metadata_does_not_overwrite_existing_ocds_name():
    now_iso = datetime.now(UTC).isoformat()
    existing = {
        "id": "uuid-2",
        "display_name": "NEW NAME SAC",
        "metadata": json.dumps({"ocds_name": "OLD NAME SAC"}),
        "sources": ["ocds_peru"],
    }
    sunat_record = {
        "entity_name": "SUNAT NAME",
        "parsed_data": {},
    }

    result = merge_sunat_metadata(existing, sunat_record, now_iso)
    metadata = json.loads(result["metadata"])
    assert metadata["ocds_name"] == "OLD NAME SAC"


def test_merge_sunat_metadata_from_string_metadata():
    now_iso = datetime.now(UTC).isoformat()
    existing = {
        "id": "uuid-3",
        "display_name": "ENTITY SAC",
        "metadata": '{"ruc": "20123456789"}',
        "sources": '["ocds_peru"]',
    }
    sunat_record = {
        "entity_name": "SUNAT NAME",
        "parsed_data": {"estado": "ACTIVO"},
    }

    result = merge_sunat_metadata(existing, sunat_record, now_iso)
    metadata = json.loads(result["metadata"])
    assert metadata["ruc"] == "20123456789"
    assert metadata["sunat_estado"] == "ACTIVO"
    assert result["sources"] == ["ocds_peru", "sunat_padron"]


def test_enrich_companies_from_sunat_preserves_ocds_name(monkeypatch, tmp_path: Path):
    records = [
        {
            "source_code": "sunat_padron",
            "entity_ruc": "20123456789",
            "entity_name": "SUNAT LEGAL NAME SAC",
            "parsed_data": {
                "estado": "ACTIVO",
                "condicion": "HABIDO",
                "ubigeo": "150101",
                "domicilio_fiscal": "AV. TEST 123",
            },
        },
    ]
    records_path = tmp_path / "sunat_records.jsonl"
    records_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    mock_db = MagicMock()
    mock_db.execute.return_value = [
        {
            "id": "uuid-1",
            "canonical_id": "20123456789",
            "display_name": "OCDS NAME SAC",
            "metadata": json.dumps({"source": "ocds_peru"}),
            "sources": ["ocds_peru"],
        }
    ]
    monkeypatch.setattr("agenteperry.sync.loader.db", mock_db)

    metrics = enrich_companies_from_sunat(records_path)

    assert metrics["companies_seen"] == 1
    assert metrics["companies_enriched"] == 1
    assert metrics["companies_unmatched"] == 0
    assert metrics["records_skipped"] == 0
    assert metrics["errors"] == 0

    assert mock_db.execute_batch.called
    call_args = mock_db.execute_batch.call_args[0]
    query = call_args[0]
    batch = call_args[1]

    assert "UPDATE source_entities" in query
    assert len(batch) == 1
    updated = batch[0]
    assert updated["id"] == "uuid-1"
    metadata = json.loads(updated["metadata"])
    assert metadata["ocds_name"] == "OCDS NAME SAC"
    assert metadata["sunat_razon_social"] == "SUNAT LEGAL NAME SAC"
    assert updated["sources"] == ["ocds_peru", "sunat_padron"]


def test_enrich_companies_skips_invalid_ruc(monkeypatch, tmp_path: Path):
    records = [
        {
            "source_code": "sunat_padron",
            "entity_ruc": "12345",  # invalid
            "entity_name": "SHORT RUC SAC",
            "parsed_data": {"estado": "ACTIVO"},
        },
        {
            "source_code": "ocds_peru",
            "entity_ruc": "20987654321",
            "entity_name": "NOT SUNAT",
            "parsed_data": {},
        },
    ]
    records_path = tmp_path / "sunat_records.jsonl"
    records_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    mock_db = MagicMock()
    mock_db.execute.return_value = []
    monkeypatch.setattr("agenteperry.sync.loader.db", mock_db)

    metrics = enrich_companies_from_sunat(records_path)

    assert metrics["companies_seen"] == 0
    assert metrics["companies_enriched"] == 0
    assert metrics["records_skipped"] == 2
    assert not mock_db.execute_batch.called


def test_enrich_companies_counts_unmatched(monkeypatch, tmp_path: Path):
    records = [
        {
            "source_code": "sunat_padron",
            "entity_ruc": "20123456789",
            "entity_name": "UNKNOWN COMPANY SAC",
            "parsed_data": {"estado": "ACTIVO"},
        },
    ]
    records_path = tmp_path / "sunat_records.jsonl"
    records_path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    mock_db = MagicMock()
    mock_db.execute.return_value = []  # no match
    monkeypatch.setattr("agenteperry.sync.loader.db", mock_db)

    metrics = enrich_companies_from_sunat(records_path)

    assert metrics["companies_seen"] == 1
    assert metrics["companies_enriched"] == 0
    assert metrics["companies_unmatched"] == 1
    assert not mock_db.execute_batch.called
