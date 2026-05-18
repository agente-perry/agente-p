"""Map source_records-compatible rows into graph candidates."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from typing import Any, cast

from pydantic import BaseModel, Field

from agenteperry.graph.models import EntityType, RelType


class EntityCandidate(BaseModel):
    """Entity ready to upsert into source_entities."""

    entity_type: EntityType
    canonical_id: str
    display_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    sources: list[str] = Field(default_factory=list)


class RelationshipCandidate(BaseModel):
    """Relationship ready to resolve and insert into source_relationships."""

    source_canonical_id: str
    target_canonical_id: str
    rel_type: RelType
    properties: dict[str, Any] = Field(default_factory=dict)
    data_source: str | None = None


def _empty_entities() -> list[EntityCandidate]:
    return []


def _empty_relationships() -> list[RelationshipCandidate]:
    return []


class GraphMappingResult(BaseModel):
    """Batch output for graph loading."""

    entities: list[EntityCandidate] = Field(default_factory=_empty_entities)
    relationships: list[RelationshipCandidate] = Field(default_factory=_empty_relationships)


def map_records_to_graph(records: Iterable[Mapping[str, Any]]) -> GraphMappingResult:
    """Convert collected source_records rows into deduplicated graph candidates."""
    entities: dict[tuple[EntityType, str], EntityCandidate] = {}
    relationships: dict[tuple[str, str, RelType, str | None], RelationshipCandidate] = {}

    for record in records:
        mapped = map_record_to_graph(record)
        for entity in mapped.entities:
            key = (entity.entity_type, entity.canonical_id)
            existing = entities.get(key)
            entities[key] = _merge_entity(existing, entity) if existing else entity
        for relationship in mapped.relationships:
            key = (
                relationship.source_canonical_id,
                relationship.target_canonical_id,
                relationship.rel_type,
                _property_external_id(relationship.properties),
            )
            relationships[key] = relationship

    return GraphMappingResult(
        entities=list(entities.values()), relationships=list(relationships.values())
    )


def map_record_to_graph(record: Mapping[str, Any]) -> GraphMappingResult:
    """Map one source_records-compatible row into graph candidates."""
    record_type = _text(record.get("record_type"))
    if record_type == "company":
        entity = _company_from_record(record)
        return GraphMappingResult(entities=[entity] if entity else [])
    if record_type == "public_entity":
        entity = _public_entity_from_record(record)
        return GraphMappingResult(entities=[entity] if entity else [])
    if record_type in {"contract", "purchase_order"}:
        return _contract_to_graph(record)
    if record_type == "committee_member":
        return _committee_member_to_graph(record)
    return GraphMappingResult()


def _contract_to_graph(record: Mapping[str, Any]) -> GraphMappingResult:
    entity_ruc = _ruc(record.get("entity_ruc"))
    supplier_ruc = _ruc(record.get("supplier_ruc"))
    entity_name = _text(record.get("entity_name")) or "Entidad publica no identificada"
    supplier_name = _text(record.get("supplier_name")) or "Proveedor no identificado"
    public_entity_id = entity_ruc or _name_key("pe", entity_name)
    supplier_id = supplier_ruc or _name_key("co", supplier_name)
    source_code = _text(record.get("source_code"))

    public_entity = EntityCandidate(
        entity_type=EntityType.PUBLIC_ENTITY,
        canonical_id=public_entity_id,
        display_name=entity_name,
        metadata={"ruc": entity_ruc, "region": _text(record.get("region"))},
        sources=[source_code] if source_code else [],
    )
    supplier = EntityCandidate(
        entity_type=EntityType.COMPANY,
        canonical_id=supplier_id,
        display_name=supplier_name,
        metadata={"ruc": supplier_ruc},
        sources=[source_code] if source_code else [],
    )
    properties = {
        "external_id": _text(record.get("external_id")),
        "monto": record.get("monto"),
        "fecha": _text(record.get("fecha")),
        "evidence_quote": _text(record.get("evidence_quote")),
    }
    return GraphMappingResult(
        entities=[public_entity, supplier],
        relationships=[
            RelationshipCandidate(
                source_canonical_id=supplier_id,
                target_canonical_id=public_entity_id,
                rel_type=RelType.GANO_CONTRATO,
                properties=properties,
                data_source=source_code,
            ),
            RelationshipCandidate(
                source_canonical_id=public_entity_id,
                target_canonical_id=supplier_id,
                rel_type=RelType.COMPRO_A,
                properties=properties,
                data_source=source_code,
            ),
        ],
    )


def _company_from_record(record: Mapping[str, Any]) -> EntityCandidate | None:
    ruc = _ruc(record.get("entity_ruc"))
    name = _text(record.get("entity_name"))
    parsed_data = record.get("parsed_data")
    metadata: dict[str, Any] = {}
    if isinstance(parsed_data, Mapping):
        metadata = dict(cast(Mapping[str, Any], parsed_data))
    source_code = _text(record.get("source_code"))
    if not ruc and not name:
        return None
    return EntityCandidate(
        entity_type=EntityType.COMPANY,
        canonical_id=ruc or _name_key("co", name or "empresa"),
        display_name=name or ruc or "Empresa no identificada",
        metadata=metadata,
        sources=[source_code] if source_code else [],
    )


def _public_entity_from_record(record: Mapping[str, Any]) -> EntityCandidate | None:
    ruc = _ruc(record.get("entity_ruc"))
    name = _text(record.get("entity_name"))
    source_code = _text(record.get("source_code"))
    if not ruc and not name:
        return None
    return EntityCandidate(
        entity_type=EntityType.PUBLIC_ENTITY,
        canonical_id=ruc or _name_key("pe", name or "entidad"),
        display_name=name or ruc or "Entidad publica no identificada",
        metadata={"ruc": ruc, "region": _text(record.get("region"))},
        sources=[source_code] if source_code else [],
    )


def _committee_member_to_graph(record: Mapping[str, Any]) -> GraphMappingResult:
    parsed_data = record.get("parsed_data")
    parsed: Mapping[str, Any] = (
        cast(Mapping[str, Any], parsed_data) if isinstance(parsed_data, Mapping) else {}
    )
    member_name = _text(parsed.get("miembro_comite")) or _text(record.get("supplier_name"))
    public_entity = _public_entity_from_record(record)
    source_code = _text(record.get("source_code"))
    if not member_name:
        return GraphMappingResult(entities=[public_entity] if public_entity else [])
    person_id = _name_key("person", member_name)
    person = EntityCandidate(
        entity_type=EntityType.PERSON,
        canonical_id=person_id,
        display_name=member_name,
        metadata={
            "cargo_comite": _text(parsed.get("cargo_comite")),
            "codigo_proceso": _text(parsed.get("codigo_proceso")),
        },
        sources=[source_code] if source_code else [],
    )
    if public_entity is None:
        return GraphMappingResult(entities=[person])
    return GraphMappingResult(
        entities=[person, public_entity],
        relationships=[
            RelationshipCandidate(
                source_canonical_id=person_id,
                target_canonical_id=public_entity.canonical_id,
                rel_type=RelType.MIEMBRO_COMITE,
                properties={
                    "external_id": _text(record.get("external_id")),
                    "codigo_proceso": _text(parsed.get("codigo_proceso")),
                    "cargo_comite": _text(parsed.get("cargo_comite")),
                    "evidence_quote": _text(record.get("evidence_quote")),
                },
                data_source=source_code,
            )
        ],
    )


def _merge_entity(existing: EntityCandidate | None, new: EntityCandidate) -> EntityCandidate:
    if existing is None:
        return new
    metadata = {**existing.metadata, **new.metadata}
    sources = sorted(set(existing.sources + new.sources))
    display_name = existing.display_name if existing.display_name != existing.canonical_id else new.display_name
    return EntityCandidate(
        entity_type=existing.entity_type,
        canonical_id=existing.canonical_id,
        display_name=display_name,
        metadata=metadata,
        sources=sources,
    )


def _property_external_id(properties: Mapping[str, Any]) -> str | None:
    return _text(properties.get("external_id"))


def _text(value: object) -> str | None:
    cleaned = str(value).strip() if value is not None else ""
    return cleaned or None


def _ruc(value: object) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    return digits if len(digits) == 11 else None


def _name_key(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.lower().encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
