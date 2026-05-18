# TASKS — SPEC-0002 SUNAT Padrón [LEGACY → REACTIVADO AS SPEC-0008]

> **⚠️ Este spec fue reactivado con ID SPEC-0008.**  
> Ver documentación actual: `specs/active/SPEC-0008-sunat-padron-enrichment/tasks.md`

## Pre-implementación

- [ ] T-01 — Spec aprobado y mergeado a main [@MiguelAAR10] [0.5h]
- [ ] T-02 — Branch `feat/SPEC-0002-sunat-padron-collector` desde main [@TBD-2] [0.1h]

## Implementación

- [ ] T-03 — Convertir `parse()` a generator de DataFrames de 50k filas (chunked) [@TBD-2] [1h]
- [ ] T-04 — Helper `_row_to_entity_tuple(row)` → `(canonical_id, display_name, metadata_jsonb)` [@TBD-2] [1.5h]
- [ ] T-05 — Computar `metadata.direccion_hash = md5(...)` para detección de domicilio compartido en F2 [@TBD-2] [0.5h]
- [ ] T-06 — Implementar `load()` con asyncpg `copy_records_to_table` + UPSERT desde staging [@TBD-2] [3h]
- [ ] T-07 — Manejar encoding ISO-8859-1 correctamente (tildes, ñ) [@TBD-2] [0.5h]
- [ ] T-08 — Logging por chunk: `chunk_size`, `total_loaded`, `duration_ms` [@TBD-2] [0.5h]
- [ ] T-09 — Skip download si sha256 unchanged [@TBD-2] [0.5h]

## Tests

- [ ] T-10 — Fixture `tests/fixtures/sunat_padron_sample.txt` con 50 filas reales [@TBD-2] [0.5h]
- [ ] T-11 — `test_parse_chunk()` con 50 filas → yields DataFrames correctos [@TBD-2] [0.5h]
- [ ] T-12 — `test_row_to_entity_tuple()` con fila típica + casos edge (campos vacíos) [@TBD-2] [1h]
- [ ] T-13 — `test_encoding_iso_8859_1()` — `'COMPAÑIA SEÑOR DEL VALLE'` decodifica bien [@TBD-2] [0.3h]
- [ ] T-14 — `test_load_idempotent()` contra Postgres test [@TBD-2] [1.5h]

## Documentación

- [ ] T-20 — `apps/scrapers/README.md` — agregar comando `bootstrap-sunat` con output esperado [@TBD-2] [0.3h]

## Cierre

- [ ] T-30 — Self-review diff completo [@TBD-2] [0.5h]
- [ ] T-31 — Run local end-to-end → 14.5M rows cargados [@TBD-2] [0.5h]
- [ ] T-32 — PR `feat: SUNAT padrón collector con COPY async + UPSERT (SPEC-0002)` [@TBD-2] [0.2h]
- [ ] T-33 — Aprobación @MiguelAAR10 [@MiguelAAR10]
- [ ] T-34 — Squash + merge [@TBD-2]
- [ ] T-35 — Mover spec a `specs/completed/SPEC-0002-sunat-padron-collector/` [@TBD-2] [0.2h]

---

## Estimación

| Sección | Horas |
|---------|-------|
| Implementación | 7.5 |
| Tests | 3.8 |
| Documentación | 0.3 |
| Cierre | 1.4 |
| **Total** | **~13h** |

Asignable a 1 dev en 2 días.
