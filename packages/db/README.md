# @agenteperry/db

Postgres migrations for AgentePerry TDR Scanner.

## Active Migrations

| # | File | Content |
|---|------|---------|
| 0001 | `extensions.sql` | `pgcrypto`, `vector`, `pg_trgm`, `unaccent`, `btree_gin` |
| 0002 | `tdr_core.sql` | `tdr_documents`, `tdr_pages`, `tdr_chunks`, `tdr_embeddings`, `tdr_flags` |

## Apply

```bash
psql "$SUPABASE_DB_URL" -f migrations/0001_extensions.sql
psql "$SUPABASE_DB_URL" -f migrations/0002_tdr_core.sql
```

## Deferred

Entities, relationships, contracts, alerts, legal RAG and Civic Amplifier tables are outside the current MVP.
