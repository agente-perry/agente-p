# SPEC-0009: Scraping Pipeline Phase 1

## Meta

- **Spec ID**: SPEC-0009
- **Title**: Scraping Pipeline Phase 1
- **Status**: active
- **Created**: 2026-05-17
- **Branch**: `feat/SPEC-0009-scraping-pipeline-phase1`
- **Owner**: scraping team
- **Priority**: P0

## Objetivo

Construir el pipeline de ingestión de datos para AgentePerry:

1. Descargar OCDS filtrado (salud + ambiente)
2. Descargar SUNAT Padrón Reducido completo
3. Descargar documentos PDF desde URLs SEACE
4. Clasificar cada PDF por nivel OCR (textual/mixed/scanned)
5. Generar manifests CSV validados
6. Construir process_document_packs.jsonl
7. Seleccionar Golden Set

## Alcance

### Incluye (P0)

- [x] Descarga OCDS 2024-2025 desde URL pública o GCS bucket
- [x] Filtrado por sector salud y ambiente
- [x] Generación de manifests: `processes.csv`, `documents.csv`, `awards.csv`
- [x] Descarga SUNAT Padrón Reducido (~14.5M RUCs, ISO-8859-1)
- [x] Descarga documentos PDF desde URLs SEACE (rate limit 1 req/s)
- [x] Clasificación OCR con MiniMax API (parallel, ilimitado)
- [x] Validación de entrega con `validate_scraping_delivery.py`
- [x] Construcción de `process_document_packs.jsonl`
- [x] Selección de Golden Set (50-100 procesos)

### Excluye (deferred)

- Tribunal OECE (resoluciones PDF)
- SUNARP
- Contraloria
- DJI / ONPE / JNE
- Neo4j / GraphRAG
- ConflictMap

## Fuentes confirmadas

| Fuente | URL | Formato | Auth | Viabilidad |
|--------|-----|---------|------|------------|
| OCDS Perú | `data.open-contracting.org/es/publication/135/download?name={year}.jsonl.gz` | JSONL.gz | Ninguna | P0 ✅ |
| SEACE docs | `prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>` | PDF | Ninguna | P0 ✅ |
| SUNAT Padrón | `www2.sunat.gob.pe/padron_reducido_ruc.zip` | ZIP/TXT pipe | Ninguna | P0 ✅ |

## MiniMax OCR

- API Key: `MINIMAX_API_KEY` (ilimitado)
- Base: `https://api.minimax.chat/v1`
- Modelo: `MiniCPM-v2`
- Parallelismo: configurable, default 20 workers
- Rate limit: respetado automáticamente por API ilimitada

## Manifests CSV

### processes.csv

```
process_id, ocid, seace_code, sector, entity_name, entity_ruc,
procedure_type, object_description, status, amount_estimated,
currency, publication_date, award_date, source_url, scraped_at
```

### documents.csv

```
document_id, process_id, document_type, file_name, file_path,
file_url, source_url, mime_type, file_size_bytes, sha256,
pages_total, pages_with_text, pages_needing_ocr, text_coverage_ratio,
ocr_class, ocr_required, ocr_status, downloaded_at, parse_status,
error_message
```

### awards.csv

```
award_id, process_id, supplier_name, supplier_ruc, award_amount,
award_currency, award_date, award_document_id, award_source_quote,
award_source_page, confidence
```

## Estructura de datos

```
data/scraped/seace_salud/
  processes.csv
  documents.csv
  awards.csv
  pdfs/{process_id}/*.pdf
  manifests/process_document_packs.jsonl

data/sunat/
  padron_reducido_ruc.csv (subset or full)
  padron_enriched.csv

data/golden_set/
  metadata.csv

data/scraping_validation_report.json
```

## Orden de ejecución

1. `ocds_filtered_download.py` — descarga y filtra OCDS
2. `sunat_padron_download.py` — descarga y parsea SUNAT
3. `seace_documents_download.py` — descarga PDFs con rate limit
4. `ocr_classifier.py` — clasifica PDFs con MiniMax API (parallel)
5. `validate_scraping_delivery.py` — valida manifests
6. `build_process_document_packs.py` — construye JSONL
7. `select_golden_candidates.py` — selecciona golden set
8. `phase1_orchestrator.py` — ejecuta todo en orden

## API Endpoints

No se necesita scraping HTML. Solo:

- Descarga directa (HTTP)
- APIs públicas documentadas

## Validation

```bash
python scripts/validate_scraping_delivery.py --base-dir data/scraped/seace_salud
python scripts/build_process_document_packs.py --base-dir data/scraped/seace_salud
python scripts/select_golden_candidates.py --base-dir data/scraped/seace_salud
```

## Success Criteria

- `processes.csv` con todos los contratos salud/ambiente
- `documents.csv` con todos los PDFs descargados y clasificados
- `awards.csv` con proveedores adjudicados y evidencia
- `process_document_packs.jsonl` generado sin errores
- `golden_set/metadata.csv` con 50-100 procesos verificables
- Todos los PDFs con `ocr_class` asignado (textual/mixed/scanned)
- Validación sin errores (`ok: true`)

## Backlog (futuro)

- Tribunal OECE: scraping paginado de resoluciones PDF
- SUNARP: consulta de representantes
- Contraloria: sanciones
- DJI/ONPE/JNE: relaciones políticas