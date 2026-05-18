# Architecture — AgentePerry TDR Scanner

## MVP Boundary

AgentePerry is a preventive scanner for public TDR documents. It does not build a full procurement graph in the MVP.

```text
CSV metadata + local/public PDFs
  -> Manual loader
  -> PDF parser
  -> Page text cleaning
  -> Chunking
  -> Embedding inputs / vector storage
  -> Rule-based flags
  -> Evidence-backed dossier API
```

## Active Components

| Layer | Path | Purpose |
|-------|------|---------|
| CLI | `apps/scrapers/src/agenteperry/cli.py` | Run local TDR pipeline commands |
| TDR core | `apps/scrapers/src/agenteperry/tdr/` | Ingestion, parsing, chunking, embeddings, flags, search |
| DB | `packages/db/migrations/0002_tdr_core.sql` | Minimal TDR schema |
| Data docs | `data/README.md` | Rules for local non-versioned data |
| Specs | `specs/active/` | Current implementation sequence |

## Deferred Components

The old platform vision is preserved in `docs/reference/` and deferred specs live in `specs/deferred/`.

Deferred until post-MVP:

- ConflictMap full.
- Entity graph and Graphiti.
- Neo4j.
- ONPE/JNE/SUNARP enrichment.
- Civic Amplifier full.
- SMS campaigns.
- National map.

## Data Flow

1. `SPEC-0001`: CSV metadata validates required columns and upserts `tdr_documents`.
2. `SPEC-0002`: PDF parser writes `tdr_pages` with clean page text.
3. `SPEC-0003`: chunker writes `tdr_chunks`; embedding worker writes `tdr_embeddings`.
4. `SPEC-0004`: flag engine writes `tdr_flags` with evidence quote and page number.
5. `SPEC-0005`: API returns a dossier payload for the demo UI.
