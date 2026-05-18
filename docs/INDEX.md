# Índice del Repositorio — AgentePerry TDR Scanner

Documento maestro para humanos y agentes de código. Si llegas por primera vez, lee en este orden.

## 1. Qué es este proyecto

AgentePerry TDR Scanner analiza Términos de Referencia públicos para detectar señales de baja trazabilidad, requisitos restrictivos y entregables obsoletos **antes** de que el contrato sea adjudicado.

No acusamos corrupción. Generamos evidencia textual, preguntas para revisión y una base estructurada para que ciudadanos, periodistas o entidades entiendan qué TDRs merecen mayor revisión.

## 2. Lectura obligatoria (en orden)

| Orden | Archivo | Para qué |
|-------|---------|----------|
| 1 | [`README.md`](../README.md) | Quick start, estructura, specs activos |
| 2 | [`AGENTS.md`](../AGENTS.md) | Reglas operativas para agentes de código |
| 3 | [`TEAM.md`](../TEAM.md) | Roles, owners, reglas de colaboración |
| 4 | [`CONSTITUTION.md`](../CONSTITUTION.md) | SDD, principio legal-safe, git rules |
| 5 | [`docs/PLAN.md`](PLAN.md) | Sprints MVP y entregables verificables |

## 3. Documentos por tema

### Para agentes de código (OpenCode, Claude, Codex)

| Archivo | Contenido |
|---------|-----------|
| [`AGENTS.md`](../AGENTS.md) | Reglas de oro: qué implementar, qué NO implementar, legal-safe |
| [`docs/AGENTS_OPENCODE.md`](AGENTS_OPENCODE.md) | Cómo usar OpenCode sin desperdiciar créditos ni contexto |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | Componentes activos, data flow, deferred |
| [`docs/ARCHITECTURE_AGENTEPERRY.md`](ARCHITECTURE_AGENTEPERRY.md) | Arquitectura canónica por fases: auditor → score → GraphRAG diferido |
| [`docs/BACKEND_UNIFIED_ARCHITECTURE.md`](BACKEND_UNIFIED_ARCHITECTURE.md) | Backend unificado: FastAPI, document_intelligence, GCS, Neo4j y PDF-Base |
| [`docs/AUDITOR_AGENT_EVALUATION.md`](AUDITOR_AGENT_EVALUATION.md) | Evaluación del Agente Auditor: nivel, APIs/modelos, runs y próximos PRs |
| [`docs/METHODOLOGY.md`](METHODOLOGY.md) | Metodología de flags, lenguaje legal-safe |

### Para desarrolladores

| Archivo | Contenido |
|---------|-----------|
| [`docs/SCRAPING.md`](SCRAPING.md) | Ingesta TDR, reglas de datos, pipelines |
| [`docs/DATA_SOURCES.md`](DATA_SOURCES.md) | Catálogo de fuentes, prioridad, owners, estado |
| [`docs/LEGACY.md`](LEGACY.md) | Qué vive en la rama legacy y cómo acceder |

### Specs (Spec-Driven Development)

| Carpeta | Estado |
|---------|--------|
| [`specs/active/`](../specs/active/) | Specs del sprint actual. Solo estos se implementan. |
| [`specs/deferred/`](../specs/deferred/) | Post-MVP. No implementar sin mover a active/ primero. |
| [`specs/completed/`](../specs/completed/) | Mergeados y verificados. |
| [`specs/_template/`](../specs/_template/) | Plantilla para nuevos specs. |

## 4. Estructura del repo

```text
apps/
  api/                 FastAPI backend (GCS + Neo4j + AuditorGraph)
  scrapers/            Paquete Python agenteperry (foco principal)
  web/                 Demo visual y dossier API (SPEC-0005)
packages/
  document_intelligence/ Motor documental y doctrina
  db/migrations/       Schema TDR mínimo (Postgres + pgvector)
  shared/              Tipos compartidos futuros
docs/
  INDEX.md             Este archivo
  PLAN.md              Sprints MVP
  ARCHITECTURE.md      Arquitectura activa
  SCRAPING.md          Reglas de ingesta
  METHODOLOGY.md       Metodología legal-safe
  DATA_SOURCES.md      Catálogo de fuentes
  LEGACY.md            Rama legacy y visión anterior
  AGENTS_OPENCODE.md   Guía de uso eficiente de agentes
  AGENT_SKILLS.md      Skills instalados para agentes
  archive/             Documentos históricos
specs/
  active/              Specs en implementación
  deferred/            Specs post-MVP
  completed/           Specs terminados
data/
  PDF-Base/            Única excepción versionada: doctrina pública en PDF
  README.md            Reglas para data local no versionada
```

## 5. Quick Start

```bash
cd apps/scrapers
uv sync --extra dev
uv run agenteperry tdr index
```

## 6. Reglas de oro para no perderse

1. **Un spec = un outcome.** Si no hay spec en `specs/active/`, no se escribe código.
2. **MVP único:** AgentePerry TDR Scanner. Nada más.
3. **Legal-safe:** "presenta señales de riesgo", nunca "corrupto" o "robo".
4. **Data real NO se commitea.** Única excepción: `data/PDF-Base/` con doctrina pública versionada.
5. **Legacy aislado:** La visión anterior vive en `legacy/contralatam-platform`.
