# TASKS — SPEC-0007

Cada task implementable en ~1–3 horas. Orden estricto: 0 → 11. Tasks marcadas `[opt]` son opcionales para v1.

## Fase A — Scaffolding y contratos

- [x] **T0. Auditar reuso desde `apps/scrapers/src/agenteperry/tdr/`** _(PR #1)_
  - Decisión: paquete aislado, no importar. Razones: chunker cross-page con overlap (vs per-page existente), Pydantic `extra="forbid"`, sin deps Postgres/scraper.
  - Documentado en `docs/AGENT_DOCUMENT_CORE.md` (sección "Why a separate package").

- [x] **T1. Scaffold del paquete `packages/document_intelligence/`** _(PR #1 + PR #1b)_
  - `pyproject.toml` con deps: `pymupdf`, `numpy`, `faiss-cpu`, `pydantic`, `click`, `pyyaml`, `rank-bm25`.
  - Extras: `[llm]` → `openai`, `[local-embed]` → `sentence-transformers`, `[dev]` → pytest/ruff/pyright/reportlab.
  - Estructura de carpetas según `spec.md`.
  - Makefile: `doc-intel-install`, `doc-intel-test`, `doc-intel-lint`, `doc-intel-typecheck`, `doc-intel-check`. `pnpm-workspace.yaml` ya cubre `packages/*` (pnpm ignora paquetes sin `package.json`).

- [x] **T2. Schemas Pydantic (`schemas/`)** _(PR #1)_
  - `DocumentRef`, `DocumentPage`, `DocumentChunk`, `DocumentCluster`, `EvidenceItem`, `DoctrineAnchor`, `EvidencePack`, `FlagRecord`, `AnalysisResult`. `DoctrineChunk` vive en `doctrine/index.py`.
  - Todos con `model_config = ConfigDict(extra="forbid")`.
  - Tests `tests/test_schemas.py`.

## Fase B — Capa de datos

- [x] **T3. PDF Parser (`parsing/pdf_parser.py`)** _(PR #1 + PR #1b)_
  - PyMuPDF, extracción por página, `needs_ocr` si `len(text.strip()) < 20`.
  - Whitespace + dedup de headers/footers repetidos (`parsing/header_footer.py`, ratio ≥0.5, mín. 3 páginas, candidatos ≤120 chars).
  - Tests: `tests/test_parser.py` (PDF sintético con boilerplate), `tests/test_header_footer.py`.

- [x] **T4. Chunker (`chunking/chunker.py`)** _(PR #1 + PR #1b)_
  - Sliding window 1200 chars, overlap 160, respeta límites de párrafo (`\n\n` > sentence-end > whitespace).
  - Preserva `page_start`, `page_end`, `section_hint` regex sobre títulos.
  - Tests: cross-page chunk explícito + preferencia párrafo + pages preservadas.

- [x] **T5. Embeddings adapter (`embeddings/`)** _(PR #1b)_
  - `BaseEmbedder` Protocol con `embed(texts) -> np.ndarray`, `dim`, `model_id`.
  - `FakeEmbedder`: blake2b → vector L2-normalizado.
  - `OpenAIEmbedder`: lee `OPENAI_API_KEY`, falla en `__init__` si falta.
  - `LocalEmbedder`: lazy import de sentence-transformers, error claro si extras ausentes.
  - Factory `get_embedder(mode: "mock"|"local-embed"|"llm")`. `get_default_embedder` queda como alias.
  - Tests `tests/test_embedder.py` + `tests/test_embedder_factory.py`.

- [x] **T6. Doctrine loader (`doctrine/loader.py`)** _(PR #1b)_
  - Lee `manifest.json` + `chunks.jsonl` + `vectors.npy` del colaborador.
  - Fallback `flags/doctrine_stub.yaml` (9 entries OCP/OECD paraphrased).
  - Construye `DoctrineIndex` (cosine en memoria; FAISS no aporta a este volumen).
  - Contrato `DoctrineIndex.query(text, top_k) -> list[DoctrineHit]` con `source`, `section`, `page`, `quote`, `flag_code`, `score`.
  - Tests `tests/test_doctrine.py`: stub fallback, artifact roundtrip, dim mismatch rejection.

- [x] **T7. TDR Index (`retrieval/index.py`)** _(PR #1b)_
  - FAISS `IndexHNSWFlat` (M=32, efConstruction=200, efSearch=64, `METRIC_INNER_PRODUCT`).
  - BM25Okapi reconstruido al cargar (no se serializa).
  - Fusión RRF (k=60) entre vector top-20 y BM25 top-20.
  - Persistencia `~/.cache/document_intelligence/tdr_index/<doc_id>/` con `manifest.json`, `chunks.jsonl`, `vectors.faiss`.
  - Contrato `TDRIndex.query(text, top_k, cluster_filter) -> list[RetrievalHit]` con `vector_score`, `bm25_score`, `score` (RRF), `cluster_hint`.
  - Tests `tests/test_index.py`: build, hybrid, cluster filter, persist/load, embedder mismatch rejection.

## Fase C — Agentes

- [x] **T8. DocumentMapperAgent** _(PR #2)_
  - Heurística regex sobre páginas: detecta secciones canónicas por keywords del catálogo (`flags/cluster_catalog.yaml`).
  - Accent-folding + uppercase matching (`agents/_canonical.py:normalize`).
  - Output: `TDRMap` con `sections: list[DocumentSection]` y `unmatched_pages`.
  - Page-range stitching: cada sección abarca hasta la página anterior a la siguiente heading.
  - Modo LLM diferido a PR #4 (contrato del agente queda estable).
  - Tests `tests/test_document_mapper.py`: detección canónica, ranges densos, unmatched pages.

- [x] **T9. ClusterBuilderAgent** _(PR #2)_
  - Mock mode: match `section_hint` → catálogo; fallback al preview del chunk; fallback final `Otros`.
  - **Contrato congelado**: escribe `chunk.metadata["cluster_label"]` ANTES de cualquier `TDRIndex.build/query`.
  - Output: `(labelled_chunks, list[DocumentCluster])`.
  - Test `tests/test_cluster_builder.py:test_cluster_filter_feeds_tdr_index` verifica que el label producido por el agente alimenta `TDRIndex.query(..., cluster_filter=...)` correctamente.
  - KMeans queda como upgrade opcional para PR #3 cuando aporte recall.

- [x] **T10. PlannerAgent** _(PR #2)_
  - Paso 1 (obligatorio): `doctrine_index.query(question, top_k=10)` — antes de tocar el TDR.
  - Paso 2: extrae `flag_codes` únicos de los doctrine hits → `candidate_flags`.
  - Paso 3: por cada candidate flag carga `cluster_flag_map.yaml` + `planner_queries.yaml` → emite `FlagQuery` records.
  - Enriquecimiento: secciones detectadas en `TDRMap` se incluyen en `clusters_to_query` como exploratorios.
  - `PlannerAudit.doctrine_consulted_first=True` y log `planner.doctrine_consulted_first` permiten verificar el invariante.
  - Test `tests/test_planner.py`: doctrine-first ordering + caplog, queries derivadas de hits, cluster filter ⊆ disponibles, doctrine vacía → plan vacío.

- [x] **T11. RetrieverAgent** _(PR #2)_
  - Ejecuta cada `FlagQuery` con `tdr_index.query(query_text, top_k, cluster_filter=target_clusters or None)`.
  - Output: `list[RetrievalResult]` con `RetrievalHitRecord` por hit (serializable).
  - Test `tests/test_retriever_agent.py`: 1 result por query, cluster filter respetado, plan vacío → results vacíos.

- [x] **T12. RiskAnalysisAgent** _(PR #3)_
  - Rule-based detection per flag: each of 8 supported flags has regex/pattern matching over hit text excerpts.
  - Deduplicates identical quotes across hits. Skips flags with no lexical pattern match.
  - Optionally attaches `DoctrineAnchor` from a `DoctrineIndex` lookup by flag_code.
  - Tests `tests/test_risk_analysis.py`: pattern match, pattern skip, unknown flag, doctrine anchor attachment, dedup.

- [x] **T13. EvidenceCriticAgent** _(PR #3)_
  - Validates that each `FlagCandidate` has: non-empty `evidence_quote`, valid `page_number`, non-empty `chunk_id`.
  - Enforces dual-evidence: rejects flags without `doctrine_anchor` when `require_dual_evidence=True`.
  - Rejects flags below configurable `min_confidence`.
  - Returns `CriticCritique` with `accepted`, `rejected`, and `summary` text.
  - Tests `tests/test_evidence_critic.py`: rejects flag without quote, without chunk_id, without doctrine_anchor, with low confidence, with empty doctrine_anchor.quote.

- [x] **T14. CivicSynthesizerAgent** _(PR #3)_
  - Converts accepted `FlagRecord[]` into an `AnalysisResult` with summary, risk explanation per flag, and questions_for_authority.
  - Legal-safe by construction: no banned vocabulary in templates.
  - Confidence computed from average of individual flag confidences.
  - Empty-flag case returns "No se encontro evidencia suficiente" with `confidence="low"`.
  - Tests `tests/test_civic_synthesizer.py`: output shape, disclaimer, questions, empty case, confidence levels, no banned language.

- [x] **T15. LegalSafetyFilter (`safety/legal_filter.py`)** _(PR #3)_
  - Scans text for 15 banned terms (corrupto, fraude, ilegal, delito, culpable, criminal, etc.).
  - Three modes: `reject` (raises `BannedTermFoundError`), `sanitize` (replaces terms with safe alternatives), `flag` (passes with warning).
  - `check_analysis()` convenience method validates an `AnalysisResult` by scanning summary + questions.
  - Default mode: `reject` in production.
  - Tests `tests/test_legal_safety_filter.py`: blocks corrupto, blocks fraude, blocks criminal, allows legal-safe language, sanitize replaces terms, flag mode warns, multiple terms detected.

## Fase D — Orquestación y CLI

- [x] **T16. Orchestrator (`agents/orchestrator.py`)**
  - Función `analyze_pdf(pdf_path, question, mode) -> AnalysisResult`.
  - Cachea índices en `~/.cache/document_intelligence/`.
  - Logs estructurados por etapa (lista de dicts en `OrchestratorState.logs`).
  - Retry loop CRIT→PLAN máximo 1 vez (dobla `retriever_top_k`).

- [x] **T17. CLI (`cli.py`)**
  - Click commands: `inspect-pdf`, `chunk-pdf`, `build-index`, `doctrine-info`, `analyze`.
  - `--mode {mock,local-embed,llm}` flag (default `mock`).
  - `--output <path>` para JSON; stdout si omitido.
  - `--pretty` para pretty-print.

## Fase E — Calidad y docs

- [x] **T18. Tests end-to-end**
  - Fixture PDF sintético con secciones controladas (incluye al menos 2 trampas que disparan flags).
  - `tests/test_orchestrator_e2e.py`: 10 tests que corren `analyze_pdf` y validan shape, flags esperadas, legal-safe, JSON serializable, retry loop, sin API keys.
  - Tests de legal safety existentes (`test_legal_safety_filter.py`): 26 tests pasan.
  - Tests de evidence critic (`test_evidence_critic.py`): 16 tests pasan.

- [x] **T19. `docs/AGENT_DOCUMENT_CORE.md`**
  - Arquitectura conceptual actualizada con orchestrator.
  - Diagrama Mermaid del pipeline (8 agentes + retry loop).
  - Tabla de agentes con responsabilidad + input + output.
  - Ejemplo end-to-end con fixture.
  - Limitaciones conocidas.
  - Roadmap (Actividad 2, 3, 4, 5).

- [x] **T20. Quality gates**
  - `uv run --extra dev pytest tests/` → 124 passed.
  - `uv run --extra dev ruff check src tests` → All checks passed.
  - `uv run --extra dev pyright` → 0 errors.
  - CI no agregado (fuera de scope hackathon).

## Fase F — Post-MVP (no en este PR)

- [ ] **T21 [opt]. CompareAgent**: comparación entre 2 TDRs (similitudes, requisitos repetidos, patrones).
- [ ] **T22 [opt]. DossierBuilderAgent**: convierte `AnalysisResult` en dossier ciudadano.
- [ ] **T23 [opt]. Adapter pgvector**: reemplaza FAISS local cuando exista Supabase.
- [ ] **T24 [opt]. Adapter web**: endpoint Next.js que consume orchestrator.

## Orden de PRs sugerido

1. **PR #1**: T0–T7 (scaffolding + datos). Verde antes de tocar agentes.
2. **PR #2**: T8–T11 (mapper + cluster + planner + retriever) con tests mock.
3. **PR #3**: T12–T15 (risk + critic + synthesizer + safety) con tests legal-safe.
4. **PR #4**: T16–T20 (orchestrator + CLI + docs + quality).

Cada PR cierra con commit `... (SPEC-0007)`.
