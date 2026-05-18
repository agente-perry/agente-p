from agenteperry.graph.mapping import map_record_to_graph, map_records_to_graph
from agenteperry.graph.models import EntityType, RelType


def test_maps_contract_record_to_entities_and_relationships():
    mapped = map_record_to_graph(
        {
            "source_code": "ocds_peru",
            "record_type": "contract",
            "external_id": "ocds-test-1:A-1",
            "entity_name": "Municipalidad Demo",
            "entity_ruc": "20123456789",
            "supplier_name": "Proveedor Demo SAC",
            "supplier_ruc": "20987654321",
            "monto": 950.5,
            "fecha": "2026-01-20",
            "evidence_quote": "Proveedor Demo SAC gano contrato.",
        }
    )

    assert {entity.entity_type for entity in mapped.entities} == {
        EntityType.PUBLIC_ENTITY,
        EntityType.COMPANY,
    }
    assert {relationship.rel_type for relationship in mapped.relationships} == {
        RelType.GANO_CONTRATO,
        RelType.COMPRO_A,
    }
    assert mapped.relationships[0].properties["external_id"] == "ocds-test-1:A-1"


def test_maps_sunat_company_record_to_company_entity():
    mapped = map_record_to_graph(
        {
            "source_code": "sunat_padron",
            "record_type": "company",
            "entity_name": "Proveedor Demo SAC",
            "entity_ruc": "20987654321",
            "parsed_data": {"estado": "ACTIVO", "condicion": "HABIDO"},
        }
    )

    assert len(mapped.entities) == 1
    entity = mapped.entities[0]
    assert entity.entity_type == EntityType.COMPANY
    assert entity.canonical_id == "20987654321"
    assert entity.metadata["estado"] == "ACTIVO"


def test_batch_mapping_deduplicates_entities():
    mapped = map_records_to_graph(
        [
            {
                "source_code": "sunat_padron",
                "record_type": "company",
                "entity_name": "Proveedor Demo SAC",
                "entity_ruc": "20987654321",
                "parsed_data": {"estado": "ACTIVO"},
            },
            {
                "source_code": "ocds_peru",
                "record_type": "contract",
                "external_id": "ocds-test-1:A-1",
                "entity_name": "Municipalidad Demo",
                "entity_ruc": "20123456789",
                "supplier_name": "Proveedor Demo SAC",
                "supplier_ruc": "20987654321",
                "monto": 950.5,
            },
        ]
    )

    company_entities = [
        entity for entity in mapped.entities if entity.canonical_id == "20987654321"
    ]
    assert len(company_entities) == 1
    assert set(company_entities[0].sources) == {"ocds_peru", "sunat_padron"}
    assert len(mapped.relationships) == 2


def test_maps_oece_committee_member_to_person_relationship():
    mapped = map_record_to_graph(
        {
            "source_code": "seace_oece",
            "record_type": "committee_member",
            "external_id": "comites:AS-9:Juan Perez",
            "entity_name": "Municipalidad Demo",
            "entity_ruc": "20123456789",
            "parsed_data": {
                "miembro_comite": "Juan Perez",
                "cargo_comite": "Presidente",
                "codigo_proceso": "AS-9",
            },
            "evidence_quote": "OECE/SEACE registra a Juan Perez en el comite.",
        }
    )

    assert any(entity.entity_type == EntityType.PERSON for entity in mapped.entities)
    assert any(entity.entity_type == EntityType.PUBLIC_ENTITY for entity in mapped.entities)
    assert len(mapped.relationships) == 1
    assert mapped.relationships[0].rel_type == RelType.MIEMBRO_COMITE
    assert mapped.relationships[0].properties["codigo_proceso"] == "AS-9"
