# CLAUDE.md

Este archivo redirige a [`AGENTS.md`](AGENTS.md), que es la fuente única de instrucciones para todos los agentes de código (Claude Code, OpenCode, Cursor, etc.).

Lee `AGENTS.md` antes de empezar a trabajar.

**Resumen rápido:**

- **Proyecto actual:** AgentePerry TDR Scanner.
- **Principio rector:** No acusamos corrupción. Detectamos señales con evidencia pública.
- **Stack:** Next.js 15 + Python scrapers + Supabase (pgvector).
- **Fase actual:** TDR ingestion → PDF parsing → chunking → embeddings → rule-based flags → dossier API. Ver [`docs/PLAN.md`](docs/PLAN.md).
- **Investigación previa:** La visión anterior (Contralatam Agent, ConflictMap, Civic Amplifier) vive en la rama `legacy/contralatam-platform`.
