"""Graph models and queries for Postgres-based graph."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    COMPANY = "company"
    PUBLIC_ENTITY = "public_entity"
    PERSON = "person"
    POLITICAL_ORG = "political_org"
    SANCION = "sancion"
    AUDIT_REPORT = "audit_report"
    ELECTORAL_CONTRIBUTION = "electoral_contribution"
    INTEREST_DECLARATION = "interest_declaration"
    LEGAL_NORM = "legal_norm"


class RelType(StrEnum):
    GANO_CONTRATO = "GANO_CONTRATO"
    COMPRO_A = "COMPRO_A"
    POSTULO_EN = "POSTULO_EN"
    MIEMBRO_COMITE = "MIEMBRO_COMITE"
    FUNCIONARIO_EN = "FUNCIONARIO_EN"
    REPRESENTANTE_DE = "REPRESENTANTE_DE"
    FAMILIAR_DE = "FAMILIAR_DE"
    APORTO_A = "APORTO_A"
    CANDIDATO_EN = "CANDIDATO_EN"
    GOVERNS = "GOVERNS"
    MISMO_DOMICILIO = "MISMO_DOMICILIO"
    MISMO_REPR_LEGAL = "MISMO_REPR_LEGAL"
    TIENE_SANCION = "TIENE_SANCION"
    MENCIONADO_EN = "MENCIONADO_EN"
    VINCULO_DJI = "VINCULO_DJI"
    GENERA_CASO = "GENERA_CASO"
    JUSTIFICA = "JUSTIFICA"


class GraphEntity(BaseModel):
    """A node in the graph."""

    id: str | None = None
    entity_type: EntityType
    canonical_id: str | None = None
    display_name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(ge=0.0, le=1.0, default=0.0)
    sources: list[str] = Field(default_factory=list)
    valid_from: date | None = None
    valid_until: date | None = None


class GraphRelationship(BaseModel):
    """An edge in the graph."""

    id: str | None = None
    source_id: str
    target_id: str
    rel_type: RelType
    weight: float = Field(default=1.0)
    valid_from: date | None = None
    valid_until: date | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    data_source: str | None = None


class SubgraphNode(BaseModel):
    """A node returned by get_subgraph traversal."""

    node_id: str
    display_name: str
    entity_type: EntityType
    depth: int
    path: list[str]


# SQL Queries for graph operations
GET_SUBGRAPH_SQL = """
WITH RECURSIVE subgraph AS (
    SELECT id, display_name, entity_type, 0 AS depth, ARRAY[id] AS path
    FROM source_entities WHERE canonical_id = %(canonical_id)s

    UNION ALL

    SELECT e.id, e.display_name, e.entity_type, sg.depth + 1, sg.path || e.id
    FROM source_entities e
    JOIN source_relationships r ON (r.source_id = sg.id OR r.target_id = sg.id)
      AND (e.id = r.target_id OR e.id = r.source_id)
      AND e.id != sg.id
    JOIN subgraph sg ON TRUE
    WHERE sg.depth < %(max_depth)s
      AND NOT e.id = ANY(sg.path)
      AND (r.valid_until IS NULL OR r.valid_until >= %(check_date)s)
)
SELECT DISTINCT id AS node_id, display_name, entity_type, depth, path
FROM subgraph
ORDER BY depth;
"""

FIND_CONFLICTS_SQL = """
-- Pattern 1: Socio Invisible
SELECT
    c.external_id AS contrato,
    p.display_name AS funcionario,
    fam.display_name AS familiar,
    emp.display_name AS empresa,
    c.monto,
    c.fecha
FROM source_records c
JOIN source_relationships r_com ON r_com.properties->>'contract_id' = c.id::text
    AND r_com.rel_type = 'MIEMBRO_COMITE'
JOIN source_entities p ON p.id = r_com.source_id
JOIN source_relationships r_fam ON r_fam.source_id = p.id AND r_fam.rel_type = 'FAMILIAR_DE'
JOIN source_entities fam ON fam.id = r_fam.target_id
JOIN source_relationships r_repr ON r_repr.source_id = fam.id AND r_repr.rel_type = 'REPRESENTANTE_DE'
JOIN source_entities emp ON emp.id = r_repr.target_id
WHERE c.supplier_ruc = emp.canonical_id;
"""

FIND_ELECTORAL_RETURN_SQL = """
-- Pattern 2: Aportante Favorito
SELECT
    emp.display_name AS empresa,
    po.display_name AS partido,
    pe.display_name AS entidad,
    SUM(c.monto) AS total_contratos_post,
    COUNT(*) AS num_contratos
FROM source_entities emp
JOIN source_relationships r_ap ON r_ap.source_id = emp.id AND r_ap.rel_type = 'APORTO_A'
JOIN source_entities po ON po.id = r_ap.target_id
JOIN source_relationships r_gov ON r_gov.source_id = po.id AND r_gov.rel_type = 'GOVERNS'
JOIN source_entities pe ON pe.id = r_gov.target_id
JOIN source_records c ON c.entity_ruc = pe.canonical_id AND c.supplier_ruc = emp.canonical_id
    AND c.fecha > (r_ap.properties->>'fecha_aporte')::date
GROUP BY emp.display_name, po.display_name, pe.display_name
HAVING SUM(c.monto) > 0;
"""

FIND_GHOST_COMPANIES_SQL = """
-- Pattern 3: Empresa Fantasma
SELECT
    c.external_id,
    emp.canonical_id AS ruc,
    emp.display_name AS empresa,
    (emp.metadata->>'fecha_inicio_act')::date AS fecha_fundacion,
    c.monto,
    c.supplier_ruc
FROM source_records c
JOIN source_entities emp ON emp.canonical_id = c.supplier_ruc
WHERE c.record_type = 'contract'
    AND (emp.metadata->>'empresas_mismo_domicilio')::int > 5
    AND (emp.metadata->>'fecha_inicio_act')::date > c.fecha - INTERVAL '12 months';
"""

FIND_MARKET_CONCENTRATION_SQL = """
-- Pattern 4: Monopolio Silencioso
WITH empresa_stats AS (
    SELECT
        entity_ruc,
        supplier_ruc,
        COUNT(*) AS num_contratos,
        SUM(monto) AS total_monto,
        SUM(monto) / SUM(SUM(monto)) OVER (PARTITION BY entity_ruc) AS pct_presupuesto
    FROM source_records
    WHERE record_type = 'contract'
        AND fecha >= CURRENT_DATE - INTERVAL '3 years'
    GROUP BY entity_ruc, supplier_ruc
)
SELECT
    pe.display_name AS entidad,
    emp.display_name AS empresa,
    es.num_contratos,
    es.total_monto,
    ROUND(es.pct_presupuesto * 100, 1) AS pct_presupuesto
FROM empresa_stats es
JOIN source_entities pe ON pe.canonical_id = es.entity_ruc
JOIN source_entities emp ON emp.canonical_id = es.supplier_ruc
WHERE es.pct_presupuesto > 0.50
    AND es.num_contratos >= 3
ORDER BY es.pct_presupuesto DESC;
"""

FIND_SHORT_WINDOW_SQL = """
-- Pattern 7: Ventana Corta
SELECT
    c.external_id,
    pe.display_name AS entidad,
    emp.display_name AS empresa,
    c.supplier_ruc AS ruc,
    (c.fecha - c.metadata->>'fecha_conv')::int AS dias_plazo,
    c.monto
FROM source_records c
JOIN source_entities pe ON pe.canonical_id = c.entity_ruc
JOIN source_entities emp ON emp.canonical_id = c.supplier_ruc
WHERE c.record_type = 'contract'
    AND (c.fecha - (c.metadata->>'fecha_conv')::date) < 5;
"""
