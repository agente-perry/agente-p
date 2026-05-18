"""Tests for source record chunk generation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agenteperry.sync.chunks import build_contract_chunk_text, upsert_contract_chunks


def test_build_contract_chunk_text_includes_traceable_fields() -> None:
    text = build_contract_chunk_text({
        "external_id": "ocds-1",
        "entity_name": "MUNICIPALIDAD TEST",
        "supplier_name": "PROVEEDOR TEST SAC",
        "monto": 1234.5,
        "fecha": "2026-01-01",
        "parsed_data": {"procedure_type": "Concurso", "tender_id": "T-1", "award_id": "A-1"},
        "evidence_quote": "PROVEEDOR TEST SAC gano contrato con MUNICIPALIDAD TEST por 1234.50.",
    })

    assert "ocds-1" in text
    assert "MUNICIPALIDAD TEST" in text
    assert "PROVEEDOR TEST SAC" in text
    assert "PEN 1234.5" in text
    assert "Tender ID: T-1" in text
    assert "Award ID: A-1" in text


@patch("agenteperry.sync.chunks.db")
def test_upsert_contract_chunks(mock_db: MagicMock) -> None:
    mock_db.execute.return_value = [{
        "id": "11111111-1111-1111-1111-111111111111",
        "external_id": "ocds-1",
        "entity_name": "MUNICIPALIDAD TEST",
        "entity_ruc": None,
        "supplier_name": "PROVEEDOR TEST SAC",
        "supplier_ruc": "20123456789",
        "monto": 1234.5,
        "fecha": "2026-01-01",
        "period_year": 2026,
        "parsed_data": {"procedure_type": "Concurso"},
        "evidence_quote": "evidencia",
        "checksum": "abc",
        "raw_path": "data/scraped/ocds/records.jsonl",
        "source_url": None,
        "source_code": "ocds_peru",
    }]
    mock_db.execute_batch = MagicMock()

    count = upsert_contract_chunks(limit=1)

    assert count == 1
    mock_db.execute_batch.assert_called_once()
    params = mock_db.execute_batch.call_args[0][1]
    assert params[0]["source_type"] == "contrato"
    assert params[0]["external_ref"] == "ocds-1"
    assert "PROVEEDOR TEST SAC" in params[0]["text_content"]
