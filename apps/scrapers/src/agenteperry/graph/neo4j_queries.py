"""Investigative Cypher queries for Neo4j — SPEC-0012.

Each public method answers one investigative question:

- find_flags_for_company(ruc)        → all flags implicating a company
- get_high_risk_suppliers(min_flags) → companies with N+ flags
- find_community_around_company(ruc) → companies sharing same representative
- detect_carousel(canonical_id)      → same rep, multiple companies, same buyer
- find_conflict_of_interest(...)     → Person path between supplier and buyer
- company_summary(ruc)               → full profile: flags + contracts + community

Rule legal-safe: these queries detect *signals of risk*, not proof of wrongdoing.
Every result includes page + evidence_quote + source so the user can verify.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from agenteperry.graph.neo4j_client import Neo4jClient

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class FlagResult:
    flag_id: str
    flag_code: str
    severity: str
    evidence_quote: str | None
    page_number: int | None
    ocid: str | None
    contract_amount: float | None


@dataclass
class CompanyFlagsResult:
    ruc: str
    company_name: str
    flags: list[FlagResult]

    @property
    def flag_count(self) -> int:
        return len(self.flags)

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.flags if f.severity == "HIGH")


@dataclass
class HighRiskSupplier:
    ruc: str
    name: str
    flag_count: int
    flag_codes: list[str]
    contract_count: int
    total_amount: float | None


@dataclass
class CommunityResult:
    ruc: str
    company_name: str
    community_size: int
    community_companies: list[dict[str, str]]  # [{ruc, name}]
    shared_persons: list[str]
    person_ids: list[str]  # canonical_ids — needed for carousel detection


@dataclass
class CarouselResult:
    person_id: str
    person_name: str
    buyer_ruc: str
    buyer_name: str
    company_count: int
    companies: list[dict[str, str]]
    contract_count: int
    total_amount: float | None


@dataclass
class ConflictPath:
    """A Person-mediated path between supplier and buyer."""
    path_nodes: list[dict[str, Any]]
    path_length: int


# ---------------------------------------------------------------------------
# Query strings
# ---------------------------------------------------------------------------

_Q_FLAGS_FOR_COMPANY = """
MATCH (co:Company {ruc: $ruc})
OPTIONAL MATCH (f:Flag)-[:IMPLICA_A]->(co)
OPTIONAL MATCH (f)-[:DETECTADA_EN]->(t:TDR)
OPTIONAL MATCH (t)-[:PERTENECE_A]->(c:Contract)
RETURN
    co.ruc        AS ruc,
    co.name       AS company_name,
    collect({
        flag_id:        f.flag_id,
        flag_code:      f.flag_code,
        severity:       f.severity,
        evidence_quote: f.evidence_quote,
        page_number:    f.page_number,
        ocid:           c.ocid,
        contract_amount: c.amount
    }) AS flags
"""

_Q_HIGH_RISK_SUPPLIERS = """
MATCH (co:Company)<-[:IMPLICA_A]-(f:Flag)
WITH co, collect(f.flag_code) AS codes, count(f) AS flag_count
WHERE flag_count >= $min_flags
OPTIONAL MATCH (co)-[:GANA_CONTRATO]->(c:Contract)
RETURN
    co.ruc      AS ruc,
    co.name     AS name,
    flag_count,
    codes       AS flag_codes,
    count(c)    AS contract_count,
    sum(c.amount) AS total_amount
ORDER BY flag_count DESC, total_amount DESC
LIMIT $limit
"""

_Q_COMMUNITY = """
MATCH (co:Company {ruc: $ruc})<-[:REPRESENTA]-(p:Person)
MATCH (p)-[:REPRESENTA]->(other:Company)
WHERE other.ruc <> $ruc
WITH
    co.ruc        AS ruc,
    co.name       AS company_name,
    collect(DISTINCT {ruc: other.ruc, name: other.name}) AS others,
    collect(DISTINCT p.nombre)                           AS shared_persons,
    collect(DISTINCT p.canonical_id)                     AS person_ids
RETURN
    ruc,
    company_name,
    others             AS community_companies,
    shared_persons,
    person_ids,
    size(others)       AS community_size
"""

_Q_CAROUSEL = """
// Same person represents multiple companies that sold to the same buyer
MATCH (p:Person {canonical_id: $canonical_id})-[:REPRESENTA]->(co:Company)
MATCH (co)-[:GANA_CONTRATO]->(c:Contract)
MATCH (co)-[:COMPRO_A]->(e:PublicEntity)
WITH p, e,
     collect(DISTINCT co) AS companies,
     collect(DISTINCT c)  AS contracts,
     sum(c.amount)        AS total_amount
WHERE size(companies) > 1
RETURN
    p.canonical_id              AS person_id,
    p.nombre                    AS person_name,
    e.ruc                       AS buyer_ruc,
    e.name                      AS buyer_name,
    size(companies)             AS company_count,
    [x IN companies | {ruc: x.ruc, name: x.name}] AS companies,
    size(contracts)             AS contract_count,
    total_amount
ORDER BY company_count DESC
"""

_Q_CONFLICT_OF_INTEREST = """
// Find any Person who both represents the supplier and is related to the buyer
MATCH path =
    (co:Company {ruc: $supplier_ruc})<-[:REPRESENTA]-(p:Person)
    -[:ES_FUNCIONARIO_DE|TRABAJO_EN|MIEMBRO_COMITE*1..2]->(e:PublicEntity {ruc: $buyer_ruc})
RETURN
    [node IN nodes(path) |
        CASE
          WHEN 'Company'       IN labels(node) THEN {type: 'Company',      ruc:  node.ruc,          name: node.name}
          WHEN 'Person'        IN labels(node) THEN {type: 'Person',       id:   node.canonical_id, name: node.nombre}
          WHEN 'PublicEntity'  IN labels(node) THEN {type: 'PublicEntity', ruc:  node.ruc,          name: node.name}
          ELSE                                      {type: 'Unknown',      id:   toString(id(node))}
        END
    ] AS path_nodes,
    length(path) AS path_length
ORDER BY path_length
LIMIT 10
"""

_Q_COMPANY_SUMMARY = """
MATCH (co:Company {ruc: $ruc})
OPTIONAL MATCH (f:Flag)-[:IMPLICA_A]->(co)
OPTIONAL MATCH (co)-[:GANA_CONTRATO]->(c:Contract)
OPTIONAL MATCH (co)-[:COMPRO_A]->(e:PublicEntity)
RETURN
    co.ruc      AS ruc,
    co.name     AS name,
    co.estado   AS estado,
    co.condicion AS condicion,
    count(DISTINCT f) AS flag_count,
    count(DISTINCT c) AS contract_count,
    sum(c.amount)     AS total_amount,
    collect(DISTINCT {code: f.flag_code, severity: f.severity}) AS flag_summary,
    collect(DISTINCT {ruc: e.ruc, name: e.name}) AS buyers
"""

_Q_COUNTS = """
MATCH (n)
RETURN labels(n)[0] AS label, count(n) AS count
ORDER BY count DESC
"""


# ---------------------------------------------------------------------------
# InvestigativeQueries class
# ---------------------------------------------------------------------------


class InvestigativeQueries:
    """Cypher-based investigative queries over the Neo4j graph.

    Usage::

        with InvestigativeQueries() as q:
            result = q.find_flags_for_company("20605681281")
            if result:
                print(result.flag_count, "flags detected")
    """

    def __init__(self, client: Neo4jClient | None = None) -> None:
        self._client = client or Neo4jClient()
        self._own_client = client is None

    def __enter__(self) -> InvestigativeQueries:
        return self

    def __exit__(self, *_: object) -> None:
        if self._own_client:
            self._client.close()

    # ------------------------------------------------------------------
    # Public query methods
    # ------------------------------------------------------------------

    def find_flags_for_company(self, ruc: str) -> CompanyFlagsResult | None:
        """Return all flags that implicate a company, with evidence quotes."""
        rows = self._client.execute_read(_Q_FLAGS_FOR_COMPANY, {"ruc": ruc})
        if not rows:
            return None
        row = rows[0]
        raw_flags = cast(list[dict[str, Any]], row.get("flags") or [])
        flags = [
            FlagResult(
                flag_id=cast(str, f.get("flag_id") or ""),
                flag_code=cast(str, f.get("flag_code") or ""),
                severity=cast(str, f.get("severity") or ""),
                evidence_quote=cast(str | None, f.get("evidence_quote")),
                page_number=cast(int | None, f.get("page_number")),
                ocid=cast(str | None, f.get("ocid")),
                contract_amount=cast(float | None, f.get("contract_amount")),
            )
            for f in raw_flags
            if f.get("flag_id")
        ]
        return CompanyFlagsResult(
            ruc=row.get("ruc") or ruc,
            company_name=row.get("company_name") or "",
            flags=flags,
        )

    def get_high_risk_suppliers(
        self,
        min_flags: int = 2,
        limit: int = 20,
    ) -> list[HighRiskSupplier]:
        """Return companies with at least *min_flags* documentary risk signals."""
        rows = self._client.execute_read(
            _Q_HIGH_RISK_SUPPLIERS,
            {"min_flags": min_flags, "limit": limit},
        )
        return [
            HighRiskSupplier(
                ruc=r.get("ruc") or "",
                name=r.get("name") or "",
                flag_count=r.get("flag_count") or 0,
                flag_codes=list(r.get("flag_codes") or []),
                contract_count=r.get("contract_count") or 0,
                total_amount=r.get("total_amount"),
            )
            for r in rows
        ]

    def find_community_around_company(self, ruc: str) -> CommunityResult:
        """Find all companies sharing a representative with the given company."""
        rows = self._client.execute_read(_Q_COMMUNITY, {"ruc": ruc})
        if not rows:
            return CommunityResult(
                ruc=ruc,
                company_name="",
                community_size=0,
                community_companies=[],
                shared_persons=[],
                person_ids=[],
            )
        row = rows[0]
        return CommunityResult(
            ruc=row.get("ruc") or ruc,
            company_name=row.get("company_name") or "",
            community_size=row.get("community_size") or 0,
            community_companies=list(row.get("community_companies") or []),
            shared_persons=list(row.get("shared_persons") or []),
            person_ids=list(row.get("person_ids") or []),
        )

    def detect_carousel(self, canonical_id: str) -> list[CarouselResult]:
        """Detect if a person controls multiple companies that sold to the same buyer.

        This is a common bid-rigging pattern: one controller spreads contracts
        across nominally different firms so each bid appears independent.
        """
        rows = self._client.execute_read(_Q_CAROUSEL, {"canonical_id": canonical_id})
        return [
            CarouselResult(
                person_id=r.get("person_id") or canonical_id,
                person_name=r.get("person_name") or "",
                buyer_ruc=r.get("buyer_ruc") or "",
                buyer_name=r.get("buyer_name") or "",
                company_count=r.get("company_count") or 0,
                companies=list(r.get("companies") or []),
                contract_count=r.get("contract_count") or 0,
                total_amount=r.get("total_amount"),
            )
            for r in rows
        ]

    def find_conflict_of_interest(
        self,
        supplier_ruc: str,
        buyer_ruc: str,
    ) -> list[ConflictPath]:
        """Find Person-mediated paths between supplier company and buying entity.

        A short path (length ≤ 3) is a signal requiring explanation,
        not proof of wrongdoing.
        """
        rows = self._client.execute_read(
            _Q_CONFLICT_OF_INTEREST,
            {"supplier_ruc": supplier_ruc, "buyer_ruc": buyer_ruc},
        )
        return [
            ConflictPath(
                path_nodes=list(r.get("path_nodes") or []),
                path_length=r.get("path_length") or 0,
            )
            for r in rows
        ]

    def company_summary(self, ruc: str) -> dict[str, Any] | None:
        """Return a full profile of a company: flags, contracts, buyers."""
        rows = self._client.execute_read(_Q_COMPANY_SUMMARY, {"ruc": ruc})
        return dict(rows[0]) if rows else None

    def get_node_counts(self) -> dict[str, int]:
        """Return count per label — useful to verify ingestion completed."""
        rows = self._client.execute_read(_Q_COUNTS)
        return {r["label"]: r["count"] for r in rows if r.get("label")}
