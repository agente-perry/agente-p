# TASKS — SPEC-0003 Risk scoring engine

## Pre-implementación

- [ ] T-01 — Spec aprobado y mergeado [@TBD-2] [0.5h]
- [ ] T-02 — Branch `feat/SPEC-0003-risk-scoring-engine` [@MiguelAAR10] [0.1h]
- [ ] T-03 — SPEC-0001 + SPEC-0002 ya completados (datos cargados) [PRE-REQ]

## DB

- [ ] T-10 — Migración `0010_p95_view.sql` con mv [@MiguelAAR10] [0.5h]
- [ ] T-11 — Migración `0011_contract_score_columns.sql` [@MiguelAAR10] [0.3h]
- [ ] T-12 — Migración `0012_helpers.sql` con `generate_case_slug`, `ubigeo_to_district` [@MiguelAAR10] [1h]
- [ ] T-13 — Aplicar migraciones local + smoke test [@MiguelAAR10] [0.3h]

## Indicadores

- [ ] T-20 — Completar `indicators.py`: `_plazo_corto` con business days helper [@MiguelAAR10] [1h]
- [ ] T-21 — `_delta_monto` ya existe — agregar test edge: monto_convocado = 0 [@MiguelAAR10] [0.3h]
- [ ] T-22 — `_monto_atipico` usar `percentil_monto_ratio > 1.0` (= por encima de P95) [@MiguelAAR10] [0.5h]
- [ ] T-23 — `_no_habido` ya existe — verificar source field path correcto [@MiguelAAR10] [0.2h]
- [ ] T-24 — `_empresa_nueva` — calcular `months_between(fecha_inicio_act, fecha_convocatoria) < 12`. Manejar `fecha_inicio_act IS NULL` graceful [@MiguelAAR10] [1h]

## Enricher

- [ ] T-30 — `enricher.py` con `ContractEnricher.iter_contracts(year)` async iterator [@MiguelAAR10] [2h]
- [ ] T-31 — Resolver join contract → supplier vía relationships (case multi-suppliers) [@MiguelAAR10] [1.5h]

## Scorer

- [ ] T-40 — `scorer.py` orquestador: enrich → evaluate → batch insert flags + update score [@MiguelAAR10] [2.5h]
- [ ] T-41 — Función `_extract_evidence(row, flag_id) -> dict` para `risk_flags.evidence` JSONB [@MiguelAAR10] [1h]
- [ ] T-42 — Logging por batch: `contracts_scored`, `flags_inserted`, `duration_ms` [@MiguelAAR10] [0.3h]

## Case creator

- [ ] T-50 — `case_creator.py` con SQL INSERT ON CONFLICT (slug) DO NOTHING [@MiguelAAR10] [1.5h]
- [ ] T-51 — Slug generator: `<ubigeo>-<supplier-slug>-<ocid-short>` — lowercase, ASCII only [@MiguelAAR10] [0.5h]

## CLI

- [ ] T-60 — `cli.py score` invoca `scorer.score_years(years)` [@MiguelAAR10] [0.3h]
- [ ] T-61 — `cli.py create-cases` invoca `case_creator.run(min_score)` [@MiguelAAR10] [0.3h]
- [ ] T-62 — `cli.py top-cases` query real desde DB con Rich table [@MiguelAAR10] [0.5h]

## Tests

- [ ] T-70 — Tests por indicador: 7 tests, uno por flag [@MiguelAAR10] [2h]
- [ ] T-71 — `test_aggregate_score_with_bonus()` casos: 3 flags, 5 flags, score > 1.0 [@MiguelAAR10] [0.5h]
- [ ] T-72 — `test_case_creator_idempotent()` con Postgres test [@MiguelAAR10] [1h]
- [ ] T-73 — `test_score_distribution_smoke()` — load fixture + score → verifica ratios razonables [@MiguelAAR10] [1.5h]

## Documentación

- [ ] T-80 — `docs/METHODOLOGY.md` — marcar 7 indicadores como ✅ implementados [@MiguelAAR10] [0.3h]
- [ ] T-81 — `apps/scrapers/README.md` — agregar ejemplo `score` + `top-cases` output [@MiguelAAR10] [0.5h]
- [ ] T-82 — ADR opcional: por qué Python over SQL puro (`docs/adr/0001-scoring-language.md`) [@MiguelAAR10] [0.5h]

## Cierre

- [ ] T-90 — Self-review [@MiguelAAR10] [0.5h]
- [ ] T-91 — Run e2e local con datos de SPEC-0001 + SPEC-0002 [@MiguelAAR10] [1h]
- [ ] T-92 — PR `feat: risk scoring engine con 7 indicadores FUNES (SPEC-0003)` [@MiguelAAR10] [0.2h]
- [ ] T-93 — Aprobación @TBD-2 [@TBD-2]
- [ ] T-94 — Squash + merge [@MiguelAAR10]
- [ ] T-95 — Mover spec a `specs/completed/` [@MiguelAAR10] [0.2h]

---

## Estimación

| Sección | Horas |
|---------|-------|
| DB | 2.1 |
| Indicadores | 3.0 |
| Enricher | 3.5 |
| Scorer | 3.8 |
| Case creator | 2.0 |
| CLI | 1.1 |
| Tests | 5.0 |
| Docs | 1.3 |
| Cierre | 2.0 |
| **Total** | **~24h** |

3 días de trabajo dedicado.
