# TASKS — SPEC-0001 OCDS collector

## Pre-implementación

- [ ] T-01 — Spec aprobado y mergeado a main [@MiguelAAR10] [0.5h]
- [ ] T-02 — Branch `feat/SPEC-0001-ocds-collector` desde main [@TBD-2] [0.1h]

## Implementación

- [ ] T-03 — Crear `apps/scrapers/src/contralatam/db/queries.py` con constants SQL (UPSERT_CONTRACT, UPSERT_ENTITY, INSERT_RELATIONSHIP_IF_NEW) [@TBD-2] [1h]
- [ ] T-04 — Extraer `_flatten` a `parsers/ocds_flattener.py` con función pura `flatten_release(release: dict) -> ContractRow` [@TBD-2] [2h]
- [ ] T-05 — Implementar `OcdsCollector.load()` con batch UPSERT vía asyncpg (batch 500) [@TBD-2] [3h]
- [ ] T-06 — Manejar edge cases: release sin buyer / award / supplier; RUC inválido [@TBD-2] [1.5h]
- [ ] T-07 — Validación RUC con `pe-sunat` antes de UPSERT — skip + log si inválido [@TBD-2] [0.5h]
- [ ] T-08 — Logging estructurado: `record_count`, `entities_upserted`, `relationships_created`, `duration_ms` por batch [@TBD-2] [0.5h]
- [ ] T-09 — Skip download si sha256 ya match (resume) [@TBD-2] [0.5h]

## Tests

- [ ] T-10 — Fixture `tests/fixtures/ocds_sample.jsonl.gz` con 10 releases reales (descargar + sample) [@TBD-2] [0.5h]
- [ ] T-11 — `test_flatten_release()` con asserts de campos clave [@TBD-2] [1h]
- [ ] T-12 — `test_flatten_missing_award()` + `test_flatten_invalid_ruc()` [@TBD-2] [1h]
- [ ] T-13 — `test_collector_e2e()` contra Postgres test (CI) [@TBD-2] [2h]
- [ ] T-14 — `test_idempotency()` — 2x runs = mismos counts [@TBD-2] [0.5h]

## Documentación

- [ ] T-20 — Actualizar `apps/scrapers/README.md` con comando + ejemplo de output [@TBD-2] [0.3h]
- [ ] T-21 — Actualizar `docs/SCRAPING.md § 1` si algo del diseño cambió [@TBD-2] [0.3h]

## Cierre

- [ ] T-30 — Self-review diff completo (`git diff main`) [@TBD-2] [0.5h]
- [ ] T-31 — Run end-to-end local: 3 años cargan en <30min [@TBD-2] [0.5h]
- [ ] T-32 — PR `feat: implementar OCDS collector con UPSERT batched (SPEC-0001)` [@TBD-2] [0.2h]
- [ ] T-33 — Aprobación @MiguelAAR10 [@MiguelAAR10]
- [ ] T-34 — Squash + merge [@TBD-2]
- [ ] T-35 — Mover spec a `specs/completed/SPEC-0001-ocds-collector/` [@TBD-2] [0.2h]
- [ ] T-36 — Tag `SPEC-0001-done` [@TBD-2] [0.1h]

---

## Estimación total

| Sección | Horas |
|---------|-------|
| Implementación | 9.0 |
| Tests | 5.0 |
| Documentación | 0.6 |
| Cierre | 1.5 |
| **Total** | **~16h** |

Asignable a 1 dev en 2–3 días de trabajo dedicado.

## Asignaciones

| Owner | Tasks | Total |
|-------|-------|-------|
| @TBD-2 (Data Engineer) | T-02 a T-21, T-30 a T-36 | ~16h |
| @MiguelAAR10 (Reviewer) | T-01, T-33 | ~1h |
