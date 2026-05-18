# Data Reality Audit — AgentePerry

**Fecha:** 2026-05-17  
**Actividad:** 8B-0 — Data Reality Audit + Anti-Fixture Plan  
**Modo:** read-only; no OCR, no scraping nuevo, no tablas nuevas, no borrado de datos

## Resumen ejecutivo

La auditoria confirma que la base operacional tiene cobertura fuerte de OCDS, cobertura SUNAT casi nula y cobertura TDR nula en DB.

| Area | Resultado verificado | Estado |
|------|----------------------|--------|
| OCDS contratos | 55,457 `source_records` tipo `contract` | Real y utilizable |
| OCDS procedimientos | 16,942 `source_records` tipo `procedure` | Real y utilizable |
| Empresas OCDS | 30,600 `source_entities` tipo `company` | Real desde OCDS/grafo |
| Entidades publicas | 2,709 `source_entities` tipo `public_entity` | Real desde OCDS/grafo |
| Relaciones compra/ganador | 46,069 `COMPRO_A` y 46,069 `GANO_CONTRATO` | Real y utilizable |
| SUNAT enrichment | 25 de 30,600 empresas | 0.0817%; no escala |
| TDR documents en DB | 0 | No hay pipeline TDR cargado en DB |
| TDR chunks en DB | 0 | Sin texto TDR persistido |
| TDR flags en DB | 0 | Sin flags TDR persistidos |
| PDFs en disco | 18 PDFs, 204 MB reportados por script Python; `du` reporta `data/` en 2.6 GB | Piloto/local, no DB |
| PDFs con OCID en path | 6 de 18 | Parcialmente trazables |

## Evidencia ejecutada

Scripts creados y ejecutados en modo read-only:

- `scripts/audit_data_reality.py`
- `scripts/audit_pdfs_disk.sh`
- `scripts/audit_fixture_origin.sh`

Comando DB usado para la auditoria local:

```bash
cd apps/scrapers
DATABASE_URL="postgresql://contralatam:dev_password@localhost:5432/contralatam" \
  uv run python ../../scripts/audit_data_reality.py
```

## Que existe realmente

### OCDS / contratos

Existe una base real y suficiente para continuar con analisis contractual:

- `source_records.contract`: 55,457
- `source_records.procedure`: 16,942
- `source_entities.company`: 30,600
- `source_entities.public_entity`: 2,709
- `source_relationships.COMPRO_A`: 46,069
- `source_relationships.GANO_CONTRATO`: 46,069

Esto habilita trabajo sobre contratos, entidades compradoras, suppliers y relaciones comprador-ganador.

### SUNAT

La cobertura real de enrichment SUNAT es:

- Empresas totales: 30,600
- Empresas con `metadata->>'sunat_razon_social'`: 25
- Cobertura: 0.0817%

El audit detecta tambien:

- `source_records` tipo `company`: 25
- `source_records.raw_path`: `tests/fixtures/sunat_padron_sample.txt`

Esto indica que los 25 registros SUNAT cargados provienen de fixture. En `source_entities`, los 25 enrichments no conservan `metadata.raw_path`, por lo que la trazabilidad del enrichment quedo incompleta.

### TDRs

La DB no tiene TDRs cargados:

- `tdr_documents`: 0
- `tdr_chunks`: 0
- `tdr_flags`: 0
- TDRs con `external_id`/OCID que matcheen `source_records`: 0

En disco si existen PDFs locales:

- Total PDFs: 18
- PDFs con OCID identificable en path: 6
- PDFs sin OCID identificable en path: 12
- Path sospechoso: `data/scraped/manual_tdrs/dummy.pdf`

La conclusion es directa: hay PDFs piloto/locales, pero no existe todavia una carga DB confiable TDR -> pages -> chunks -> flags.

## Que fue verificado

- Conteos reales en DB por `record_type` y `entity_type`.
- Cobertura SUNAT sobre empresas en `source_entities`.
- Origen `raw_path` de registros sospechosos en `source_records`.
- Conteo de tablas TDR core.
- Vinculo de TDRs contra OCID/source_records.
- Inventario de PDFs en disco.
- Paths sospechosos en disco y referencias a fixtures en codigo.

## Que no fue verificado

- No se verifico OCR ni calidad de texto extraido.
- No se verifico MiniMax ni ningun proveedor de OCR.
- No se hizo scraping nuevo contra SEACE.
- No se ejecuto batch masivo.
- No se validaron semanticamente los 18 PDFs locales.
- No se limpio ningun registro de fixture.
- No se creo `tdr_contract_mapping` ni tablas nuevas.

## Fixture risk

Hallazgo confirmado por patron:

```text
25 source_records desde tests/fixtures/sunat_padron_sample.txt
25 empresas con metadata SUNAT
```

Interpretacion: la cantidad de registros fixture SUNAT y la cantidad de empresas enriquecidas con SUNAT coinciden. Es altamente probable que el enrichment SUNAT existente provenga del fixture. Como `source_entities.metadata.raw_path` esta en NULL para los 30,600 registros, se debe hacer limpieza controlada con query por RUC antes de borrar o modificar datos.

No borrar todavia. Primero guardar un reporte con los RUC afectados y confirmar que esos 25 enrichments corresponden exactamente a los 25 `source_records.company` del fixture.

## Flags habilitadas vs bloqueadas

| Grupo | Estado actual | Motivo |
|-------|---------------|--------|
| Flags dependientes de SUNAT real (F1-F4) | Bloqueadas | Solo 25 empresas con enrichment SUNAT; fuente fixture |
| Flags sobre OCDS/contratos (F5-F12) | Habilitables | 55,457 contratos y relaciones comprador-ganador reales |
| Flags TDR documentales | Codigo disponible, datos DB bloqueados | `tdr_documents`, `tdr_chunks`, `tdr_flags` estan en 0 |
| Dossier TDR evidencia-pagina | Piloto local solamente | Hay PDFs locales, pero no persistencia DB TDR completa |

## Recomendacion de limpieza

No ejecutar limpieza automatica todavia. Plan recomendado:

1. Exportar los 25 `source_records` con `raw_path = 'tests/fixtures/sunat_padron_sample.txt'`.
2. Extraer RUCs de esos 25 registros.
3. Cruzar contra `source_entities` donde `metadata->>'sunat_razon_social' IS NOT NULL`.
4. Si el set coincide, preparar migracion de limpieza reversible:
   - eliminar o marcar los 25 `source_records.company` fixture;
   - remover solo campos `sunat_*` de las 25 empresas afectadas;
   - preservar nombres y relaciones OCDS.
5. Agregar audit JSON antes y despues de limpiar.
6. Ejecutar tests y query de cobertura SUNAT post-limpieza.

## Recomendacion operacional

Orden correcto antes de TDR-first completo:

1. Mantener esta auditoria como baseline.
2. Instalar guard anti-fixture en todos los loaders que acepten `input_path`.
3. Limpiar fixture SUNAT de forma reversible.
4. Ejecutar un batch pequeno TDR sin OCR sobre PDFs con texto usable.
5. Solo despues integrar OCR controlado.

Frase de control:

> El TDR es la unidad de analisis, pero la verdad operacional empieza por saber que data es real y que data es fixture.
