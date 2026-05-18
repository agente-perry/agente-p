# SPEC-0010: TDR Downloader v1

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0010 |
| **Estado** | active |
| **Owner** | Anthony |
| **Reviewers** | @miguel |
| **Sprint / Fase** | F8 — TDR Ingest |
| **Creado** | 2026-05-16 |
| **Última actualización** | 2026-05-16 |
| **Depende de** | SPEC-0009 (TDR Discovery completado) |
| **Bloquea** | SPEC-0002 (TDR PDF Parser — ya tiene schema, necesita inputs reales) |

---

## 1. Problema

Activity 3 (SPEC-0009) confirmó que:
- 2,566 contratos Salud y 99 Ambiente/Minería tienen URLs directas SEACE en `raw_data->tender->documents[]`.
- 20/20 procesos muestreados accesibles **sin login, captcha ni paywall**.
- El motor documental (parseo PDF, chunks, embeddings, flags) está listo pero `tdr_documents = 0`.

Falta la pieza que conecta las URLs OCDS con el motor documental: un downloader controlado.

## 2. Objetivo

> Implementar `TdrDownloader` — un downloader reproducible, trazable y controlado que consuma documentos de contratos OCDS priorizados y los registre en `tdr_documents`.

Después de este spec:
- `tdr_documents` contiene ≥ 10 registros reales de Salud y ≥ 5 de Ambiente.
- Cada registro tiene: `external_id`, `sector`, `entity_name`, `monto`, `fecha`, `file_path`, `checksum`, `download_status`, `source_record_id`.
- CLI: `agenteperry tdr download --sector salud --limit 10`.
- `audit.json` con métricas de descarga.
- Tests unitarios de filtrado y selección.
- 0 scraping HTML de SEACE. 0 Playwright.

## 3. Contexto técnico

### 3.1 Fuente de documentos

Los contratos OCDS almacenados en `source_records` contienen en `raw_data`:

```json
{
  "tender": {
    "documents": [
      {
        "title": "Bases Administrativas",
        "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=d0f684bf-...",
        "format": "application/pdf"
      },
      {
        "title": "Pliego de absolución de consultas y observaciones",
        "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=cee1cdc2-...",
        "format": "application/pdf"
      }
    ]
  }
}
```

### 3.2 Schema `tdr_documents`

Ya existe (migración `0002_tdr_core.sql`). Columnas relevantes:

```sql
id                 uuid        NOT NULL DEFAULT gen_random_uuid()
external_id        text        NOT NULL UNIQUE
title              text        NOT NULL
entity_name        text
source_url         text
file_url           text        -- URL SEACE original
procedure_code     text        -- tender.id de OCDS
sector             text        -- 'salud' | 'ambiente_mineria'
local_path         text        -- ruta relativa al archivo descargado
checksum           text        -- SHA256 del archivo
download_status    text        -- available | downloaded | failed | ...
publication_date   date
estimated_value    numeric
created_at         timestamptz
```

Si faltan columnas (`source_record_id`, `monto`, `document_type`, `download_error`), se agregan via migración `0004_tdr_documents_downloader.sql`.

### 3.3 Estructura de archivos de salida

```
data/tdrs/
  salud/
    <ocid>/
      bases_admin.pdf
      bases_integradas.pdf
      pliego_absoluciones.pdf
  ambiente_mineria/
    <ocid>/
      bases_admin.pdf
```

### 3.4 Query SQL de entrada

```sql
SELECT
    sr.id           AS source_record_id,
    sr.external_id  AS ocid,
    sr.entity_name,
    sr.monto,
    sr.fecha,
    sr.supplier_name,
    sr.supplier_ruc,
    sr.raw_data->'tender'->>'title'                    AS objeto,
    sr.raw_data->'tender'->>'procurementMethodDetails' AS modalidad,
    d->>'title'  AS doc_title,
    d->>'url'    AS doc_url,
    d->>'format' AS doc_format
FROM source_records sr,
     jsonb_array_elements(sr.raw_data->'tender'->'documents') AS d
WHERE sr.record_type = 'contract'
  AND sr.fecha >= '2024-01-01'
  AND (sr.entity_name ILIKE '%salud%')
  AND sr.raw_data->'tender'->'documents' IS NOT NULL
  AND d->>'url' IS NOT NULL
  AND (
      d->>'title' ILIKE '%base%'
      OR d->>'title' ILIKE '%tdr%'
      OR d->>'title' ILIKE '%term%'
      OR d->>'title' ILIKE '%pliego%'
      OR d->>'title' ILIKE '%especif%'
  )
ORDER BY sr.monto DESC NULLS LAST;
```

## 4. Decisiones técnicas

| Decisión | Justificación |
|----------|---------------|
| **No es SEACE scraper** | Usamos URLs ya en OCDS. No hacemos scraping HTML ni XHR intercept. |
| **No Playwright en v1** | No es necesario: URL directa funciona con `urllib.request`. |
| **Rate limit: 1 req/s** | Cortesía con SEACE. No hay evidencia de rate limiting agresivo. |
| **Retry: 3 intentos con backoff exponencial** | URLs de Alfresco son estables; 3 intentos suficientes. |
| **Max docs por contrato: configurable (default: 3)** | Evitar descargar todos los 28 docs de un proceso. Priorizar bases/pliegos. |
| **Extensiones permitidas: pdf, rar, zip, doc, docx** | RAR y ZIP encontrados en recon. DOC/DOCX frecuentes en SEACE. |
| **Checksum SHA256** | Deduplicación e integridad; igual al patrón OCDS pipeline. |
| **`data/tdrs/` en .gitignore** | Archivos binarios, no en VCS. `data/` ya está en `.gitignore` parcialmente. |
| **`tdr_documents` como registro maestro** | Ya existe. Evitar tabla nueva solo para downloader. |
| **No parsear en v1** | El parser (SPEC-0002) espera el archivo en disco + metadata en DB. El downloader solo ingesta. |

## 5. Statuses de documento

| Status | Descripción |
|--------|-------------|
| `pending` | Identificado, no descargado todavía |
| `downloaded` | Descarga exitosa, checksum calculado, metadata en DB |
| `not_found` | HTTP 404 o URL inaccesible |
| `failed` | Error network no recuperable después de 3 intentos |
| `unsupported_format` | Content-Type no es pdf/zip/rar/doc/docx |
| `duplicate` | Checksum ya existe en `tdr_documents` |
| `manual_required` | Requiere login/captcha/interacción manual |
| `skipped` | Fuera de límite, tipo de documento no prioritario |

## 6. Prioridad de tipos de documento

Orden de descarga por score (mayor = más prioritario):

| Título contiene | Score |
|---|---|
| `tdr` | 100 |
| `términos de referencia` | 100 |
| `especificaciones técnicas` | 90 |
| `bases integradas` | 80 |
| `bases administrativas` | 80 |
| `pliego de absolución` | 60 |
| `pliego de observaciones` | 60 |
| `bases` | 50 |
| Otros | 10 |

## 7. Metadata a preservar en `tdr_documents`

```python
{
    "external_id": "<ocid>-<doc_index>",        # único
    "title": "Bases Integradas",                 # tender.document.title
    "entity_name": "ESSALUD",                    # source_records.entity_name
    "source_url": "<seace_url>",                 # tender.document.url
    "file_url": "<seace_url>",                   # igual a source_url en v1
    "procedure_code": "<tender_id>",             # raw_data->tender->id
    "sector": "salud",                           # derivado de keywords
    "local_path": "data/tdrs/salud/<ocid>/bases_integradas.pdf",
    "checksum": "sha256:...",
    "download_status": "downloaded",
    "publication_date": "2024-08-23",            # source_records.fecha
    "estimated_value": 347883662.85,             # source_records.monto
    "source_record_id": "<uuid>",                # source_records.id (si columna existe)
}
```

## 8. CLI propuesto

```bash
# Descargar hasta 10 contratos Salud
agenteperry tdr download --sector salud --limit 10

# Descargar hasta 5 contratos Ambiente/Minería
agenteperry tdr download --sector ambiente --limit 5

# Usar JSONL de Activity 3 en vez de DB
agenteperry tdr download --sector salud --input data/filtered/salud_2024_2025.jsonl --limit 10

# Dry-run: solo mostrar qué se descargaría
agenteperry tdr download --sector salud --limit 10 --dry-run

# Max docs por contrato
agenteperry tdr download --sector salud --limit 10 --max-docs 2
```

## 9. Criterios de aceptación

- [ ] `TdrDownloader` en `apps/scrapers/src/agenteperry/tdr/downloader.py`.
- [ ] Filtro de documentos por título (score-based, configurable).
- [ ] Rate limit: 1 req/s entre descargas.
- [ ] Retry: 3 intentos con backoff (1s, 4s, 9s).
- [ ] Checksum SHA256 calculado y guardado.
- [ ] Status `downloaded` / `failed` / `not_found` por documento.
- [ ] `tdr_documents` upserted con metadata completa.
- [ ] Archivo en `data/tdrs/<sector>/<ocid>/<sanitized_filename>`.
- [ ] CLI: `agenteperry tdr download --sector salud --limit 10`.
- [ ] `audit.json` en `data/tdrs/audit_<sector>_<timestamp>.json`.
- [ ] Migración `0004` si faltan columnas necesarias.
- [ ] Tests unitarios: filtro de docs, score, sanitize_filename, checksum.
- [ ] 0 ruff, 0 pyright, pytest pasa.
- [ ] No descargar nada en tests (mock `urllib.request`).

## 10. Out of scope

- ❌ Parseo de PDFs (SPEC-0002).
- ❌ Chunks, embeddings, flags (SPEC-0003/0004).
- ❌ Scraping HTML de SEACE.
- ❌ Playwright.
- ❌ SUNAT Task 3.
- ❌ SEACE/OECE pipeline masivo.
- ❌ Frontend, dashboard, ConflictMap.
- ❌ Descarga de todos los documentos (solo bases/TDR/pliegos priorizados).

## 11. Riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| URL SEACE expirada/rota | Media | Media | Retry + status `not_found`; log URL para recon manual |
| Archivo binario no legible (RAR corruption) | Baja | Baja | Validar Content-Type y tamaño; log para triage manual |
| Rate limiting SEACE no documentado | Media | Media | 1 req/s; si 429 → backoff × 5, log `failed` |
| `tdr_documents` sin columnas `source_record_id` / `monto` | Alta | Baja | Migración 0004 la agrega si falta |
| `.gitignore` no cubre `data/tdrs/` | Alta | Medio | Verificar y actualizar antes de commit |

## 12. Branch esperada

```
feat/SPEC-0010-tdr-downloader-v1
```

## 13. Commit sugerido

```
feat(scrapers): implement TDR downloader v1 with OCDS document extraction (SPEC-0010)
```

## 14. Anexos

- Discovery report: `docs/TDR_DISCOVERY_REPORT.md`
- Recon CSV: `data/tdr_recon/recon_20_processes.csv`
- TDRs de prueba: `data/tdrs/salud/`, `data/tdrs/ambiente/`
- Query ingesta: ver sección 3.4
- Schema existente: `packages/db/migrations/0002_tdr_core.sql`
