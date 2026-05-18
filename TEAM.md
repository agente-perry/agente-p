# TEAM.md — AgentePerry TDR Scanner

Equipo Hack@Latam. Cada persona tiene un foco operativo para evitar que el MVP se disperse.

## Miembros

| Persona | Rol funcional | Responsabilidad real | Areas owned |
|---------|---------------|----------------------|-------------|
| Miguel | Tech Lead / DB | Schema, specs, flags, pitch, calidad final | `packages/db/`, `specs/`, `AGENTS.md`, `CONSTITUTION.md` |
| John | Data Engineer | PDFs, loader manual, parser, limpieza de texto | `apps/scrapers/src/agenteperry/tdr/ingestion.py`, `parsing.py`, data fixtures |
| Anthony | Backend / AI | Embeddings, API, persistencia, flag engine | `apps/scrapers/src/agenteperry/tdr/embeddings.py`, `apps/web/app/api/`, `flags.py` |
| Noelia | Frontend / UX | Dossier UI, visualizacion, demo final | `apps/web/`, `packages/shared/`, UX del dossier |

## Specs del Sprint Actual

| SPEC | Owner | Reviewer |
|------|-------|----------|
| SPEC-0000 Focus TDR MVP | Miguel | Anthony |
| SPEC-0001 TDR Manual Loader | John | Miguel |
| SPEC-0002 TDR PDF Parser | John | Anthony |
| SPEC-0003 TDR Chunking + Embeddings | Anthony | Miguel |
| SPEC-0004 TDR Rule-Based Flags | Miguel / Anthony | John |
| SPEC-0005 TDR Dossier API | Anthony / Noelia | Miguel |

## Reglas de Colaboracion

- Un PR debe apuntar a un spec activo.
- Cross-review obligatorio si toca DB + scrapers + web.
- Nadie implementa modulos diferidos sin mover primero un spec desde `specs/deferred/` a `specs/active/`.
- Direct push a `main` prohibido.
- Data real no se commitea.

## Branches

| Tipo | Patron | Ejemplo |
|------|--------|---------|
| Chore | `chore/SPEC-NNNN-slug` | `chore/SPEC-0000-focus-tdr-mvp` |
| Feature | `feat/SPEC-NNNN-slug` | `feat/SPEC-0001-tdr-manual-loader` |
| Fix | `fix/SPEC-NNNN-slug` | `fix/SPEC-0004-flag-regex` |
| Docs | `docs/SPEC-NNNN-slug` | `docs/SPEC-0000-readme-focus` |
