"""Test SUNAT collector end-to-end using the fixture sample."""

from pathlib import Path
from unittest.mock import MagicMock

from agenteperry.cli import _build_sunat_audit
from agenteperry.collectors.sunat import (
    SUNAT_PADRON_URL,
    iter_sunat_rows,
    sunat_row_to_result,
)

FIXTURE_PATH = Path(__file__).with_name("fixtures") / "sunat_padron_sample.txt"


def test_fixture_exists():
    assert FIXTURE_PATH.exists(), f"Fixture not found at {FIXTURE_PATH}"


def test_fixture_parses_into_rows():
    rows = list(iter_sunat_rows(FIXTURE_PATH))
    assert len(rows) >= 20
    assert len(rows) <= 55

    for row in rows:
        assert "ruc" in row
        assert "razon_social" in row
        assert "estado" in row
        assert "condicion" in row
        assert "ubigeo" in row


def test_fixture_rucs_are_all_valid():
    rows = list(iter_sunat_rows(FIXTURE_PATH))
    assert len(rows) > 0
    for row in rows:
        ruc = row.get("ruc", "").strip()
        assert len(ruc) == 11, f"Invalid RUC length in fixture: {ruc!r}"
        assert ruc.isdigit(), f"Non-digit RUC in fixture: {ruc!r}"


def test_fixture_has_encoding_characters():
    rows = list(iter_sunat_rows(FIXTURE_PATH))
    names = [r.get("razon_social", "") for r in rows]
    joined = " ".join(names)
    assert "Ñ" in joined or "\u00D1" in joined, "Fixture should contain Ñ"


def test_fixture_has_estado_condicion():
    rows = list(iter_sunat_rows(FIXTURE_PATH))
    estados = {r.get("estado", "").strip() for r in rows}
    condiciones = {r.get("condicion", "").strip() for r in rows}

    assert "ACTIVO" in estados or "BAJA" in estados
    assert "HABIDO" in condiciones or "NO HABIDO" in condiciones


def test_sunat_row_to_result_maps_fields():
    row = {
        "ruc": "20123456789",
        "razon_social": "ACME CONSTRUCTORES S.A.C.",
        "estado": "ACTIVO",
        "condicion": "HABIDO",
        "ubigeo": "150101",
        "tipo_via": "AV.",
        "nombre_via": "JAVIER PRADO ESTE",
        "codigo_zona": "Z.I.",
        "tipo_zona": "RINGO",
        "numero": "750",
        "interior": "TORRE A",
        "lote": "",
        "departamento": "1001",
        "manzana": "L",
        "kilometro": "2.50",
    }
    result = sunat_row_to_result(row, None, "abc")
    record = result.to_record()

    assert record["source_code"] == "sunat_padron"
    assert record["record_type"] == "company"
    assert record["entity_ruc"] == "20123456789"
    assert record["entity_name"] == "ACME CONSTRUCTORES S.A.C."
    assert record["region"] == "15"
    assert record["source_url"] == SUNAT_PADRON_URL

    parsed = record["parsed_data"]
    assert parsed["estado"] == "ACTIVO"
    assert parsed["condicion"] == "HABIDO"
    assert parsed["ubigeo"] == "150101"
    assert "JAVIER PRADO ESTE" in (parsed["domicilio_fiscal"] or "")


def test_sunat_fixture_smoke_e2e():
    """Parse full fixture and convert to records."""
    rows = list(iter_sunat_rows(FIXTURE_PATH))
    records = [sunat_row_to_result(row, FIXTURE_PATH, "demo_checksum").to_record() for row in rows]

    assert len(records) == len(rows)
    valid_rucs = [r for r in records if r["entity_ruc"] and len(str(r["entity_ruc"])) == 11]
    assert len(valid_rucs) == len(records), "All fixture rows should have valid 11-digit RUCs"

    active = [r for r in records if r["parsed_data"].get("estado") == "ACTIVO"]
    baja = [r for r in records if r["parsed_data"].get("estado") == "BAJA"]
    no_habido = [r for r in records if r["parsed_data"].get("condicion") == "NO HABIDO"]

    assert len(active) > 0
    assert len(baja) > 0
    assert len(no_habido) > 0

    # Every record should have evidence_quote
    for r in records:
        assert r["evidence_quote"]


def test_build_sunat_audit_counts(monkeypatch):
    from agenteperry.db import client as db_client_module

    mock_db = MagicMock()
    mock_db.execute.return_value = [{"c": 0}]
    monkeypatch.setattr(db_client_module, "DbClient", lambda: mock_db)

    records = [
        {"entity_ruc": "20123456789", "entity_name": "ACME SAC", "parsed_data": {"estado": "ACTIVO", "condicion": "HABIDO", "ubigeo": "150101"}},
        {"entity_ruc": "20999887766", "entity_name": "BAJA SAC", "parsed_data": {"estado": "BAJA", "condicion": "NO HABIDO", "ubigeo": "070101"}},
        {"entity_ruc": "12345", "entity_name": "SHORT RUC", "parsed_data": {"estado": "ACTIVO", "condicion": "HABIDO"}},
        {"entity_name": "NO RUC", "parsed_data": {"estado": "ACTIVO"}},
    ]

    audit = _build_sunat_audit(
        records=records,
        entities=[],
        relationships=[],
        enrichment_metrics={
            "companies_seen": 2,
            "companies_enriched": 1,
            "companies_unmatched": 1,
            "records_skipped": 1,
            "errors": 0,
        },
    )

    assert audit["source_code"] == "sunat_padron"
    assert audit["total_records"] == 4
    assert audit["with_valid_ruc"] == 2
    assert audit["with_name"] == 4
    assert audit["with_estado"] == 4
    assert audit["with_condicion"] == 3
    assert audit["with_ubigeo"] == 2
    assert audit["active_count"] == 3
    assert audit["baja_count"] == 1
    assert audit["no_habido_count"] == 1
    assert audit["companies_enriched"] == 1
    assert audit["companies_unmatched"] == 1
    assert "run_at" in audit
    assert "ocds_companies_total" in audit