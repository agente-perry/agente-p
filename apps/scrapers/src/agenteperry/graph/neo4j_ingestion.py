"""Neo4j graph ingestion: Postgres → Neo4j Aura — SPEC-0012.

Reads from the existing Postgres tables (source_entities, source_records,
source_relationships, tdr_documents, tdr_flags) and upserts nodes + edges
into Neo4j using MERGE (idempotent, safe to re-run).

Pipeline order matters — nodes must exist before edges that reference them:
  1. Companies        (source_entities WHERE entity_type = 'company')
  2. PublicEntities   (source_entities WHERE entity_type = 'public_entity')
  3. Persons          (source_entities WHERE entity_type = 'person')
  4. Contracts        (source_records WHERE record_type = 'contract')
  5. TDRs             (tdr_documents)
  6. Flags            (tdr_flags)
  7. Edges            (REPRESENTA, GANA_CONTRATO, COMPRO_A,
                       PERTENECE_A, DETECTADA_EN, IMPLICA_A)

Run::

    from agenteperry.graph.neo4j_ingestion import GraphIngestion
    stats = GraphIngestion().run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from agenteperry.db.client import DbClient
from agenteperry.graph.neo4j_client import Neo4jClient

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@dataclass
class IngestionStats:
    companies: int = 0
    public_entities: int = 0
    persons: int = 0
    contracts: int = 0
    tdrs: int = 0
    flags: int = 0
    edges_total: int = 0
    errors: list[str] = field(default_factory=list[str])

    def to_dict(self) -> dict[str, Any]:
        return {
            "companies": self.companies,
            "public_entities": self.public_entities,
            "persons": self.persons,
            "contracts": self.contracts,
            "tdrs": self.tdrs,
            "flags": self.flags,
            "edges_total": self.edges_total,
            "errors": len(self.errors),
        }


# ---------------------------------------------------------------------------
# Cypher templates — UNWIND batch pattern for efficiency
# ---------------------------------------------------------------------------

_MERGE_COMPANIES = """
UNWIND $rows AS row
MERGE (co:Company {ruc: row.ruc})
SET co.name        = row.name,
    co.estado      = row.estado,
    co.condicion   = row.condicion,
    co.ubigeo      = row.ubigeo,
    co.updated_at  = datetime()
"""

_MERGE_PUBLIC_ENTITIES = """
UNWIND $rows AS row
MERGE (e:PublicEntity {ruc: row.ruc})
SET e.name       = row.name,
    e.updated_at = datetime()
"""

_MERGE_PERSONS = """
UNWIND $rows AS row
MERGE (p:Person {canonical_id: row.canonical_id})
SET p.nombre     = row.nombre,
    p.updated_at = datetime()
"""

_MERGE_CONTRACTS = """
UNWIND $rows AS row
MERGE (c:Contract {ocid: row.ocid})
SET c.amount        = row.amount,
    c.contract_date = row.contract_date,
    c.title         = row.title,
    c.region        = row.region,
    c.supplier_ruc  = row.supplier_ruc,
    c.buyer_ruc     = row.buyer_ruc,
    c.updated_at    = datetime()
"""

_MERGE_TDRS = """
UNWIND $rows AS row
MERGE (t:TDR {tdr_id: row.tdr_id})
SET t.ocid                = row.ocid,
    t.entidad             = row.entidad,
    t.objeto              = row.objeto,
    t.valor_referencial   = row.valor_referencial,
    t.sector              = row.sector,
    t.coverage_pct        = row.coverage_pct,
    t.updated_at          = datetime()
"""

_MERGE_FLAGS = """
UNWIND $rows AS row
MERGE (f:Flag {flag_id: row.flag_id})
SET f.tdr_id         = row.tdr_id,
    f.ocid           = row.ocid,
    f.flag_code      = row.flag_code,
    f.severity       = row.severity,
    f.evidence_quote = row.evidence_quote,
    f.page_number    = row.page_number,
    f.updated_at     = datetime()
"""

# Edge: Company -[:GANA_CONTRATO]-> Contract
_EDGE_GANA_CONTRATO = """
UNWIND $rows AS row
MATCH (co:Company {ruc: row.supplier_ruc})
MATCH (c:Contract {ocid: row.ocid})
MERGE (co)-[:GANA_CONTRATO]->(c)
"""

# Edge: Company -[:COMPRO_A]-> PublicEntity
_EDGE_COMPRO_A = """
UNWIND $rows AS row
MATCH (co:Company {ruc: row.supplier_ruc})
MATCH (e:PublicEntity {ruc: row.buyer_ruc})
MERGE (co)-[:COMPRO_A]->(e)
"""

# Edge: Person -[:REPRESENTA]-> Company  (from source_relationships)
_EDGE_REPRESENTA = """
UNWIND $rows AS row
MATCH (p:Person {canonical_id: row.person_id})
MATCH (co:Company {ruc: row.company_ruc})
MERGE (p)-[:REPRESENTA]->(co)
"""

# Edge: TDR -[:PERTENECE_A]-> Contract
_EDGE_TDR_CONTRATO = """
UNWIND $rows AS row
MATCH (t:TDR {tdr_id: row.tdr_id})
MATCH (c:Contract {ocid: row.ocid})
MERGE (t)-[:PERTENECE_A]->(c)
"""

# Edge: Flag -[:DETECTADA_EN]-> TDR
_EDGE_FLAG_TDR = """
UNWIND $rows AS row
MATCH (f:Flag {flag_id: row.flag_id})
MATCH (t:TDR {tdr_id: row.tdr_id})
MERGE (f)-[:DETECTADA_EN]->(t)
"""

# THE CRITICAL EDGE: Flag -[:IMPLICA_A]-> Company
# Links documentary evidence to the winning company.
_EDGE_FLAG_IMPLICA = """
UNWIND $rows AS row
MATCH (f:Flag {flag_id: row.flag_id})
MATCH (co:Company {ruc: row.supplier_ruc})
MERGE (f)-[:IMPLICA_A]->(co)
"""

# Edge: Person -[:ES_FUNCIONARIO_DE]-> PublicEntity
# Powers the conflict-of-interest Cypher query (_Q_CONFLICT_OF_INTEREST).
# Source: source_relationships WHERE rel_type = 'FUNCIONARIO_EN'
_EDGE_ES_FUNCIONARIO_DE = """
UNWIND $rows AS row
MATCH (p:Person {canonical_id: row.person_id})
MATCH (e:PublicEntity {ruc: row.entity_ruc})
MERGE (p)-[:ES_FUNCIONARIO_DE]->(e)
"""

# Edge: Person -[:MIEMBRO_COMITE]-> Contract
# Links committee members to the contracts where they evaluated proposals.
# Source: source_relationships WHERE rel_type = 'MIEMBRO_COMITE'
_EDGE_MIEMBRO_COMITE_CONTRACT = """
UNWIND $rows AS row
MATCH (p:Person {canonical_id: row.person_id})
MATCH (c:Contract {ocid: row.ocid})
MERGE (p)-[:MIEMBRO_COMITE]->(c)
"""


# ---------------------------------------------------------------------------
# Postgres queries
# ---------------------------------------------------------------------------

_PG_COMPANIES = """
SELECT
    se.canonical_id                          AS ruc,
    se.display_name                          AS name,
    se.metadata->>'estado'                   AS estado,
    se.metadata->>'condicion'                AS condicion,
    se.metadata->>'ubigeo'                   AS ubigeo
FROM source_entities se
WHERE se.entity_type = 'company'
  AND se.canonical_id ~ '^[0-9]{11}$'
LIMIT %(limit)s
"""

_PG_PUBLIC_ENTITIES = """
SELECT
    se.canonical_id  AS ruc,
    se.display_name  AS name
FROM source_entities se
WHERE se.entity_type = 'public_entity'
  AND se.canonical_id ~ '^[0-9]{11}$'
LIMIT %(limit)s
"""

_PG_PERSONS = """
SELECT
    se.canonical_id  AS canonical_id,
    se.display_name  AS nombre
FROM source_entities se
WHERE se.entity_type = 'person'
LIMIT %(limit)s
"""

_PG_CONTRACTS = """
SELECT
    sr.external_id                                           AS ocid,
    sr.supplier_ruc,
    sr.entity_ruc                                            AS buyer_ruc,
    (sr.parsed_data->>'monto')::numeric                     AS amount,
    (sr.parsed_data->>'fecha')::text                        AS contract_date,
    COALESCE(
        sr.parsed_data->'tender'->>'title',
        sr.parsed_data->>'titulo',
        sr.parsed_data->>'descripcion'
    )                                                        AS title,
    sr.region
FROM source_records sr
WHERE sr.record_type = 'contract'
  AND sr.external_id IS NOT NULL
LIMIT %(limit)s
"""

_PG_TDRS = """
SELECT
    td.id::text                  AS tdr_id,
    td.ocid,
    td.entidad_nombre            AS entidad,
    td.objeto_contratacion       AS objeto,
    td.valor_referencial,
    td.sector,
    td.coverage_pct
FROM tdr_documents td
WHERE td.ocid IS NOT NULL
LIMIT %(limit)s
"""

_PG_FLAGS = """
SELECT
    tf.id::text                  AS flag_id,
    tf.tdr_id::text,
    td.ocid,
    tf.flag_code,
    tf.severity,
    tf.evidence_quote,
    tf.page_number,
    sr.supplier_ruc
FROM tdr_flags tf
JOIN tdr_documents td  ON td.id = tf.tdr_id
LEFT JOIN source_records sr
    ON sr.external_id = td.ocid
   AND sr.record_type = 'contract'
   AND sr.supplier_ruc IS NOT NULL
WHERE tf.flag_code IS NOT NULL
LIMIT %(limit)s
"""

_PG_REPRESENTA = """
SELECT
    srel.source_id   AS person_id,
    se_co.canonical_id AS company_ruc
FROM source_relationships srel
JOIN source_entities se_co ON se_co.id = srel.target_id
                           AND se_co.entity_type = 'company'
                           AND se_co.canonical_id ~ '^[0-9]{11}$'
WHERE srel.rel_type = 'REPRESENTANTE_DE'
LIMIT %(limit)s
"""

# Person -[:ES_FUNCIONARIO_DE]-> PublicEntity
# Activates the conflict-of-interest Cypher path in neo4j_queries._Q_CONFLICT_OF_INTEREST.
_PG_FUNCIONARIO = """
SELECT
    srel.source_id                 AS person_id,
    se_pe.canonical_id             AS entity_ruc
FROM source_relationships srel
JOIN source_entities se_pe ON se_pe.id = srel.target_id
                           AND se_pe.entity_type = 'public_entity'
                           AND se_pe.canonical_id ~ '^[0-9]{11}$'
WHERE srel.rel_type = 'FUNCIONARIO_EN'
LIMIT %(limit)s
"""

# Person -[:MIEMBRO_COMITE]-> Contract
# Links evaluators to the contract they awarded — enables committee-bias detection.
_PG_MIEMBRO_COMITE = """
SELECT
    srel.source_id                                     AS person_id,
    (srel.properties->>'contract_id')                  AS ocid
FROM source_relationships srel
WHERE srel.rel_type = 'MIEMBRO_COMITE'
  AND srel.properties ? 'contract_id'
  AND srel.properties->>'contract_id' IS NOT NULL
LIMIT %(limit)s
"""


# ---------------------------------------------------------------------------
# GraphIngestion class
# ---------------------------------------------------------------------------


class GraphIngestion:
    """Ingest the full graph from Postgres into Neo4j Aura.

    Usage::

        stats = GraphIngestion().run()
        print(stats.to_dict())

    Optionally limit rows per table (useful for smoke tests)::

        stats = GraphIngestion().run(limit=200)
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient | None = None,
        pg_client: DbClient | None = None,
        batch_size: int = 500,
    ) -> None:
        self._neo4j = neo4j_client or Neo4jClient()
        self._pg = pg_client or DbClient()
        self._batch_size = batch_size
        self._own_neo4j = neo4j_client is None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def run(self, limit: int = 10_000) -> IngestionStats:
        """Run the full ingestion pipeline.  Returns collected statistics."""
        log.info("neo4j.ingestion.start", limit=limit)
        stats = IngestionStats()
        try:
            self._ingest_companies(stats, limit)
            self._ingest_public_entities(stats, limit)
            self._ingest_persons(stats, limit)
            self._ingest_contracts(stats, limit)
            self._ingest_tdrs(stats, limit)
            self._ingest_flags(stats, limit)
            self._ingest_edges(stats, limit)
        finally:
            if self._own_neo4j:
                self._neo4j.close()

        log.info(
            "neo4j.ingestion.done",
            **{k: v for k, v in stats.to_dict().items() if k != "errors"},
            errors=len(stats.errors),
        )
        if stats.errors:
            for err in stats.errors:
                log.warning("neo4j.ingestion.warning", message=err)
        return stats

    # ------------------------------------------------------------------
    # Node ingestion steps
    # ------------------------------------------------------------------

    def _ingest_companies(self, stats: IngestionStats, limit: int) -> None:
        rows = self._pg.execute(_PG_COMPANIES, {"limit": limit})
        if not rows:
            log.debug("neo4j.ingestion.step", step="companies", rows=0)
            return
        clean = [
            {
                "ruc": r["ruc"] or "",
                "name": r["name"] or "",
                "estado": r.get("estado"),
                "condicion": r.get("condicion"),
                "ubigeo": r.get("ubigeo"),
            }
            for r in rows
            if r.get("ruc")
        ]
        self._neo4j.execute_write_batch(_MERGE_COMPANIES, clean, self._batch_size)
        stats.companies = len(clean)
        log.debug("neo4j.ingestion.step", step="companies", rows=stats.companies)

    def _ingest_public_entities(self, stats: IngestionStats, limit: int) -> None:
        rows = self._pg.execute(_PG_PUBLIC_ENTITIES, {"limit": limit})
        if not rows:
            log.debug("neo4j.ingestion.step", step="public_entities", rows=0)
            return
        clean = [
            {"ruc": r["ruc"] or "", "name": r["name"] or ""}
            for r in rows
            if r.get("ruc")
        ]
        self._neo4j.execute_write_batch(_MERGE_PUBLIC_ENTITIES, clean, self._batch_size)
        stats.public_entities = len(clean)
        log.debug("neo4j.ingestion.step", step="public_entities", rows=stats.public_entities)

    def _ingest_persons(self, stats: IngestionStats, limit: int) -> None:
        rows = self._pg.execute(_PG_PERSONS, {"limit": limit})
        if not rows:
            log.debug("neo4j.ingestion.step", step="persons", rows=0)
            return
        clean = [
            {
                "canonical_id": r["canonical_id"] or "",
                "nombre": r["nombre"] or "",
            }
            for r in rows
            if r.get("canonical_id")
        ]
        self._neo4j.execute_write_batch(_MERGE_PERSONS, clean, self._batch_size)
        stats.persons = len(clean)
        log.debug("neo4j.ingestion.step", step="persons", rows=stats.persons)

    def _ingest_contracts(self, stats: IngestionStats, limit: int) -> None:
        rows = self._pg.execute(_PG_CONTRACTS, {"limit": limit})
        if not rows:
            log.debug("neo4j.ingestion.step", step="contracts", rows=0)
            return
        clean = [
            {
                "ocid": r["ocid"] or "",
                "supplier_ruc": r["supplier_ruc"] or "",
                "buyer_ruc": r["buyer_ruc"] or "",
                "amount": float(r["amount"]) if r.get("amount") else None,
                "contract_date": r.get("contract_date"),
                "title": r.get("title"),
                "region": r.get("region"),
            }
            for r in rows
            if r.get("ocid")
        ]
        self._neo4j.execute_write_batch(_MERGE_CONTRACTS, clean, self._batch_size)
        stats.contracts = len(clean)
        log.debug("neo4j.ingestion.step", step="contracts", rows=stats.contracts)

    def _ingest_tdrs(self, stats: IngestionStats, limit: int) -> None:
        try:
            rows = self._pg.execute(_PG_TDRS, {"limit": limit})
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"tdr_documents: {exc}")
            log.warning("neo4j.ingestion.step_skipped", step="tdrs", reason=str(exc))
            return
        if not rows:
            return
        clean = [
            {
                "tdr_id": r["tdr_id"] or "",
                "ocid": r.get("ocid"),
                "entidad": r.get("entidad"),
                "objeto": r.get("objeto"),
                "valor_referencial": float(r["valor_referencial"]) if r.get("valor_referencial") else None,
                "sector": r.get("sector"),
                "coverage_pct": float(r["coverage_pct"]) if r.get("coverage_pct") else None,
            }
            for r in rows
            if r.get("tdr_id")
        ]
        self._neo4j.execute_write_batch(_MERGE_TDRS, clean, self._batch_size)
        stats.tdrs = len(clean)

    def _ingest_flags(self, stats: IngestionStats, limit: int) -> None:
        try:
            rows = self._pg.execute(_PG_FLAGS, {"limit": limit})
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"tdr_flags: {exc}")
            return
        if not rows:
            return
        clean = [
            {
                "flag_id": r["flag_id"] or "",
                "tdr_id": r.get("tdr_id") or "",
                "ocid": r.get("ocid"),
                "flag_code": r.get("flag_code"),
                "severity": r.get("severity"),
                "evidence_quote": r.get("evidence_quote"),
                "page_number": r.get("page_number"),
                "supplier_ruc": r.get("supplier_ruc"),
            }
            for r in rows
            if r.get("flag_id")
        ]
        self._neo4j.execute_write_batch(_MERGE_FLAGS, clean, self._batch_size)
        stats.flags = len(clean)

    # ------------------------------------------------------------------
    # Edge ingestion
    # ------------------------------------------------------------------

    def _ingest_edges(self, stats: IngestionStats, limit: int) -> None:
        # GANA_CONTRATO + COMPRO_A (from contracts, need both rucs)
        contracts = self._pg.execute(_PG_CONTRACTS, {"limit": limit})
        with_supplier = [
            {"ocid": r["ocid"], "supplier_ruc": r["supplier_ruc"], "buyer_ruc": r["entity_ruc"] if "entity_ruc" in r else r.get("buyer_ruc")}
            for r in contracts
            if r.get("ocid") and r.get("supplier_ruc")
        ]
        if with_supplier:
            self._neo4j.execute_write_batch(_EDGE_GANA_CONTRATO, with_supplier, self._batch_size)
            stats.edges_total += len(with_supplier)

        with_buyer = [r for r in with_supplier if r.get("buyer_ruc")]
        if with_buyer:
            self._neo4j.execute_write_batch(_EDGE_COMPRO_A, with_buyer, self._batch_size)
            stats.edges_total += len(with_buyer)

        # PERTENECE_A (TDR → Contract)
        try:
            tdrs = self._pg.execute(_PG_TDRS, {"limit": limit})
            tdr_edges = [
                {"tdr_id": r["tdr_id"], "ocid": r["ocid"]}
                for r in tdrs
                if r.get("tdr_id") and r.get("ocid")
            ]
            if tdr_edges:
                self._neo4j.execute_write_batch(_EDGE_TDR_CONTRATO, tdr_edges, self._batch_size)
                stats.edges_total += len(tdr_edges)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"tdr/contract edges: {exc}")

        # DETECTADA_EN + IMPLICA_A (Flag → TDR, Flag → Company)
        try:
            flags = self._pg.execute(_PG_FLAGS, {"limit": limit})
            flag_tdr = [
                {"flag_id": r["flag_id"], "tdr_id": r["tdr_id"]}
                for r in flags
                if r.get("flag_id") and r.get("tdr_id")
            ]
            if flag_tdr:
                self._neo4j.execute_write_batch(_EDGE_FLAG_TDR, flag_tdr, self._batch_size)
                stats.edges_total += len(flag_tdr)

            # THE CRITICAL EDGE
            flag_company = [
                {"flag_id": r["flag_id"], "supplier_ruc": r["supplier_ruc"]}
                for r in flags
                if r.get("flag_id") and r.get("supplier_ruc")
            ]
            if flag_company:
                self._neo4j.execute_write_batch(_EDGE_FLAG_IMPLICA, flag_company, self._batch_size)
                stats.edges_total += len(flag_company)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"flag edges: {exc}")

        # REPRESENTA (Person → Company)
        try:
            rels = self._pg.execute(_PG_REPRESENTA, {"limit": limit})
            repr_edges = [
                {"person_id": r["person_id"], "company_ruc": r["company_ruc"]}
                for r in rels
                if r.get("person_id") and r.get("company_ruc")
            ]
            if repr_edges:
                self._neo4j.execute_write_batch(_EDGE_REPRESENTA, repr_edges, self._batch_size)
                stats.edges_total += len(repr_edges)
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"REPRESENTA edges: {exc}")

        # ES_FUNCIONARIO_DE (Person → PublicEntity)
        # Activates conflict-of-interest detection in Cypher queries.
        try:
            func_rels = self._pg.execute(_PG_FUNCIONARIO, {"limit": limit})
            func_edges = [
                {"person_id": r["person_id"], "entity_ruc": r["entity_ruc"]}
                for r in func_rels
                if r.get("person_id") and r.get("entity_ruc")
            ]
            if func_edges:
                self._neo4j.execute_write_batch(_EDGE_ES_FUNCIONARIO_DE, func_edges, self._batch_size)
                stats.edges_total += len(func_edges)
                log.debug("neo4j.ingestion.step", step="ES_FUNCIONARIO_DE edges", rows=len(func_edges))
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"ES_FUNCIONARIO_DE edges: {exc}")

        # MIEMBRO_COMITE (Person → Contract)
        # Links committee evaluators to the contracts they awarded.
        try:
            comite_rels = self._pg.execute(_PG_MIEMBRO_COMITE, {"limit": limit})
            comite_edges = [
                {"person_id": r["person_id"], "ocid": r["ocid"]}
                for r in comite_rels
                if r.get("person_id") and r.get("ocid")
            ]
            if comite_edges:
                self._neo4j.execute_write_batch(_EDGE_MIEMBRO_COMITE_CONTRACT, comite_edges, self._batch_size)
                stats.edges_total += len(comite_edges)
                log.debug("neo4j.ingestion.step", step="MIEMBRO_COMITE edges", rows=len(comite_edges))
        except Exception as exc:  # noqa: BLE001
            stats.errors.append(f"MIEMBRO_COMITE edges: {exc}")
