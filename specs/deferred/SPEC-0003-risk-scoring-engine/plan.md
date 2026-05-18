# PLAN — SPEC-0003 Risk scoring engine

## Arquitectura

```
                    contracts + entities (DB)
                              │
                              ▼
              ┌───────────────────────────────┐
              │  enrich_contract_view()       │
              │  Cross-join contract+supplier │
              │  + ubigeo, estado_sunat,      │
              │  + percentil_monto (mv)       │
              └─────────────┬─────────────────┘
                            │ async iter
                            ▼
              ┌──────────────────────────────┐
              │  evaluate_indicators(row)    │
              │  → list[(flag_id, score)]    │
              └─────────────┬────────────────┘
                            │
                            ▼
              ┌──────────────────────────────┐
              │  INSERT risk_flags batched   │
              └─────────────┬────────────────┘
                            │
                            ▼
              ┌──────────────────────────────┐
              │  aggregate_score(flags)      │
              │  → risk_score + nivel_riesgo │
              │  UPDATE contracts            │
              └─────────────┬────────────────┘
                            │
                            ▼
              ┌──────────────────────────────┐
              │  case_creator (--min-score)  │
              │  Promote → risk_cases        │
              └──────────────────────────────┘
```

## Componentes

| Path | Cambio |
|------|--------|
| `apps/scrapers/src/contralatam/scoring/indicators.py` | completar 7 indicadores, ya hay stub |
| `apps/scrapers/src/contralatam/scoring/scorer.py` | NUEVO — orquesta evaluate + persist |
| `apps/scrapers/src/contralatam/scoring/case_creator.py` | NUEVO — promueve scores a casos |
| `apps/scrapers/src/contralatam/scoring/enricher.py` | NUEVO — query SQL que pivotea contract+supplier+metadata |
| `packages/db/migrations/0010_p95_view.sql` | NUEVA — `mv_monto_p95_por_method` |
| `packages/db/migrations/0011_contract_score_columns.sql` | NUEVA — agregar `risk_score`, `nivel_riesgo` a `contracts` |
| `apps/scrapers/src/contralatam/cli.py` | wire up `score` + `create-cases` |
| `apps/scrapers/tests/test_indicators.py` | extender |
| `apps/scrapers/tests/test_scorer.py` | NUEVO |

## SQL nuevo

### `0010_p95_view.sql`

```sql
CREATE MATERIALIZED VIEW mv_monto_p95_por_method AS
SELECT
  tender_method,
  source_year,
  percentile_cont(0.95) WITHIN GROUP (ORDER BY monto_contratado) AS p95_monto,
  count(*) AS sample_size
FROM contracts
WHERE monto_contratado IS NOT NULL AND monto_contratado > 0
GROUP BY tender_method, source_year;

CREATE INDEX ON mv_monto_p95_por_method(tender_method, source_year);
```

### `0011_contract_score_columns.sql`

```sql
ALTER TABLE contracts
  ADD COLUMN IF NOT EXISTS risk_score DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS nivel_riesgo VARCHAR(20),
  ADD COLUMN IF NOT EXISTS scored_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_contracts_score ON contracts(risk_score DESC) WHERE risk_score > 0.3;
```

## Query de enriquecimiento

```sql
SELECT
  c.ocid,
  c.tender_method,
  c.num_postores,
  c.monto_convocado,
  c.monto_contratado,
  c.fecha_convocatoria,
  c.fecha_cierre_conv,
  EXTRACT(EPOCH FROM (c.fecha_cierre_conv - c.fecha_convocatoria))/86400 AS dias_plazo_conv,
  CASE WHEN c.monto_convocado > 0
       THEN ABS(c.monto_contratado - c.monto_convocado) / c.monto_convocado
       ELSE NULL END AS delta_monto_pct,
  c.ubigeo,
  c.region,
  -- supplier info via relationships
  s.id AS supplier_id,
  s.metadata->>'condicion_domicilio' AS supplier_condicion_domicilio,
  s.metadata->>'estado_contribuyente' AS supplier_estado_contribuyente,
  -- percentil
  CASE WHEN p.p95_monto IS NOT NULL AND c.monto_contratado > 0
       THEN c.monto_contratado / p.p95_monto
       ELSE NULL END AS percentil_monto_ratio
FROM contracts c
LEFT JOIN relationships r ON r.source_id = (
  SELECT e.id FROM entities e WHERE e.canonical_id IS NOT NULL
  AND r.target_id IS NOT NULL AND r.rel_type = 'GANO_CONTRATO'
  LIMIT 1
)
LEFT JOIN entities s ON s.id = r.source_id
LEFT JOIN mv_monto_p95_por_method p
  ON p.tender_method = c.tender_method AND p.source_year = c.source_year
WHERE c.source_year = ANY($1);
```

(El JOIN exact a supplier vía relationships requiere refinamiento — quizá vista helper.)

## Algoritmo

```python
async def score_year(year: int) -> ScoringStats:
    enricher = ContractEnricher()
    flags_to_insert: list[FlagRow] = []
    score_updates: list[tuple[str, float, str]] = []

    async for row in enricher.iter_contracts(year=year):
        flags = evaluate_indicators(row)
        score = aggregate_score(flags)
        level = nivel_riesgo(score)

        for flag_id, score_contrib in flags:
            flags_to_insert.append(FlagRow(
                flag_type=flag_id,
                score_contrib=score_contrib,
                contract_ocid=row['ocid'],
                entity_a=row['supplier_id'],
                evidence=_extract_evidence(row, flag_id),
            ))

        score_updates.append((row['ocid'], score, level))

        if len(flags_to_insert) >= 500:
            await _flush_flags(flags_to_insert)
            await _flush_scores(score_updates)
            flags_to_insert.clear()
            score_updates.clear()

    await _flush_flags(flags_to_insert)
    await _flush_scores(score_updates)
```

## Case creator

```python
async def create_cases(min_score: float = 0.5):
    """Promote contracts above threshold to risk_cases."""
    sql = """
        INSERT INTO risk_cases (slug, score_total, nivel_riesgo, ubigeo_caso, region_caso, district_caso, flag_ids, entity_ids)
        SELECT
          generate_case_slug(c.ocid, c.ubigeo, s.display_name),
          c.risk_score,
          c.nivel_riesgo,
          c.ubigeo,
          c.region,
          ubigeo_to_district(c.ubigeo),
          ARRAY(SELECT id FROM risk_flags WHERE contract_ocid = c.ocid),
          ARRAY[s.id, b.id]  -- supplier + buyer
        FROM contracts c
        LEFT JOIN ...
        WHERE c.risk_score >= $1
          AND NOT EXISTS (SELECT 1 FROM risk_cases rc WHERE c.ocid = ANY(...))
    """
```

`generate_case_slug` y `ubigeo_to_district` definidos en migración `0012_helpers.sql`.

## Performance

| Métrica | Target |
|---------|--------|
| Scoring 500k contratos | < 5 min |
| Refresh mv P95 | < 30s |
| Crear casos (filter score >= 0.5) | < 1 min |
| RAM peak | < 1GB |

## Tests

- `test_unico_postor_fires()` ✅ ya existe
- `test_plazo_corto()` 
- `test_delta_monto_above_threshold()`
- `test_monto_atipico_p95()`
- `test_no_habido_supplier()`
- `test_empresa_nueva()` con `fecha_inicio_actividades`
- `test_aggregate_score_with_bonus()` — 5 flags → bonus 1.15x
- `test_nivel_riesgo_thresholds()` ✅ ya existe
- `test_case_creator_idempotent()` — 2x runs no duplica

Coverage target scoring/: 90%.
