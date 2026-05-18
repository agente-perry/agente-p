# Production Data Guard Plan — AgentePerry

**Fecha:** 2026-05-17  
**Actividad:** 8B-0 — Anti-Fixture Plan  
**Alcance:** plan de control; no borra datos ni crea tablas

## Objetivo

Evitar que archivos de tests, fixtures, samples o rutas temporales sean cargados como datos reales en cualquier pipeline de produccion.

El guard debe fallar antes de escribir en DB.

## Principios

1. El origen de cada corrida es parte de la data.
2. Ningun path bajo `tests/`, `fixtures/`, `sample`, `/tmp/`, `_test_` o `dummy` entra a produccion sin override explicito.
3. Todo loader que escribe en DB debe producir audit JSON.
4. Conteos bajos no son warnings: bloquean la corrida si rompen umbrales.
5. `--allow-fixture` solo existe para tests y smoke runs locales.

## API propuesta

```python
FORBIDDEN_PATH_PATTERNS = (
    "tests/",
    "fixtures/",
    "sample",
    "/tmp/",
    "_test_",
    "dummy",
)


def assert_production_data(raw_path: str | Path | None, *, allow_fixture: bool = False) -> None:
    """Reject test/fixture/sample/tmp paths before any production write."""
    if allow_fixture:
        return
    if raw_path is None:
        raise ValueError("PRODUCTION GUARD: raw_path is required for production loads")
    normalized = str(raw_path).lower().replace("\\", "/")
    for pattern in FORBIDDEN_PATH_PATTERNS:
        if pattern in normalized:
            raise ValueError(
                "PRODUCTION GUARD: refused to load non-production data path "
                f"{raw_path!s}; matched pattern {pattern!r}. "
                "Use --allow-fixture only in tests."
            )
```

## Donde aplicarlo

| Area | Funcion/comando | Regla |
|------|------------------|-------|
| Source records | `upsert_source_records()` | Validar JSONL path y cada `raw_path` |
| Graph entities | `upsert_entities()` | Validar graph JSON path y metadata raw_path |
| SUNAT enrichment | `enrich_companies_from_sunat()` | Validar `records_jsonl` y source raw paths |
| Collectors con `input_path` | `sources pipeline`, `sources collect` | Validar antes de collect cuando escribe a DB |
| TDR manual loader | `tdr load-manual --sync` | Validar manifest path y PDFs locales |
| Phase1 scripts | `phase1_*` | Validar input/output source manifests antes de persistir |

## CLI policy

Agregar flag uniforme:

```text
--allow-fixture
```

Reglas:

- Default: `False`.
- Solo permitido en tests, smoke local y fixtures controlados.
- Si `--allow-fixture` esta activo, el audit debe registrar `allow_fixture: true`.
- CI debe tener tests que comprueben que fixtures son rechazados sin ese flag.

## Audit obligatorio por corrida

Cada corrida que cargue datos debe generar un `audit.json` con:

```json
{
  "run_at": "ISO-8601",
  "source_code": "sunat_padron",
  "input_path": "/abs/path/file.jsonl",
  "input_sha256": "...",
  "allow_fixture": false,
  "records_seen": 0,
  "records_written": 0,
  "expected_min_records": 100,
  "coverage": {
    "with_ruc": 0,
    "with_amount": 0,
    "with_source_url": 0
  },
  "blocked": false,
  "block_reason": null
}
```

## Umbrales minimos

| Fuente | Umbral minimo inicial | Accion si falla |
|--------|-----------------------|-----------------|
| OCDS real | `records_seen >= 1000` para corrida completa; smoke debe declarar `--limit` | Bloquear si no es smoke |
| SUNAT real | `records_seen >= 100000` para padron completo; enrichment subset debe declarar expected RUC count | Bloquear |
| TDR PDF batch | `total_pdfs > 0` y `pdfs_with_ocid_path / total_pdfs >= 0.8` para carga DB | Bloquear carga DB, permitir audit |
| TDR text batch | `pages_total > 0`, `chunks_created > 0` para cada PDF textual | Marcar documento como failed/no_text |
| Source URL coverage | `with_source_url >= 95%` en OCDS/document manifests | Bloquear corrida completa |

## Bloqueo por conteo esperado vs real

Regla general:

```text
if expected_count and real_count < expected_count * 0.95:
    block_pipeline()
```

Excepciones:

- Smoke runs deben declarar `--limit` y `--smoke`.
- Tests deben declarar `--allow-fixture`.
- Corridas exploratorias pueden escribir solo a disco, no a DB.

## Plan de implementacion recomendado

1. Crear helper unico `agenteperry.data_guard` o `agenteperry.sync.guard`.
2. Reemplazar guards ad-hoc por el helper comun.
3. Agregar `--allow-fixture` a comandos que aceptan paths locales.
4. Agregar tests unitarios:
   - rechaza `tests/fixtures/sunat_padron_sample.txt`;
   - rechaza `/tmp/foo.jsonl`;
   - permite con `allow_fixture=True`;
   - exige `raw_path` en produccion.
5. Agregar audit JSON obligatorio en source pipeline y SUNAT enrichment.
6. Ejecutar limpieza SUNAT fixture solo despues de exportar backup de los 25 RUC afectados.

## Estado actual observado

La auditoria encontro:

- 25 `source_records` con `raw_path = tests/fixtures/sunat_padron_sample.txt`.
- 25 empresas con metadata SUNAT.
- 30,600 empresas totales.
- Cobertura SUNAT real: 0.0817%.
- Un guard preliminar existe en `sync/loader.py`, pero debe ser estandarizado, probado y propagado a todos los entrypoints.

## Criterio de salida

El proyecto solo puede declarar una fuente como produccion cuando:

1. `audit.json` existe.
2. `input_path` no es sospechoso.
3. `input_sha256` esta registrado.
4. `records_seen` supera el umbral esperado.
5. Cobertura clave supera umbral minimo.
6. No hay `allow_fixture: true`.
7. Tests, ruff y pyright pasan.
