# TASKS — SPEC-0011

## Fase 1: Spec
- [x] T-01 — spec.md creado [@miguel] [0.2h]
- [x] T-02 — plan.md creado [@miguel] [0.2h]
- [x] T-03 — tasks.md creado [@miguel] [0.2h]

## Fase 2: Directorios
- [ ] T-10 — Crear directorios `data/scraped/{ocds,filtered,tdrs,manual_tdrs,tdr_recon,collectors}` [@miguel] [0.1h]
- [ ] T-11 — Mover `data/raw/ocds/` y `data/derived/ocds/` → `data/scraped/ocds/` [@miguel] [0.2h]
- [ ] T-12 — Mover `data/filtered/` → `data/scraped/filtered/` [@miguel] [0.2h]
- [ ] T-13 — Mover `data/tdrs/` → `data/scraped/tdrs/` [@miguel] [0.2h]
- [ ] T-14 — Mover `data/manual_tdrs/` → `data/scraped/manual_tdrs/` [@miguel] [0.1h]
- [ ] T-15 — Mover `data/tdr_recon/` → `data/scraped/tdr_recon/` [@miguel] [0.1h]
- [ ] T-16 — Eliminar directorios vacíos viejos [@miguel] [0.1h]

## Fase 3: Index y leyenda
- [ ] T-20 — Escribir `data/INDEX.md` [@miguel] [2h]
- [ ] T-21 — Escribir metadata por source en `data/scraped/*/metadata.json` [@miguel] [1h]
- [ ] T-22 — Actualizar `data/README.md` [@miguel] [0.3h]

## Fase 4: Codigo
- [ ] T-30 — Actualizar paths en `tdr_discovery.py` [@miguel] [0.3h]
- [ ] T-31 — Actualizar paths en `run_golden_set.py` [@miguel] [0.3h]
- [ ] T-32 — Actualizar paths en `cli.py` [@miguel] [0.1h]
- [ ] T-33 — Actualizar paths en `test_source_chunks.py` [@miguel] [0.1h]

## Fase 5: Specs
- [ ] T-40 — Archivar `SPEC-0006-source-registry-and-traceability` [@miguel] [0.2h]
- [ ] T-41 — Actualizar `specs/_next.txt` [@miguel] [0.1h]

## Fase 6: Verificacion
- [ ] T-50 — pytest [@miguel] [0.3h]
- [ ] T-51 — ruff check [@miguel] [0.1h]
- [ ] T-52 — pyright [@miguel] [0.2h]
- [ ] T-53 — agenteperry tdr index [@miguel] [0.1h]
