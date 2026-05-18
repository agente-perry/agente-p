"""Graph queries against the Neo4j AuraDB populated by ``ingest/main.py``."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agenteperry_api.schemas.models import (
    CompanyGraphNode,
    FlagAggregate,
    GraphCounts,
)
from agenteperry_api.services import neo4j_reader

router = APIRouter(prefix="/graph", tags=["graph"])

_NODE_LABELS = [
    "Company",
    "PublicEntity",
    "Contract",
    "Tender",
    "Address",
    "Person",
    "Dossier",
    "RiskFlag",
    "ProcedureSeace",
]
_EDGE_TYPES = [
    "WON",
    "AWARDED_BY",
    "UNDER_TENDER",
    "LOCATED_AT",
    "SAME_ADDRESS_AS",
    "REPRESENTS",
    "SAME_REPR_AS",
    "ANALYZED_BY",
    "HAS_FLAG",
]


def _require_neo4j() -> None:
    if not neo4j_reader.is_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Neo4j is not configured. Set NEO4J_URI + NEO4J_PASSWORD in "
                "the API environment to enable the /graph endpoints."
            ),
        )


@router.get("/counts", response_model=GraphCounts)
def counts() -> GraphCounts:
    _require_neo4j()
    nodes: dict[str, int] = {}
    edges: dict[str, int] = {}
    for label in _NODE_LABELS:
        rows = neo4j_reader.run_query(f"MATCH (n:{label}) RETURN count(n) AS n")
        nodes[label] = int(rows[0]["n"]) if rows else 0
    for rel in _EDGE_TYPES:
        rows = neo4j_reader.run_query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")
        edges[rel] = int(rows[0]["n"]) if rows else 0
    return GraphCounts(nodes=nodes, edges=edges)


@router.get("/company/{ruc}", response_model=CompanyGraphNode)
def company(ruc: str) -> CompanyGraphNode:
    _require_neo4j()
    rows = neo4j_reader.run_query(
        """
        MATCH (c:Company {ruc: $ruc})
        OPTIONAL MATCH (c)-[:WON]->(co:Contract)
        WITH c, count(DISTINCT co) AS total_contracts
        RETURN c.ruc AS ruc, c.name AS name, c.estado AS estado,
               c.condicion AS condicion, total_contracts,
               coalesce(c.total_won_pen, 0.0) AS total_won_pen,
               c.risk_score_v2 AS risk_score_v2
        """,
        {"ruc": ruc},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Company not found: {ruc}")
    row = rows[0]
    return CompanyGraphNode(
        ruc=str(row.get("ruc") or ruc),
        name=row.get("name"),
        estado=row.get("estado"),
        condicion=row.get("condicion"),
        total_contracts=int(row.get("total_contracts") or 0),
        total_won_pen=float(row.get("total_won_pen") or 0.0),
        risk_score_v2=row.get("risk_score_v2"),
    )


@router.get("/flags", response_model=list[FlagAggregate])
def flags_aggregate(limit: int = 20) -> list[FlagAggregate]:
    """Aggregate count of RiskFlag nodes by flag_code."""
    _require_neo4j()
    rows = neo4j_reader.run_query(
        """
        MATCH (d:Dossier)-[:HAS_FLAG]->(f:RiskFlag)
        WITH f.flag_code AS flag_code, collect(DISTINCT d.ocid)[..5] AS sample, count(*) AS n
        RETURN flag_code, n, sample
        ORDER BY n DESC
        LIMIT $limit
        """,
        {"limit": int(limit)},
    )
    return [
        FlagAggregate(
            flag_code=str(r.get("flag_code")),
            company_count=int(r.get("n") or 0),
            sample_companies=list(r.get("sample") or []),
        )
        for r in rows
    ]
