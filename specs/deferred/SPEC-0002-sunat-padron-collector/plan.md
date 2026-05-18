# PLAN — SPEC-0002 SUNAT Padrón collector [LEGACY → REACTIVADO AS SPEC-0008]

> **⚠️ Este plan fue reactivado con ID SPEC-0008.**
> El alcance evolucionó de "collector standalone" a "enrichment no destructivo de source_entities.company".
> Ver documentación actual: `specs/active/SPEC-0008-sunat-padron-enrichment/plan.md`

## Arquitectura

```
sunat.gob.pe/padron_reducido_ruc.zip
        │ HTTPS stream
        ▼
data/raw/sunat/padron_ruc.zip   (cached, sha256 tracked)
        │ zipfile.extract
        ▼
padron_ruc.txt (ISO-8859-1, pipe '|', 14.5M rows)
        │ pd.read_csv chunked (chunksize=50000)
        ▼
For each chunk:
  Map to entity rows
        │
        ▼
PG TRANSACTION (per chunk):
  COPY into staging temp table (asyncpg.copy_records_to_table)
  INSERT ... ON CONFLICT (entity_type, canonical_id) DO UPDATE
    SET metadata = entities.metadata || EXCLUDED.metadata,
        sources  = ARRAY(SELECT DISTINCT unnest(...))
  TRUNCATE staging
        │
        ▼
entities populated with SUNAT metadata
```

## Modelo de datos

Sin cambios al schema. Usa `entities` existente.

### Mapeo TXT → entity

| Columna TXT | Campo entity |
|-------------|--------------|
| `ruc` | `canonical_id` |
| `razon_social` | `display_name` |
| `estado_contribuyente` | `metadata.estado_contribuyente` |
| `condicion_domicilio` | `metadata.condicion_domicilio` |
| `ubigeo` | `metadata.ubigeo` |
| `tipo_via` + `nombre_via` + `numero` + `interior` + ... | `metadata.direccion_completa` (concatenado, lowercased) |
| `tipo_via` | `metadata.tipo_via` |
| `nombre_via` | `metadata.nombre_via` |
| `numero` | `metadata.direccion_numero` |

`metadata.direccion_hash` = `md5(direccion_completa + ubigeo)` para detectar domicilios compartidos.

`entity_type` = `'company'` para todos.
`sources` = `ARRAY['SUNAT_PADRON']`.

## Implementación

### Pseudocódigo `PadronCollector.load()`

```python
async def load(self, df: pd.DataFrame) -> int:
    pool = await get_async_pool()
    total = 0

    # Read in chunks to avoid loading all at once
    for chunk in chunks_of(df, 50_000):
        rows = [_row_to_tuple(r) for r in chunk.itertuples(index=False)]

        async with pool.acquire() as conn:
            async with conn.transaction():
                # Stage into TEMP table
                await conn.execute("""
                    CREATE TEMP TABLE staging_padron (
                        canonical_id VARCHAR(50),
                        display_name TEXT,
                        metadata JSONB
                    ) ON COMMIT DROP;
                """)

                await conn.copy_records_to_table(
                    'staging_padron',
                    records=rows,
                    columns=['canonical_id', 'display_name', 'metadata'],
                )

                # UPSERT into entities
                await conn.execute("""
                    INSERT INTO entities (entity_type, canonical_id, display_name, metadata, sources)
                    SELECT 'company', canonical_id, display_name, metadata, ARRAY['SUNAT_PADRON']
                    FROM staging_padron
                    ON CONFLICT (entity_type, canonical_id) DO UPDATE SET
                        display_name = COALESCE(EXCLUDED.display_name, entities.display_name),
                        metadata = entities.metadata || EXCLUDED.metadata,
                        sources = ARRAY(SELECT DISTINCT unnest(entities.sources || EXCLUDED.sources));
                """)

        total += len(rows)
        self.logger.info("padron.chunk_loaded", chunk_size=len(rows), total=total)

    return total
```

### `parse()` cambiado a chunked iterator

Cambiar `parse()` de devolver DataFrame entero → generator de DataFrames de 50k filas.

```python
def parse(self, raw_path: Path) -> Iterator[pd.DataFrame]:
    with zipfile.ZipFile(raw_path) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        with zf.open(txt_name) as f:
            for chunk in pd.read_csv(
                f, sep='|', encoding='latin1', header=None,
                names=PADRON_COLUMNS, dtype=str,
                on_bad_lines='skip', chunksize=50_000,
            ):
                yield chunk
```

## Performance

| Métrica | Target |
|---------|--------|
| Download 200MB | < 60s |
| Unzip + parse en chunks | streaming, sin pico |
| Load total 14.5M rows | < 15 min |
| RAM peak | < 2GB |

## Tests

- `test_parse_chunk()` con fixture txt de 100 filas
- `test_row_to_entity()` con fila típica
- `test_handle_encoding()` con bytes ISO-8859-1 reales con `ñ`, `Ñ`, tildes
- `test_idempotency()` — load 2x del mismo chunk → counts iguales

Fixture: `tests/fixtures/sunat_padron_sample.txt` con 50 filas reales (anonimizadas si necesario, aunque es data pública).

## Rollout

- Branch: `feat/SPEC-0002-sunat-padron-collector`
- Rollback: `DELETE FROM entities WHERE 'SUNAT_PADRON' = ANY(sources) AND NOT 'OCDS' = ANY(sources);` (preserva entities cruzadas con OCDS)
