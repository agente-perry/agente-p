# AGENTS.md

Instructions for AI coding agents collaborating on this repository.

## Project

Multi-agent system to detect risk signals in Peruvian public procurement
documents (TDRs), using only public evidence. Methodology references the
public FUNES framework from Ojo Publico.

## Working principle

- We do not accuse. We surface signals with traceable public evidence.
- Every flag must cite the source document fragment that produced it.
- Output is investigative material, not a verdict.

## Stack

- Python 3.11+ (scrapers, document intelligence, API)
- Next.js 15 (web dossier UI)
- Supabase Postgres + pgvector
- Neo4j (entity graph)
- AI SDK with provider routing

## Repo layout

```
apps/
  api/              FastAPI orchestrator
  scrapers/         Ingestion and parsing agents
  web/              Next.js dossier UI
packages/
  document_intelligence/   Doctrine-anchored analysis agents
  db/                      Postgres migrations and seed data
  shared/                  Shared types and utilities
infra/
  docker/           Local dev compose
  supabase/         Supabase config
```

## Conventions

- Branches: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`, `docs/<slug>`.
- Commits: imperative subject, ~70 chars max.
- Direct push to `main` is prohibited. All changes go through PR.
- No real personal data, credentials, or non-public material in commits.
- No identifying information about contributors in code or docs.

## Code style

- Python: ruff + black defaults, type hints required on public APIs.
- TypeScript: project ESLint + Prettier config.
- Tests required for new agent logic and new scrapers.
