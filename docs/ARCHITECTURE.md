# Architecture

Multi-agent pipeline for analyzing Peruvian public procurement TDR documents
and surfacing risk signals with traceable evidence.

## Pipeline

```text
Public TDR sources
    -> Discovery / ingestion agents
    -> PDF parsing + OCR fallback
    -> Page cleaning + chunking
    -> Embedding + vector storage (pgvector)
    -> Doctrine-anchored risk analysis agents
    -> Entity graph enrichment (Neo4j)
    -> Evidence-backed dossier API
    -> Web dossier UI
```

## Components

| Layer | Path | Purpose |
|-------|------|---------|
| API | `apps/api/` | FastAPI orchestrator, dossier endpoints |
| Scrapers | `apps/scrapers/` | Ingestion CLI, PDF parser, chunker, flag engine |
| Web | `apps/web/` | Next.js 15 dossier UI |
| Document intelligence | `packages/document_intelligence/` | Planner, evidence critic, risk-scoring agents, doctrine index |
| DB | `packages/db/` | Postgres migrations, source registry, schema |
| Shared | `packages/shared/` | Cross-package types |
| Infra | `infra/` | Docker compose, Supabase config |

## Data flow

1. Ingestion: discovery agents pull public procurement documents and metadata.
2. Parsing: PDF parser extracts text with OCR fallback for scanned pages.
3. Chunking + embeddings: page-aligned chunks with pgvector storage for retrieval.
4. Doctrine retrieval: legal-doctrine index supplies precedents to the analysis agents.
5. Risk analysis: planner -> evidence critic -> risk-scoring agents produce flags with quote and page citation.
6. Graph enrichment: entity graph adds context for conflict-of-interest signals.
7. Dossier API: returns a structured, evidence-backed report for the web UI.

## Storage

- Supabase Postgres with pgvector for documents, pages, chunks, embeddings, and flags.
- Neo4j for the entity graph.
- Object storage for raw PDFs (out of repository).

## Methodology

Risk signal taxonomy and language conventions are documented in
[`METHODOLOGY.md`](METHODOLOGY.md). The framework references the public FUNES
methodology published by Ojo Publico.
