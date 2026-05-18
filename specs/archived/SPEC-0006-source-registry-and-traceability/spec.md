# SPEC-0006: Source Registry, Graph Foundation and Traceability

## Objetivo

Expandir el MVP TDR Scanner para soportar múltiples fuentes de datos públicos del Estado peruano con trazabilidad completa, grafo relacional en Postgres y RAG sobre texto legal.

## Motivación

Para el hackathon mundial necesitamos datos reales de múltiples fuentes (no solo TDRs). El legacy branch contiene análisis técnico detallado de 24 fuentes, 8 patrones de detección y un schema de grafo. Este spec adapta esa inteligencia al MVP actual sin traer todo el ruido legacy.

## Alcance

### Dentro de alcance
- [ ] Catálogo de fuentes (`source_catalog`) con metadata trazable.
- [ ] Registros genéricos (`source_records`) para cualquier fuente.
- [ ] Entidades normalizadas (`source_entities`) y relaciones (`source_relationships`) en Postgres.
- [ ] Chunks y embeddings genéricos (`document_chunks`, `document_embeddings`) para RAG.
- [ ] Patrones de detección de conflictos de interés adaptados a Postgres.
- [ ] Integración con pgvector para búsqueda semántica cruzada.

### Fuera de alcance (por ahora)
- Neo4j / Graphiti (usamos Postgres relacional como grafo).
- Civic Amplifier completo.
- SMS alerts.
- Scoring automático completo (mantenemos rule-based).

## Fuentes Priorizadas

| Fase | Fuentes | Método |
|------|---------|--------|
| 1 | OCDS Perú, SUNAT Padrón, OECE/SEACE bulk | Descarga directa / API |
| 2 | Contraloría Sanciones, MEF CKAN, CGR Informes | Playwright controlado |
| 3 | Ley 32069, Ley 31227, TDRs reales | PDF parsing + RAG |
| 4 | ONPE Claridad, JNE, SIDJI | Enrichment bajo demanda |

## Schema Nuevo

Ver `packages/db/migrations/0003_source_registry.sql`.

### Tablas principales

- `source_catalog`: catálogo de fuentes.
- `source_records`: registro genérico JSONB de cualquier fuente.
- `source_entities`: entidades normalizadas (persona, empresa, entidad pública).
- `source_relationships`: relaciones tipo grafo en Postgres.
- `document_chunks`: chunks de texto para RAG.
- `document_embeddings`: embeddings pgvector.

## Patrones De Detección

Adaptados del legacy (8 patrones) a queries SQL en Postgres:

1. **Socio Invisible** — conflicto de interés por familiar.
2. **Aportante Favorito** — retorno de inversión electoral.
3. **Empresa Fantasma** — creada para ganar.
4. **Monopolio Silencioso** — proveedor recurrente.
5. **Comité Cómplice** — mismo evaluador, mismo ganador.
6. **Sancionado Activo** — inhabilitado contratando.
7. **Ventana Corta** — plazo diseñado para excluir.
8. **Conflicto Declarado** — DJI activa ignorada.

Ver `docs/CONFLICT_OF_INTEREST.md`.

## RAG Foundation

- Indexar Ley 32069, Ley 31227, informes CGR.
- Chunks por artículo/sección.
- Embeddings `text-embedding-3-small`.
- Búsqueda semántica cruzada: contrato + ley + entidad.

## Metadata Trazable

Cada registro debe incluir:

```text
source_id, source_name, source_url, collection_method,
fetched_at, retrieved_by, checksum, external_id,
entity_ruc, entity_name, region, period_year,
page_number, evidence_quote, evidence_url
```

## Criterios De Aceptación

- [ ] Migration 0003 crea tablas sin romper 0002.
- [ ] `source_catalog` contiene las 24 fuentes del legacy.
- [ ] `source_entities` puede almacenar persona, empresa, entidad pública.
- [ ] `source_relationships` soporta al menos 10 tipos de relación.
- [ ] `document_chunks` + `document_embeddings` funcionan con pgvector.
- [ ] Al menos 1 patrón de detección tiene query SQL funcional.
- [ ] Tests pasan.
- [ ] Ruff y pyright limpios.

## Fuera De Alcance

- Scoring automático con ML.
- Neo4j/Graphiti.
- SMS/WhatsApp.
- Dashboard visual.
