# Guía de Uso de Agentes de Código (OpenCode, Claude, Codex)

Este proyecto usa intensivamente agentes de código. Esta guía explica cómo sacarle el máximo provecho sin desperdiciar créditos, tiempo ni contexto.

## El problema: ruido = costo

Los agentes de código (OpenCode, Claude Code, Codex) tienen **ventanas de contexto limitadas**. Si el repo tiene:
- Archivos legacy que dicen "implementar X" (aunque haya un `AGENTS.md` que diga lo contrario)
- 25 fuentes diferentes sin prioridad
- 3 arquitecturas diferentes en docs distintos

...el agente inevitablemente los leerá, los mezclará y tomará decisiones malas. Eso genera:
- Código fuera del MVP
- Commits que hay que revertir
- Créditos desperdiciados
- Tiempo perdido

## Solución: repo limpio + contexto explícito

### 1. Estructura anti-ruido

```text
main (limpia)
  README.md           -> Qué es y cómo empezar (2 minutos)
  AGENTS.md           -> Qué SÍ y qué NO implementar
  docs/INDEX.md       -> Mapa de navegación
  specs/active/       -> Solo lo que se implementa AHORA
  
legacy/contralatam-platform (completa)
  hackl@latam/        -> Investigación previa
  Contralatam Agent   -> Visión anterior
  25 fuentes          -> Catálogo completo
```

**Regla:** Si un archivo confunde más de lo que ayuda, no va en `main`.

### 2. Cómo empezar una sesión con un agente

**Mal:**
```
"Implementa scraping de SUNAT"
```
→ El agente busca SUNAT en el repo, encuentra `specs/deferred/SPEC-0002-sunat-padron-collector/`, lo lee, y empieza a implementar algo fuera del MVP.

**Bien:**
```
"Trabaja en SPEC-0001-tdr-manual-loader. Lee specs/active/SPEC-0001-tdr-manual-loader/spec.md y tasks.md. No implementes nada fuera de ese spec."
```
→ El agente tiene un scope acotado y verificable.

### 3. Prompts efectivos para OpenCode

#### Iniciar trabajo en un spec

```text
Eres un desarrollador Python trabajando en AgentePerry TDR Scanner.

REGLAS:
- Lee AGENTS.md antes de escribir código.
- El MVP es TDR Scanner. No implementes OCDS, SUNAT, ConflictMap, Neo4j ni Civic Amplifier.
- Usa lenguaje legal-safe: "presenta señales de riesgo", nunca "corrupto".
- Un spec = un outcome. Este es el spec activo: specs/active/SPEC-NNNN-slug/
- Escribe tests. Verifica con: uv run --extra dev pytest
- Verifica estilo con: uv run --extra dev ruff check src tests

TAREA:
[Describe la tarea específica del spec]
```

#### Pedir revisión de código

```text
Revisa este código para:
1. Cumplir con AGENTS.md (foco TDR Scanner, legal-safe)
2. Tener tests
3. No importar módulos legacy (contralatam, ocds, sunat)
4. Usar el schema activo en packages/db/migrations/0002_tdr_core.sql

Código:
[Pega el código]
```

#### Debugging

```text
Este test falla: [pega error]

Contexto:
- Estoy en SPEC-0002-tdr-pdf-parser
- El schema es packages/db/migrations/0002_tdr_core.sql
- No uses Neo4j ni Graphiti.

Encuentra la causa raíz y propón un fix mínimo.
```

### 4. Cómo ahorrar créditos de OpenCode

| Técnica | Ahorro |
|---------|--------|
| **Scope explícito** | Evita que el agente explore 25 fuentes legacy |
| **Spec-driven** | Un spec = un outcome. No "explora y vemos qué pasa" |
| **Verificación local** | Corre `pytest`, `ruff`, `pyright` antes de pedir ayuda |
| **Contexto mínimo** | No pegues 500 líneas de código si el error está en 3 |
| **Iteración corta** | Pide un cambio, verifícalo, luego el siguiente. No "haz todo" |

### 5. Anti-patrones comunes

| Anti-patrón | Por qué falla |
|-------------|---------------|
| "Implementa todo el catálogo de fuentes" | El agente no sabe priorizar. Implementará P3 antes que P0. |
| "Arregla todos los bugs" | Sin lista específica, el agente inventa bugs. |
| "Haz el proyecto más robusto" | Vago. El agente agregará abstracciones innecesarias. |
| "Mira hackl@latam/ para entender la arquitectura" | Legacy confuso. Usa `docs/ARCHITECTURE.md` activo. |

### 6. Comandos útiles para verificar antes de pedir ayuda

```bash
# Tests pasan?
cd apps/scrapers && uv run --extra dev pytest

# Estilo correcto?
cd apps/scrapers && uv run --extra dev ruff check src tests

# Tipos correctos?
cd apps/scrapers && uv run --extra dev pyright

# Qué specs están activos?
ls specs/active/

# Qué he cambiado?
git diff --name-only
```

### 7. Skills instalados

El repo tiene skills específicos para agentes:

```bash
# Ver skills disponibles
npx skills list --json

# Reinstalar skills
bash scripts/install-agent-skills.sh
```

Skills relevantes para este proyecto:
- `agenteperry-tdr-scanner` — Guardrail local: bloquea trabajo fuera del MVP TDR.
- `python-backend` — FastAPI, Postgres, seguridad.
- `supabase` — Auth, DB, Edge Functions.
- `best-practices` — Seguridad, calidad, compatibilidad.

## Resumen para el equipo

1. **Antes de abrir OpenCode:** saber qué spec estás implementando.
2. **Durante la sesión:** dar scope explícito, verificar localmente, iterar en pasos pequeños.
3. **Después de la sesión:** commitear con referencia al spec (`(SPEC-NNNN)`), abrir PR.
4. **Si algo falla:** no reinicies desde cero. Revisa `docs/INDEX.md` y el spec activo.
