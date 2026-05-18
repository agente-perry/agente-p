"""Test source pipeline e2e including audit generation."""

from agenteperry.cli import _build_audit


def test_build_audit_counts():
    records = [
        {"record_type": "contract", "entity_ruc": "20123456789", "supplier_ruc": "20987654321", "monto": 100.0, "region": "LIMA", "external_id": "c1", "checksum": "abc"},
        {"record_type": "contract", "entity_ruc": "20123456789", "supplier_ruc": None, "monto": None, "region": None, "external_id": "c2", "checksum": "def"},
        {"record_type": "procedure", "entity_ruc": "20123456789", "supplier_ruc": None, "monto": 200.0, "region": "AREQUIPA", "external_id": "p1", "checksum": "ghi"},
    ]
    audit = _build_audit(records=records, entities=[], relationships=[])

    assert audit["total_records"] == 3
    assert audit["contracts_count"] == 2
    assert audit["procedures_count"] == 1
    assert audit["with_entity_ruc"] == 3
    assert audit["with_supplier_ruc"] == 1
    assert audit["with_monto"] == 2
    assert audit["with_region"] == 2
    assert audit["with_external_id"] == 3
    assert audit["with_checksum"] == 3
    assert "run_at" in audit


def test_build_audit_with_entities_and_rels():
    records = [
        {"record_type": "contract", "entity_ruc": "20123456789", "supplier_ruc": "20987654321", "monto": 100.0, "region": "LIMA", "external_id": "c1", "checksum": "abc"},
    ]
    entities = [
        {"entity_type": "public_entity", "canonical_id": "20123456789", "display_name": "Entity A"},
        {"entity_type": "company", "canonical_id": "20987654321", "display_name": "Company B"},
    ]
    relationships = [
        {"source_canonical_id": "20987654321", "target_canonical_id": "20123456789", "rel_type": "GANO_CONTRATO", "properties": {"external_id": "c1"}},
    ]
    audit = _build_audit(records=records, entities=entities, relationships=relationships, chunks_count=5)

    assert audit["entities_created"] == 2
    assert audit["relationships_created"] == 1
    assert audit["document_chunks_created"] == 5
