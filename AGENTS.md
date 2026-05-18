# AGENTS.md — AgentePerry TDR Scanner

Instrucciones para agentes de codigo que colaboran en este repo.

## Current MVP Focus

El MVP actual es **AgentePerry TDR Scanner**.

Implementar solo:

- TDR document ingestion.
- PDF parsing.
- Text cleaning.
- Chunking.
- Embeddings para busqueda.
- Rule-based TDR flags.
- Evidence-backed dossier API.

No implementar ahora:

- ONPE.
- JNE.
- SUNARP.
- Graphiti.
- Neo4j.
- ConflictMap full.
- Civic Amplifier full.
- Mapa nacional.
- Campanas SMS.
- Deteccion automatica de corrupcion.

## Antes de escribir codigo

1. Debe existir un `SPEC-NNNN` en `specs/active/` que justifique el cambio.
2. La rama debe seguir `<tipo>/SPEC-NNNN-slug`.
3. El commit debe terminar con `(SPEC-NNNN)` salvo docs-only/hotfix menor.
4. Si toca area de otro owner, pedir cross-review segun `TEAM.md` y `.github/CODEOWNERS`.

## Principio legal-safe

No acusamos corrupcion. Detectamos senales de riesgo con evidencia publica.

Prohibido en UI/copy/dossiers:

- "robo"
- "corrupto"
- "mafioso"
- "culpable"
- "delincuente"
- "delito"

Usar:

- "presenta senales de riesgo"
- "merece revision"
- "requiere explicacion"
- "patron atipico"

Toda evidencia debe incluir cita textual, pagina y fuente cuando exista.

## Orden de Implementacion

1. `SPEC-0000-focus-tdr-mvp`: limpieza, docs, specs y schema base.
2. `SPEC-0001-tdr-manual-loader`: cargar metadata CSV en `tdr_documents`.
3. `SPEC-0002-tdr-pdf-parser`: extraer texto por pagina en `tdr_pages`.
4. `SPEC-0003-tdr-chunk-embeddings`: chunks + embeddings consultables.
5. `SPEC-0004-tdr-rule-based-flags`: flags con evidencia.
6. `SPEC-0005-tdr-dossier-api`: API minima para demo.

No saltar de fase si la anterior no tiene datos verificables.

## Stack

| Capa | Tech | Uso MVP |
|------|------|---------|
| Scrapers | Python 3.11+, uv, Click, PyMuPDF | Pipeline TDR |
| DB | Supabase Postgres + pgvector | TDR docs/pages/chunks/embeddings/flags |
| Web/API | Next.js App Router | Solo dossier API/demo posterior |
| AI | Embeddings provider configurable | Busqueda, no scoring |

## Estructura

```text
apps/scrapers/src/agenteperry/
  cli.py
  tdr/
    ingestion.py
    parsing.py
    chunking.py
    embeddings.py
    flags.py
    search.py
    models.py
packages/db/migrations/
  0001_extensions.sql
  0002_tdr_core.sql
docs/
  INDEX.md             indice maestro
  DATA_SOURCES.md      catalogo de fuentes
  LEGACY.md            rama legacy y vision anterior
  AGENTS_OPENCODE.md   guia de uso eficiente de agentes
  reference/           Inteligencia del legacy integrada al codebase
    legacy-platform.md
```

## Calidad minima

- `uv run --extra dev pytest`
- `uv run --extra dev ruff check src tests`
- `uv run --extra dev pyright`
- No commitear data real, PDFs, CSVs grandes, JSONL, ZIPs, `.env` ni credenciales.
- La investigacion previa vive en la rama `legacy/contralatam-platform`; no editar.

## Agent Skills

Este repo incluye skills de proyecto para Claude Code, OpenCode y Codex-compatible agents.

- Ver matriz: `docs/AGENT_SKILLS.md`.
- Reinstalar: `bash scripts/install-agent-skills.sh`.
- Verificar: `npx skills list --json`.
- No usar skills de Graphiti/Neo4j/ConflictMap hasta que exista spec activo.

## Git

- Branch: `chore/SPEC-0000-focus-tdr-mvp`, `feat/SPEC-0001-tdr-manual-loader`, etc.
- Commit: `docs(scope): focus MVP on TDR Scanner (SPEC-0000)`.
- PR: un spec por PR cuando sea posible.
