# SPEC-0006: Source Registry, Graph Foundation and Traceability

## Tasks

### Schema
- [ ] T-1 — Migration `0003_source_registry.sql` crea tablas sin errores.
- [ ] T-2 — Seed 24 fuentes en `source_catalog`.
- [ ] T-3 — Índices GIN, HNSW, trigram creados.
- [ ] T-4 — Función `get_subgraph()` funciona con CTE recursivo.
- [ ] T-5 — RLS policies creadas.

### Docs
- [ ] T-6 — `docs/GRAPH_FOUNDATION.md` completo.
- [ ] T-7 — `docs/CONFLICT_OF_INTEREST.md` con 8 queries SQL.
- [ ] T-8 — `docs/SOURCE_REGISTRY.md` con trazabilidad.
- [ ] T-9 — `docs/SCRAPING_TECHNIQUES.md` con métodos por fuente.

### Data Bulk (Fase 3)
- [ ] T-10 — OCDS collector descarga JSONL.gz 2022-2026.
- [ ] T-11 — OCDS parser flattening a `source_records`.
- [ ] T-12 — SUNAT Padrón descarga ZIP y parsea TXT.
- [ ] T-13 — SUNAT loader inserta en `source_entities` (company).
- [ ] T-14 — OECE/SEACE Pentaho download por categoría.
- [ ] T-15 — OECE loader normaliza procedimientos.

### Enrichment (Fase 4)
- [ ] T-16 — Contraloría Sanciones: Playwright download XLSX.
- [ ] T-17 — Contraloría loader: XLSX → `source_records`.
- [ ] T-18 — MEF CKAN: API list + download datasets.
- [ ] T-19 — CGR Informes: Playwright XHR intercept (selectivo).

### RAG (Fase 5)
- [ ] T-20 — Ley 32069 PDF descargado.
- [ ] T-21 — Ley 32069 chunking por artículo.
- [ ] T-22 — Ley 32069 embeddings en `document_embeddings`.
- [ ] T-23 — 100 TDRs reales descargados.
- [ ] T-24 — 100 TDRs parseados y chunking.
- [ ] T-25 — 100 TDRs embeddings.

### Patrones (Fase 6)
- [ ] T-26 — Query Patrón 1: Socio Invisible.
- [ ] T-27 — Query Patrón 2: Aportante Favorito.
- [ ] T-28 — Query Patrón 3: Empresa Fantasma.
- [ ] T-29 — Query Patrón 4: Monopolio Silencioso.
- [ ] T-30 — Query Patrón 5: Comité Cómplice.
- [ ] T-31 — Query Patrón 6: Sancionado Activo.
- [ ] T-32 — Query Patrón 7: Ventana Corta.
- [ ] T-33 — Query Patrón 8: Conflicto Declarado.
- [ ] T-34 — Materializar vistas para patrones frecuentes.
- [ ] T-35 — Generar `evidence_flags` desde queries.

### Demo (Fase 7)
- [ ] T-36 — API endpoint: buscar por RUC y devolver subgrafo.
- [ ] T-37 — API endpoint: buscar semánticamente en leyes + TDRs.
- [ ] T-38 — Dossier con flags + evidence_quote + page_number.
- [ ] T-39 — Demo visual: tabla de entidades + relaciones.
- [ ] T-40 — Pitch: "Esta empresa presenta 3 señales de riesgo".

### Calidad
- [ ] T-41 — Tests pasan.
- [ ] T-42 — Ruff limpio.
- [ ] T-43 — Pyright 0 errores.
- [ ] T-44 — PR a main con review.
