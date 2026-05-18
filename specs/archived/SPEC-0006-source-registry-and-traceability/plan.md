# SPEC-0006: Source Registry, Graph Foundation and Traceability

## Plan De Implementacion

### Fase 1 — Schema (1 día)
- Migration `0003_source_registry.sql`.
- Tablas: `source_catalog`, `source_records`, `source_entities`, `source_relationships`, `document_chunks`, `document_embeddings`, `evidence_flags`.
- Seed 24 fuentes.
- Función `get_subgraph()`.

### Fase 2 — Docs (1 día)
- `docs/GRAPH_FOUNDATION.md` — modelo de grafo en Postgres.
- `docs/CONFLICT_OF_INTEREST.md` — 8 patrones con queries SQL.
- `docs/SOURCE_REGISTRY.md` — trazabilidad completa.
- `docs/SCRAPING_TECHNIQUES.md` — métodos por fuente.

### Fase 3 — Data Bulk (2-3 días)
- OCDS Perú: descarga JSONL.gz por año (2022-2026).
- SUNAT Padrón: descarga ZIP, parsear TXT.
- OECE/SEACE: Pentaho CSV/XLSX por categoría.
- Insertar en `source_records` + `source_entities`.

### Fase 4 — Enrichment Controlado (2-3 días)
- Contraloría Sanciones: Playwright download intercept.
- MEF CKAN: API descarga datasets.
- CGR Informes: Playwright XHR intercept (selectivo).

### Fase 5 — RAG Legal + TDRs (2 días)
- Ley 32069: PDF → chunks → embeddings.
- TDRs reales: PDF → chunks → embeddings.
- Informes CGR: PDF → chunks → embeddings.

### Fase 6 — Patrones SQL (2 días)
- Implementar queries de los 8 patrones.
- Materializar vistas para patrones frecuentes.
- Generar `evidence_flags` con metadata trazable.

### Fase 7 — Demo (1 día)
- Dossier con evidencia cruzada.
- Subgrafo visualizable.
- Búsqueda semántica.

## Diagrama De Datos

```text
source_catalog
  -> source_records (raw_data JSONB)
    -> source_entities (normalized nodes)
      -> source_relationships (graph edges)
        -> evidence_flags (rule-based detection)

source_records
  -> document_chunks
    -> document_embeddings (pgvector)
      -> semantic search + RAG
```

## Tecnologías

| Capa | Tech |
|------|------|
| DB | Supabase Postgres 16 + pgvector |
| Scraping | Python + requests + Playwright |
| Parsing | pandas + ijson + pdfplumber |
| Embeddings | OpenAI text-embedding-3-small |
| Search | pgvector cosine similarity + full-text |

## Riesgos

- **Volumen OCDS:** ~2 GB comprimido, 2.7M tenders. Usar `ijson` streaming.
- **CAPTCHA SUNAT:** Consulta múltiple requiere intervención humana.
- **Rate limits:** CGR, ONPE, JNE necesitan throttling (5-10 req/min).
- **Legal:** No automatizar SUNARP SPRL (pagado). No scraping masivo de Poder Judicial.

## Métricas De Éxito

- [ ] 5M+ registros en `source_records`.
- [ ] 100K+ entidades en `source_entities`.
- [ ] 500K+ relaciones en `source_relationships`.
- [ ] Ley 32069 indexada en pgvector.
- [ ] 100+ TDRs reales parseados.
- [ ] Al menos 3 patrones SQL funcionando con datos reales.
