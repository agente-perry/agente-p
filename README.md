# AgentePerry TDR Scanner

AgentePerry analiza Terminos de Referencia publicos para detectar senales de baja trazabilidad, requisitos restrictivos y entregables obsoletos antes de que el contrato sea adjudicado.

No acusa corrupcion. Genera evidencia textual, preguntas para revision y una base estructurada para que ciudadanos, periodistas o entidades entiendan que TDRs merecen mayor revision.

> **Arquitectura canonica**: ver [`docs/ARCHITECTURE_AGENTEPERRY.md`](docs/ARCHITECTURE_AGENTEPERRY.md). Define la tesis, las 5 fases, la regla de activacion de GraphRAG y lo que NO se debe construir todavia.
>
> **Backend unificado**: ver [`docs/BACKEND_UNIFIED_ARCHITECTURE.md`](docs/BACKEND_UNIFIED_ARCHITECTURE.md). Explica como conviven FastAPI, `document_intelligence`, GCS, Neo4j existente y `data/PDF-Base` como corpus doctrinal publico.

## MVP Hack@Latam

El MVP actual es un solo flujo:

```text
TDR ingestion -> PDF parsing -> text cleaning -> chunking -> embeddings -> rule-based flags -> evidence-backed dossier API
```

El sprint activo se enfoca en:

1. Cargar metadata de TDRs publicos en PDF.
2. Extraer texto limpio por pagina.
3. Dividir documentos en chunks consultables.
4. Crear embeddings para busqueda semantica.
5. Detectar senales iniciales con reglas explicables.
6. Guardar evidencia textual y numero de pagina.
7. Preparar un dossier preventivo via API.

## Fuera del MVP

No implementar ahora:

- ONPE, JNE, SUNARP.
- ConflictMap completo.
- Graphiti o Neo4j.
- Mapa nacional.
- SMS masivo.
- Civic Amplifier completo.
- Deteccion automatica de corrupcion.

Todo eso queda como roadmap post-MVP.

## Estructura

```text
apps/
  api/                 FastAPI backend: GCS + Neo4j + AuditorGraph bridge
  scrapers/            foco principal: paquete Python agenteperry
  web/                 demo visual posterior y dossier API cuando toque SPEC-0005
packages/
  document_intelligence/ motor documental: parse, chunks, retrieval, flags, critic, safety
  db/migrations/       schema TDR minimo para Supabase/Postgres + pgvector
  shared/              tipos compartidos futuros
docs/
  INDEX.md             indice maestro para humanos y agentes
  ARCHITECTURE.md      arquitectura TDR Scanner
  SCRAPING.md          ingesta TDR y reglas de datos
  METHODOLOGY.md       metodologia legal-safe y flags TDR
  PLAN.md              sprints MVP
  DATA_SOURCES.md      catalogo de fuentes y prioridades
  LEGACY.md            rama legacy y vision anterior
  AGENTS_OPENCODE.md   guia de uso eficiente de agentes
  AGENT_SKILLS.md      skills instalados para agentes
  reference/           documentos de referencia (inteligencia integrada)
specs/
  active/              specs del sprint TDR actual
  deferred/            specs legacy fuera del MVP
data/
  PDF-Base/            unica excepcion versionada: PDFs publicos de doctrina
  README.md            reglas para data local no versionada
```

## Quick Start

```bash
cd apps/scrapers
uv sync --extra dev
uv run agenteperry tdr index
```

Ejemplo local con archivos no versionados:

```bash
uv run agenteperry tdr load-manual ../../data/manual_tdrs/metadata.csv
uv run agenteperry tdr parse ../../storage/raw/tdr/demo.pdf --out ../../storage/processed/tdr/demo.pages.json
uv run agenteperry tdr chunk ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.chunks.json
uv run agenteperry tdr embed-inputs ../../storage/processed/tdr/demo.chunks.json --out ../../storage/processed/tdr/demo.embedding-inputs.json
uv run agenteperry tdr flags ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.flags.json
uv run agenteperry tdr smoke-search ../../storage/processed/tdr/demo.chunks.json "formato A3"
```

## Sprints

| Sprint | Foco | Entregable verificable |
|--------|------|------------------------|
| 0 | Limpieza y foco | Repo comunica AgentePerry TDR Scanner en menos de 2 minutos |
| 1 | Data Core | `tdr_documents` y `tdr_pages` con 5-20 PDFs reales |
| 2 | Chunks + Embeddings | Busqueda semantica devuelve fragmentos con pagina y fuente |
| 3 | Flags | `tdr_flags` contiene `evidence_quote` + `page_number` |
| 4 | Dossier API | `GET /api/tdr/{id}` devuelve flags, score y preguntas de revision |

## Specs Activos

| ID | Nombre | Owner |
|----|--------|-------|
| [SPEC-0000](specs/active/SPEC-0000-focus-tdr-mvp/spec.md) | Focus TDR MVP | Miguel |
| [SPEC-0001](specs/active/SPEC-0001-tdr-manual-loader/spec.md) | TDR Manual Loader | John |
| [SPEC-0002](specs/active/SPEC-0002-tdr-pdf-parser/spec.md) | TDR PDF Parser | John |
| [SPEC-0003](specs/active/SPEC-0003-tdr-chunk-embeddings/spec.md) | TDR Chunking + Embeddings | Anthony |
| [SPEC-0004](specs/active/SPEC-0004-tdr-rule-based-flags/spec.md) | TDR Rule-Based Flags | Miguel / Anthony |
| [SPEC-0005](specs/active/SPEC-0005-tdr-dossier-api/spec.md) | TDR Dossier API | Anthony / Noelia |

## Principio Rector

No acusamos corrupcion. Detectamos senales de riesgo basadas en evidencia publica.

Usar lenguaje legal-safe:

- Si: "presenta senales de riesgo", "merece revision", "requiere explicacion", "patron atipico".
- No: "robo", "corrupto", "mafioso", "culpable", "delincuente".

## Rama Legacy

La visión anterior del proyecto (Contralatam Agent, ConflictMap, Graphiti, Civic Amplifier, 25+ fuentes) vive preservada en la rama `legacy/contralatam-platform`.

```bash
# Ver la visión completa anterior
git checkout legacy/contralatam-platform

# Volver al MVP
git checkout main
```

No traer componentes legacy a `main` sin crear primero un spec activo. Ver [`docs/LEGACY.md`](docs/LEGACY.md).

## Uso de Agentes de Código (OpenCode)

Usamos OpenCode intensivamente. Para no desperdiciar créditos ni contexto:

1. **Scope explícito:** "Trabaja en SPEC-0001", no "implementa scraping".
2. **Repo limpio:** `main` solo tiene TDR Scanner. Legacy está aislado.
3. **Verificación local:** Corre `pytest`, `ruff`, `pyright` antes de pedir ayuda.
4. **Iteración corta:** Un cambio, una verificación, siguiente cambio.

Guía completa: [`docs/AGENTS_OPENCODE.md`](docs/AGENTS_OPENCODE.md).

## Colaboracion

Lee en orden:

1. `README.md`
2. [`AGENTS.md`](AGENTS.md)
3. [`TEAM.md`](TEAM.md)
4. [`docs/INDEX.md`](docs/INDEX.md)
5. [`specs/README.md`](specs/README.md)
6. El spec activo que vas a tomar.

## Agent Skills

El repo incluye skills instalados para Claude Code, OpenCode y Codex-compatible agents.

```bash
npx skills list --json
bash scripts/install-agent-skills.sh
```

Detalles: [`docs/AGENT_SKILLS.md`](docs/AGENT_SKILLS.md).
