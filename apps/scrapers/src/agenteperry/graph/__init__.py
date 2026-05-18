"""Graph module for Postgres-based graph operations and Neo4j Aura integration."""

from agenteperry.graph.mapping import (
    EntityCandidate,
    GraphMappingResult,
    RelationshipCandidate,
    map_record_to_graph,
    map_records_to_graph,
)
from agenteperry.graph.models import (
    FIND_CONFLICTS_SQL,
    FIND_ELECTORAL_RETURN_SQL,
    FIND_GHOST_COMPANIES_SQL,
    FIND_MARKET_CONCENTRATION_SQL,
    FIND_SHORT_WINDOW_SQL,
    GET_SUBGRAPH_SQL,
    EntityType,
    GraphEntity,
    GraphRelationship,
    RelType,
    SubgraphNode,
)

__all__ = [
    # Postgres graph
    "EntityType",
    "EntityCandidate",
    "RelType",
    "RelationshipCandidate",
    "GraphMappingResult",
    "GraphEntity",
    "GraphRelationship",
    "SubgraphNode",
    "GET_SUBGRAPH_SQL",
    "FIND_CONFLICTS_SQL",
    "FIND_ELECTORAL_RETURN_SQL",
    "FIND_GHOST_COMPANIES_SQL",
    "FIND_MARKET_CONCENTRATION_SQL",
    "FIND_SHORT_WINDOW_SQL",
    "map_record_to_graph",
    "map_records_to_graph",
    # Neo4j Aura — SPEC-0012 (import lazily so neo4j package is optional)
    # Usage: from agenteperry.graph.neo4j_client import Neo4jClient
    # Usage: from agenteperry.graph.neo4j_schema import setup_schema
    # Usage: from agenteperry.graph.neo4j_ingestion import GraphIngestion
    # Usage: from agenteperry.graph.neo4j_queries import InvestigativeQueries
    # Usage: from agenteperry.graph.neo4j_enrichment import enrich_dossier_with_graph
]
