# PLAN — SPEC-0001 OCDS collector

## Arquitectura

```
data.open-contracting.org
        │ HTTPS stream
        ▼
data/raw/ocds/{year}.jsonl.gz    (cached, sha256 tracked)
        │ gzip + ijson stream
        ▼
flatten_release(release) → dict   (one row per ocid)
        │ batched 500
        ▼
PG TRANSACTION:
  UPSERT contracts          (PK ocid)
  UPSERT entities buyers    (PK entity_type+canonical_id)
  UPSERT entities suppliers (PK entity_type+canonical_id)
  INSERT relationships      (skip-dup via WHERE NOT EXISTS)
        │
        ▼
contracts + entities + relationships ready for SPEC-0003 scorer
```

## Componentes a tocar

| Path | Cambio | Owner |
|------|--------|-------|
| `apps/scrapers/src/contralatam/collectors/ocds/ocds_collector.py` | implementar `load()` + completar `parse()` | @TBD-2 |
| `apps/scrapers/src/contralatam/db/queries.py` | nuevo archivo con SQL constants `UPSERT_CONTRACT`, `UPSERT_ENTITY`, `INSERT_RELATIONSHIP` | @TBD-2 |
| `apps/scrapers/src/contralatam/parsers/ocds_flattener.py` | extraer `_flatten` de `ocds_collector.py` a módulo dedicado + tests | @TBD-2 |
| `apps/scrapers/tests/test_ocds_collector.py` | nuevos tests con VCR.py fixture | @TBD-2 |
| `apps/scrapers/tests/fixtures/ocds_sample.jsonl.gz` | 10 releases reales de muestra | @TBD-2 |

## Modelo de datos

Ya existe en migraciones 0002 (entities, relationships) y 0003 (contracts). Sin cambios.

### SQL crítico

```sql
-- packages/db/queries/upsert_contract.sql
INSERT INTO contracts (
  ocid, buyer_id, tender_method, tender_method_details, objeto,
  monto_convocado, monto_adjudicado, monto_contratado,
  num_postores, fecha_convocatoria, fecha_cierre_conv,
  region, ubigeo, source_year, raw_ocds, scraped_at
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW())
ON CONFLICT (ocid) DO UPDATE SET
  monto_contratado = EXCLUDED.monto_contratado,
  raw_ocds         = EXCLUDED.raw_ocds,
  scraped_at       = NOW();
```

```sql
-- packages/db/queries/upsert_entity.sql
INSERT INTO entities (entity_type, canonical_id, display_name, metadata, sources)
VALUES ($1, $2, $3, $4, ARRAY[$5])
ON CONFLICT (entity_type, canonical_id) DO UPDATE SET
  metadata = entities.metadata || EXCLUDED.metadata,
  sources  = ARRAY(SELECT DISTINCT unnest(entities.sources || EXCLUDED.sources))
RETURNING id;
```

## Flujo

1. `OcdsCollector.run(year=Y)` se invoca desde CLI por cada year.
2. `download(year)`: stream con `httpx.AsyncClient`, escribe a `data/raw/ocds/{year}.jsonl.gz`. Skip si existe + sha256 match.
3. `parse(path)`: `gzip.open` + `ijson.items(..., 'item', multiple_values=True)` → yields release dicts.
4. `flatten(release)`: convierte release OCDS → record dict con campos planos para `contracts` + arrays de companies/relationships.
5. `load(records)`: 
   - Agrupa en batches de 500.
   - Abre transacción.
   - `executemany(UPSERT_ENTITY_SQL, buyer_rows)` → recoge buyer_ids.
   - `executemany(UPSERT_ENTITY_SQL, supplier_rows)` → recoge supplier_ids.
   - `executemany(UPSERT_CONTRACT_SQL, contract_rows)` con buyer_id resuelto.
   - Para cada (supplier, contract) tupla: `INSERT INTO relationships ... WHERE NOT EXISTS (...)` con `rel_type='GANO_CONTRATO'`.
   - Commit.
6. Loggea `record_count`, `entities_upserted`, `relationships_created`, `duration_ms`.

## Decisiones técnicas

### asyncpg vs SQLAlchemy

asyncpg directo con `executemany`. SQLAlchemy ORM agrega 5–10x overhead en bulk inserts. SQL crudo en `db/queries.py` está bien para este volumen.

### Batch size 500

Sweet spot empírico: <100 desperdicia round-trips, >2000 hace timeouts en transacciones largas. 500 = ~50 batches/segundo en pgvector pg16.

### Idempotencia de relationships

No tenemos UNIQUE constraint en `(source_id, target_id, rel_type, valid_from)`. En F1 usamos `INSERT ... WHERE NOT EXISTS (SELECT 1 FROM relationships r WHERE r.source_id=$1 AND r.target_id=$2 AND r.rel_type=$3 AND r.valid_from = $4)`. En F2+ evaluar UNIQUE constraint.

### Skip relationships si missing buyer/supplier

Si OCDS release no tiene `buyer.identifier.id`, skip contract entirely + log warning. Si supplier sin RUC, skip ese supplier solo (otros del mismo award sí cargan).

## Performance

| Métrica | Target |
|---------|--------|
| Download 2024 (147MB) | < 90s a 2MB/s |
| Parse + flatten 2024 | < 5 min |
| Load 2024 (~150k releases) | < 8 min |
| RAM peak | < 1GB |
| Total 2024+2025+2026 | < 30 min |

## Seguridad

- No procesamos datos personales (OCDS solo expone empresas + entidades públicas).
- Logs no incluyen RUCs completos a nivel DEBUG (privacidad básica aunque sea público).
- `raw_ocds` JSONB guarda payload original — útil para auditoría, indexed con jsonb_path_ops.

## Tests

### Unit
- `test_flatten_release()` — fixture con 1 release real → asserts en campos extraídos
- `test_flatten_missing_award()` — release sin award → `monto_adjudicado IS NULL`
- `test_flatten_invalid_ruc()` — RUC con check digit malo → loggeado y skipped

### Integration (con Postgres test)
- `test_collector_e2e()` — VCR fixture con 10 releases → 10 contracts + N entities en DB
- `test_idempotency()` — correr 2x → counts iguales

### Coverage target
- `parsers/ocds_flattener.py`: 90%
- `collectors/ocds/`: 75%

## Rollout

- Branch: `feat/SPEC-0001-ocds-collector`
- No feature flag — es bootstrap data
- Rollback: `TRUNCATE contracts; DELETE FROM entities WHERE 'OCDS' = ANY(sources);` (en último caso)
