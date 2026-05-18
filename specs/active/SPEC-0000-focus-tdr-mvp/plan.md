# PLAN — SPEC-0000

## Cambios

- Rebrand a AgentePerry TDR Scanner.
- Legacy a `docs/archive/` y `specs/deferred/`.
- Paquete Python activo `agenteperry`.
- Migraciones activas solo para TDR.

## Verificacion

```bash
cd apps/scrapers
uv run --extra dev pytest
uv run --extra dev ruff check src tests
uv run --extra dev pyright
uv run --extra dev agenteperry tdr index
```
