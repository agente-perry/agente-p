# SPEC-0012: Neo4j Graph Integration

## Objetivo

Conectar AgentePerry a Neo4j Aura para almacenar el grafo investigativo
y ejecutar queries Cypher que el pipeline de agentes no puede hacer eficientemente
en Postgres (traversal de N saltos, deteccion de carrusel, comunidades empresariales).

## Motivacion

Los patrones de riesgo mas importantes (carrusel, conflicto de interes, red empresarial)
requieren traversal de grafo. Postgres con CTEs recursivos es fragil a >3 saltos.
Neo4j Aura esta conectado y el esquema fue disenado por el equipo de arquitectura.

## Fuera de alcance

- Graphiti (deferred)
- ConflictMap full (deferred)
- Deteccion automatica de red en tiempo real

## Componentes

1. `graph/neo4j_client.py` — cliente sync Neo4j, patron db/client.py
2. `graph/neo4j_schema.py` — constraints + indices (idempotente)
3. `graph/neo4j_ingestion.py` — Postgres → Neo4j (Companies, Contracts, TDRs, Flags)
4. `graph/neo4j_queries.py` — queries investigativos Cypher
5. CLI: `graph neo4j-setup / neo4j-ingest / neo4j-inspect / neo4j-high-risk`

## Tablas Postgres de origen

- `source_entities` (entity_type = 'company' | 'public_entity' | 'person')
- `source_records` (record_type = 'contract', supplier_ruc, entity_ruc, monto)
- `source_relationships` (rel_type = 'REPRESENTANTE_DE', etc.)
- `tdr_documents` (id, ocid, entidad, valor_referencial)
- `tdr_flags` (id, tdr_id, flag_code, severity, evidence_quote, page_number)

## Nodos Neo4j

- (:Company {ruc, name})
- (:PublicEntity {ruc, name})
- (:Person {canonical_id, nombre})
- (:Contract {ocid, amount, contract_date})
- (:TDR {tdr_id, ocid, entidad, objeto, valor_referencial})
- (:Flag {flag_id, flag_code, severity, evidence_quote, page_number})

## Edges criticos

- (Company)-[:GANA_CONTRATO]->(Contract)
- (Company)-[:COMPRO_A]->(PublicEntity)
- (Person)-[:REPRESENTA]->(Company)
- (TDR)-[:PERTENECE_A]->(Contract)
- (Flag)-[:DETECTADA_EN]->(TDR)
- (Flag)-[:IMPLICA_A]->(Company)   ← edge que conecta evidencia con empresa

## Queries investigativos

1. `find_flags_for_company(ruc)` — todas las flags que implican a una empresa
2. `get_high_risk_suppliers(min_flags)` — empresas con N+ flags
3. `find_community_around_company(ruc)` — red de empresas bajo mismo representante
4. `detect_carousel(canonical_id)` — mismo representante, multiples empresas, misma entidad
5. `find_conflict_of_interest(supplier_ruc, buyer_ruc)` — camino Person entre proveedor y entidad

## Criterios de aceptacion

- `agenteperry graph neo4j-setup` crea constraints e indices sin error
- `agenteperry graph neo4j-verify` retorna True (conexion OK)
- `agenteperry graph neo4j-ingest` ingesta Companies + Contracts desde source_entities/source_records
- `agenteperry graph neo4j-inspect --ruc <ruc>` muestra flags + comunidad
- `agenteperry graph neo4j-high-risk` lista empresas con >=2 flags

## Dependencia

```
neo4j>=5.20          # driver oficial sync
```
Extra opcional: `uv pip install agenteperry[graph]`

## Rama / Commit

- Rama: `feat/SPEC-0012-neo4j-graph-integration`
- Commit suffix: `(SPEC-0012)`
