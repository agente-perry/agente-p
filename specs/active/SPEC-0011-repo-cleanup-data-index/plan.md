# SPEC-0011: Repo Cleanup, Data Centralization, and Data Index

## Plan de implementacion

### Fase 1 — Estructura del spec
- [x] spec.md creado
- [ ] plan.md creado
- [ ] tasks.md creado

### Fase 2 — Directorios y archivos
- [ ] Crear `data/scraped/ocds/` y mover `data/raw/ocds/`, `data/derived/ocds/`
- [ ] Crear `data/scraped/filtered/` y mover `data/filtered/`
- [ ] Crear `data/scraped/tdrs/` y mover `data/tdrs/`
- [ ] Crear `data/scraped/manual_tdrs/` y mover `data/manual_tdrs/`
- [ ] Crear `data/scraped/tdr_recon/` y mover `data/tdr_recon/`
- [ ] Crear `data/scraped/collectors/` (directorio vacío futuro)
- [ ] Crear `data/scraped/README.md` con descripción del directorio

### Fase 3 — Index y leyenda
- [ ] Escribir `data/INDEX.md` con:
  - Mapa del directorio
  - Schema de cada archivo
  - Tabla de fuentes
  - Leyenda para equipo de Grafos
- [ ] Escribir `data/scraped/ocds/metadata.json` con schema y stats
- [ ] Escribir `data/scraped/filtered/metadata.json` con schema y stats

### Fase 4 — Código
- [ ] Actualizar `tdr_discovery.py`: `data/filtered/` y `data/tdr_recon/`
- [ ] Actualizar `run_golden_set.py`: `data/golden_set/`
- [ ] Actualizar `cli.py`: docstring `data/tdrs/`
- [ ] Actualizar `test_source_chunks.py`: fixture `data/raw/`

### Fase 5 — Specs
- [ ] Archivar `SPEC-0006-source-registry-and-traceability` en `specs/archived/`
- [ ] Dejar `SPEC-0006-source-registry-traceability` como spec oficial
- [ ] Actualizar `specs/_next.txt` a 0012

### Fase 6 — Verificacion
- [ ] `uv run --extra dev pytest`
- [ ] `uv run --extra dev ruff check src tests`
- [ ] `uv run --extra dev pyright`
- [ ] `uv run --extra dev agenteperry tdr index`
