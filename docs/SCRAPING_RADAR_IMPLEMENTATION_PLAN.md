# SCRAPING RADAR IMPLEMENTATION PLAN — AgentePerry

Fecha: 2026-05-17

Estado: plan tecnico para desarrollar el radar incremental de scraping, CDC, monitoreo de fuentes y generacion de casos investigables.

Este documento reemplaza el enfoque centrado en demo manual. El objetivo ya no es mostrar un caso aislado, sino construir una fabrica de datos publica, incremental y auditable.

---

## 1. Decision ejecutiva

AgentePerry debe evolucionar hacia un **Data Radar** continuo:

```text
fuentes publicas
  -> collectors
  -> raw snapshot store
  -> CDC / change detection
  -> normalizacion
  -> grafo operacional
  -> documentos
  -> PDF quality gate
  -> document intelligence
  -> risk scoring
  -> case candidates
  -> revision humana
  -> dossier legal-safe
```

La arquitectura recomendada es **hibrida**:

| Capa | Medio | Uso |
|---|---|---|
| DB Postgres/Supabase | `source_records`, `source_entities`, `source_relationships`, `tdr_*` | Fuente operacional para consultas, grafo y agentes |
| Nuevas tablas DB | `source_runs`, `source_record_versions`, `source_documents` | CDC formal, versionado, trazabilidad de corrida |
| Filesystem | `data/runs/<run_id>/audit.json`, `changed_records.jsonl`, `errors.jsonl` | Auditoria reproducible y debug offline |
| Filesystem actual | `data/scraped/`, `data/tdrs/`, `data/scraped/results/` | Artefactos descargados/procesados existentes |
| Filesystem futuro | `data/runs/`, `data/results/` | Corridas reproducibles y salidas canonicas nuevas |

No conviene `JSONL-only` como arquitectura final porque el repo ya tiene schema relacional vivo y `sync/loader.py`. Tampoco conviene `DB-only` porque se pierde reproducibilidad de corrida. La ruta correcta es **DB para operar, JSONL para auditar**.

---

## 2. Producto objetivo

Comandos finales deseados:

```bash
# Radar diario sobre contrataciones
agenteperry radar run --source ocds_peru --mode incremental --analyze-docs

# Radar sobre padron SUNAT
agenteperry radar run --source sunat_padron --mode incremental

# Radar sobre sanciones
agenteperry radar run --source contraloria_sanciones --mode incremental

# Health checks de fuentes
agenteperry radar health --all

# Caso especifico
agenteperry run-case --ocid ocds-dgv273-seacev3-988512

# Casos pendientes para revision humana
agenteperry cases list --status pending_review
```

---

## 3. Arquitectura propuesta

```text
Scheduler
  -> Source Registry
  -> Source Health Monitor
  -> Collector Runner
  -> Raw Snapshot Store
  -> CDC Engine
  -> Normalizer
  -> Source Records DB Sync
  -> Entity Resolver
  -> Graph Builder
  -> Document Discovery
  -> Document Downloader
  -> PDF Quality Gate
  -> Document Intelligence Agent
  -> Evidence Critic Agent
  -> Case Builder Agent
  -> Human Review Queue
```

### Responsabilidades por capa

| Capa | Responsabilidad | Estado actual |
|---|---|---|
| Source Registry | Catalogar fuentes, tipo, prioridad, metodo, campos esperados | Existe `sources/catalog.py` |
| Collectors | Extraer registros de una fuente publica | 5 collectors implementados |
| CDC Engine | Detectar new/changed/unchanged/failed por hash | Existe solo para OCDS en `cdc/`; falta generico |
| Sync DB | Upsert de records/entities/relationships | Existe `sync/loader.py` |
| Graph Builder | Convertir records a nodos/aristas | Existe `graph/mapping.py` |
| Document Pipeline | Descargar/auditar/analisar PDFs | Existe `tdr/` |
| Case Builder | Crear caso investigable legal-safe | Parcial via `tdr/dossier.py` |
| Human Review | Aprobar/rechazar antes de difundir | No existe |

---

## 4. Fuentes actuales y estado de desarrollo

### P0 — Fundacionales

| Source code | Fuente | Tipo registrado | Collector | Estado | Proposito |
|---|---|---:|---|---|---|
| `ocds_peru` | OCDS Peru | bulk_download | `OCDSPeruCollector` | Implementado | Contratos, entidades, proveedores, documentos, montos |
| `sunat_padron` | SUNAT Padron Reducido RUC | bulk_download | `SunatPadronCollector` | Implementado | Estado/condicion/ubigeo de empresas |
| `seace_oece` | OECE/SEACE Datos Abiertos | bulk_download | `OeceCollector` | Implementado | Comites, contratos, ordenes, proveedores, procesos |
| `contraloria_sanciones` | Registro de sanciones | playwright en catalogo, collector bulk CSV implementado | `SancionesCollector` | Implementado parcial | Personas/proveedores sancionados |
| `ley_32069` | Ley de contrataciones | reference | sin collector operativo | Metadata | Referencia legal/RAG |

Observacion: `contraloria_sanciones` esta registrada como `PLAYWRIGHT`, pero el repo ya tiene `SancionesCollector` por descarga CSV/datos abiertos. Hay que corregir el catalogo o documentar doble metodo: `bulk_download` primero, Playwright como fallback.

### P1 — Siguientes fuentes utiles

| Source code | Fuente | Metodo recomendado | Estado actual | Valor |
|---|---|---|---|---|
| `mef_datos_abiertos` | MEF CKAN | CKAN API | Implementado (`MefCkanCollector`) | Presupuesto, devengado, girado |
| `cgr_informes` | Contraloria Informes | Playwright/XHR/PDF | Pendiente | Informes de control por entidad/proceso |
| `sunat_multi_ruc` | SUNAT Consulta Multiple | form scraping semi-manual | Pendiente | Actividad economica y datos vivos puntuales |
| `congreso_leyes` | Congreso leyes | form scraping | Pendiente | Marco legal y comisiones |
| `convoca_contrataciones` | Convoca | HTML/feeds livianos | Pendiente | Contexto periodistico, no fuente primaria |

### P2/P3 — Diferidos o manual-assisted

| Source code | Fuente | Estado recomendado |
|---|---|---|
| `onpe_claridad` | ONPE Claridad | Diferir hasta spec activa |
| `jne_voto_informado` | JNE Voto Informado | Diferir hasta spec activa |
| `jne_plataforma` | JNE Plataforma Electoral | Diferir hasta spec activa |
| `sidji_dji` | Declaraciones Juradas de Intereses | Manual/semi-automatico, legal-safe |
| `sunarp_conoce` | SUNARP Conoce Aqui | Manual-assisted, no masivo |
| `sunarp_sprl` | SUNARP SPRL | Pago/manual, revisar terminos |

---

## 5. Datos scrapeados actualmente

### 5.1 OCDS enriquecido

Archivos actuales:

| Archivo | Registros aproximados/verificados | Descripcion |
|---|---:|---|
| `data/scraped/ocds/records.jsonl` | grande, muestreado | Records normalizados desde OCDS |
| `data/scraped/ocds/contracts_2026.jsonl` | grande, muestreado | Contratos 2026 normalizados |
| `data/scraped/ocds/graph.json` | existe | Grafo generado desde records OCDS |
| `data/scraped/ocds/graph_2026.jsonl` | existe | Grafo 2026 en JSONL |
| `data/scraped/ocds/audit.json` | existe | Auditoria de colecta/procesamiento |
| `data/scraped/filtered/salud_2024_2025.jsonl` | 2,566 | Salud filtrado |
| `data/scraped/filtered/salud_2024_2025_with_documents.jsonl` | 2,566 | Salud con documentos OCDS |
| `data/scraped/filtered/ambiente_2024_2025.jsonl` | 99 | Ambiente filtrado |
| `data/scraped/filtered/ambiente_2024_2025_with_documents.jsonl` | 99 | Ambiente con documentos OCDS |

Columnas top-level vistas en `records.jsonl` / `contracts_2026.jsonl`:

```text
source_code
external_id
record_type
raw_data
parsed_data
raw_path
checksum
content_type
fetched_at
period_year
region
entity_name
entity_ruc
supplier_name
supplier_ruc
monto
fecha
source_url
page_number
evidence_quote
```

Campos frecuentes en `parsed_data` OCDS:

```text
ocid
tender_id
award_id
award_status
procedure_type
contracts_count
```

Campos importantes dentro de `raw_data` OCDS:

```text
ocid
id
date
publishedDate
buyer
parties
planning
tender
awards
contracts
sources
tag
dataSegmentation
```

Documentos disponibles en `raw_data.tender.documents[]` o en campo `documents` de filtrados:

```text
id
documentType
format
url
language
datePublished
dateModified
```

Uso actual: base principal para detectar procesos, proveedores, entidades, montos, tenderers, documentos y contratos.

### 5.2 SUNAT Padron

Archivo actual:

| Archivo | Registros | Descripcion |
|---|---:|---|
| `data/scraped/collectors/sunat_padron/records.jsonl` | 25 | Fixture/smoke realista del padron reducido |
| `data/scraped/collectors/sunat_padron/graph.json` | existe | Grafo de empresas SUNAT |
| `data/scraped/collectors/sunat_padron/audit.json` | existe | Auditoria del collector |

Columnas top-level normalizadas son las mismas de `CollectionResult.to_record()`.

Campos en `parsed_data` SUNAT:

```text
ruc
razon_social
estado
condicion
ubigeo
domicilio_fiscal
```

Campos en `raw_data` SUNAT:

```text
ruc
razon_social
estado
condicion
ubigeo
tipo_via
nombre_via
codigo_zona
tipo_zona
numero
interior
lote
departamento
manzana
kilometro
```

Uso deseado: enriquecer proveedores de OCDS por `supplier_ruc` y detectar estados como `NO HABIDO`, `BAJA`, domicilios compartidos o inconsistencias de ubigeo.

### 5.3 OECE/SEACE Datos Abiertos

Estado en repo: `OeceCollector` implementado con categorias:

```text
pac
procedimientos
convocatorias
contratos
ordenes_compra
proveedores
consorcios
entidades
comites
pronunciamientos
```

Datos locales verificados: no hay dataset grande persistido en `data/scraped/collectors/oece/`; el directorio existe pero esta vacio.

Uso deseado: complementar OCDS con comites, ordenes, proveedores, procedimientos y pronunciamientos cuando OCDS no tenga detalle suficiente.

### 5.4 Contraloria sanciones

Estado en repo: `SancionesCollector` existe y produce `CollectionResult`.

Datos locales verificados: no se encontro dataset persistido de sanciones en `data/scraped/collectors/`.

Uso deseado: conectar RUC/DNI/persona sancionada con proveedores, representantes, comites o funcionarios. Debe ser legal-safe: indicador de revision, no conclusion.

### 5.5 Documentos TDR/PDFs

Archivos/directorios:

| Ruta | Estado | Descripcion |
|---|---|---|
| `data/scraped/tdrs/` | existe | PDFs/RAR/ZIP descargados por sector/OCID |
| `data/scraped/tdrs/pdf_usability_report.csv` | 14 PDFs/artefactos auditados + header | Reporte usability |
| `data/scraped/tdrs/pdf_usability_audit.json` | existe | Auditoria JSON |
| `data/scraped/results/` | 3 OCID | `pages.json`, `chunks.json`, `flags.json`, `dossier.json`, `dossier.md` |
| `data/golden_set/pdfs/` | existe | PDFs de validacion |

Columnas de `pdf_usability_report.csv`:

```text
path
sector
extension
total_pages
pages_with_text
pages_needs_ocr
coverage_pct
tdr_status
is_usable
notes
```

Columnas de `tdr_recon/recon_20_processes.csv`:

```text
ocid
sector
entidad
objeto
monto
fecha
proveedor_nombre
proveedor_ruc
source_url
seace_url_candidate
tdr_status
tdr_url
tdr_path
access_method
notes
```

---

## 6. Conexion de datos deseada

### 6.1 OCDS como columna vertebral

OCDS debe ser el eje inicial porque trae:

```text
ocid
external_id
buyer/entity
supplier
monto
fecha
procedure_type
tender.documents[]
tenderers[]
awards[]
contracts[]
```

Desde OCDS se derivan entidades base:

| Entidad | Key | Fuente |
|---|---|---|
| Public entity | `entity_ruc` o CONSUCODE ID | `buyer`, `parties` |
| Supplier/company | `supplier_ruc` si existe, si no `PE-RUC-*` de parties | `awards.suppliers`, `parties` |
| Contract/process | `external_id`, `ocid`, `tender_id`, `award_id` | `release` |
| Document | `document.id` + `url` | `tender.documents`, `contracts.documents` |

### 6.2 SUNAT enrichment

Join principal:

```text
ocds.supplier_ruc OR parties.identifier.id
  -> sunat_padron.parsed_data.ruc
```

Agrega:

```text
razon_social oficial
estado
condicion
ubigeo
domicilio_fiscal
```

Señales posibles:

```text
proveedor no habido
proveedor con baja
proveedor con domicilio compartido con otros proveedores
proveedor con ubigeo lejano/inconsistente para servicio local
```

### 6.3 OECE/SEACE enrichment

Join principal:

```text
ocds.ocid / tender_id / procedure_code
  -> oece.procedimientos.codigo_proceso
  -> oece.contratos / oece.comites / oece.ordenes
```

Agrega:

```text
miembros de comite
ordenes de compra
contratos administrativos
proveedores/consorcios
pronunciamientos
```

Señales posibles:

```text
comite repetido en procesos similares
proveedor recurrente con la misma entidad
ordenes repetidas bajo umbrales
consorcios con participantes recurrentes
```

### 6.4 Contraloria sanciones

Joins posibles:

```text
persona sancionada -> miembro de comite / funcionario / representante
proveedor RUC -> persona o razon social relacionada si existe
entidad sancionadora/entidad vinculada -> buyer/entity
```

Señales posibles:

```text
persona sancionada aparece como funcionario/comite
proveedor vinculado a persona sancionada
entidad con historial de sanciones relacionadas
```

Nota: todas estas son señales de revision, no conclusiones.

### 6.5 Documentos y TDRs

Desde OCDS:

```text
tender.documents[]
contracts.documents[]
```

Flujo:

```text
document.url
  -> download_document()
  -> checksum
  -> detect file_type pdf/zip/rar
  -> inspect_pdf_text_layer()
  -> available / partial / needs_ocr / archive_pending
  -> parse pages
  -> chunks
  -> flags
  -> dossier
```

---

## 7. CDC recomendado

### Hash por fuente

Cada fuente debe definir:

```text
source_code
external_id
record_type
raw_hash
normalized_hash
first_seen_at
last_seen_at
changed_at
run_id
status
```

### Regla general

```python
external_id = build_external_id(record)
normalized = normalize(record)
hash = sha256(canonical_json(normalized))

if external_id not in index:
    change_type = "new"
elif index[external_id] != hash:
    change_type = "changed"
else:
    change_type = "unchanged"
```

### Storage recomendado

DB:

```text
source_runs
source_record_versions
source_records
```

Filesystem:

```text
data/runs/<run_id>/audit.json
data/runs/<run_id>/changed_records.jsonl
data/runs/<run_id>/errors.jsonl
data/runs/<run_id>/documents_manifest.jsonl
data/runs/<source_code>/hashes.json
```

---

## 8. Implementacion por fases

### Activity 8A — Radar Core Foundation

Objetivo: crear base sin nuevas fuentes.

Archivos:

```text
apps/scrapers/src/agenteperry/radar/__init__.py
apps/scrapers/src/agenteperry/radar/models.py
apps/scrapers/src/agenteperry/radar/cdc.py
apps/scrapers/src/agenteperry/radar/health.py
apps/scrapers/src/agenteperry/radar/orchestrator.py
apps/scrapers/src/agenteperry/radar/cli.py
apps/scrapers/src/agenteperry/cli.py
tests/test_radar_cdc.py
tests/test_radar_health.py
tests/test_radar_orchestrator.py
```

Criterios:

```text
agenteperry radar health --all
agenteperry radar run --source ocds_peru --mode incremental --limit 100
data/runs/<run_id>/audit.json generado
data/runs/<source_code>/hashes.json generado
tests + ruff + pyright pasan
```

### Activity 8B — DB CDC tables

Objetivo: hacer CDC operacional, no solo audit files.

Migration:

```text
packages/db/migrations/0004_source_runs.sql
```

Tablas:

```text
source_runs
source_record_versions
source_documents
```

Criterios:

```text
cada radar run crea source_run
cada new/changed crea source_record_version
source_records sigue siendo estado actual
```

### Activity 8C — Document Discovery integration

Objetivo: del contrato cambiado al documento nuevo.

Integra:

```text
select_tdr_documents()
download_document()
inspect_pdf_text_layer()
```

Criterios:

```text
documents_discovered
documents_downloaded
pdf_available
pdf_needs_ocr
archive_pending
```

### Activity 8D — Analyzer behind flag

Objetivo: analizar solo si se pide.

Comando:

```bash
agenteperry radar run --source ocds_peru --mode incremental --limit 100 --analyze-docs
```

Criterios:

```text
dossiers_generated
flags_generated
case_candidates_generated
```

---

## 9. Source Registry esperado por fuente

Cada fuente debe tener contrato tecnico:

```yaml
source_code: ocds_peru
name: OCDS Peru
priority: P0
access_type: bulk_download
requires_playwright: false
update_frequency: daily
primary_key:
  - external_id
cdc_strategy:
  type: normalized_hash
  hash_fields:
    - external_id
    - parsed_data
    - documents
outputs:
  - source_records
  - source_entities
  - source_relationships
  - source_documents
health_checks:
  - source_url_available
  - collector_available
  - schema_valid
```

Actualmente el catalogo esta en Python (`sources/catalog.py`). No recomiendo moverlo a YAML todavia. Primero agregar validaciones y health checks sobre el catalogo existente.

---

## 10. Casos investigables que el radar debe producir

No debe producir acusaciones. Debe producir candidatos de revision:

| Caso candidato | Fuentes requeridas | Señal |
|---|---|---|
| Proveedor con estado SUNAT no optimo gana contrato | OCDS + SUNAT | Requiere revision de condicion tributaria |
| Proceso con documento nuevo o modificado | OCDS CDC | Requiere reanalisis documental |
| PDF publicado pero no usable | OCDS + PDF gate | Requiere OCR o acceso alternativo |
| Contrato alto monto con unico postor | OCDS | Requiere explicacion de competencia |
| Comite recurrente con mismo proveedor | OECE comites + OCDS | Patron atipico |
| Proveedor/funcionario con sancion relacionada | Sanciones + OECE/OCDS | Requiere revision humana |
| Bases integradas modificadas tras consultas | OCDS documents CDC | Requiere comparar versiones |

---

## 11. Reporte final por fuente: scrapeado, faltante, columnas

| Fuente | Scrapeado ahora | Columnas/datos actuales | Falta desarrollar |
|---|---|---|---|
| OCDS Peru | Si: `records.jsonl`, `contracts_2026.jsonl`, filtered salud/ambiente | `external_id`, `ocid`, `entity_name`, `supplier_name`, `monto`, `fecha`, `parsed_data`, `raw_data`, `tender.documents[]` | CDC generico, source_runs, document_versions, incremental diario |
| SUNAT Padron | Si: 25 registros de fixture/smoke | `ruc`, `razon_social`, `estado`, `condicion`, `ubigeo`, `domicilio_fiscal` | Batch real completo, CDC checksum ZIP, join masivo con proveedores OCDS |
| OECE/SEACE | Collector listo, data local vacia | Segun categoria: procesos, contratos, ordenes, comites, proveedores | Ejecutar collector por categoria/año, normalizar columnas estables, CDC por categoria |
| Contraloria Sanciones | Collector listo, data local no encontrada | Esperado: persona/RUC, tipo_sancion, estado, vigencia, entidad | Correr collector, corregir catalogo type, CDC por documento/checksum |
| MEF Datos Abiertos | Collector CKAN listo, data local no encontrada | Dataset/resource metadata CKAN | Definir datasets objetivo y normalizadores |
| TDR/PDFs | Si: PDFs descargados, audit, 3 dossiers | PDF path, coverage, status, pages/chunks/flags/dossier | Integrar al radar incremental con document discovery |
| CGR Informes | No | No disponible | Playwright framework + health monitor antes del collector |
| ONPE/JNE/SUNARP | No | No disponible | Diferido hasta spec activa |

---

## 12. Orden recomendado desde ahora

1. **Activity 8A — Radar Core Foundation**
   - CDC generico por `source_code + external_id`.
   - Audit files por corrida.
   - Health checks basicos.
   - `radar run` y `radar health`.

2. **Activity 8B — DB CDC Schema**
   - `source_runs`.
   - `source_record_versions`.
   - `source_documents`.

3. **Activity 8C — OCDS Document Discovery**
   - Detectar documentos nuevos/cambiados.
   - Descargar solo documentos nuevos.
   - PDF gate obligatorio.

4. **Activity 9 — OECE/SEACE categorias criticas**
   - `comites`.
   - `contratos`.
   - `ordenes_compra`.
   - `proveedores`.

5. **Activity 10 — Contraloria Sanciones**
   - Collector real ejecutado.
   - CDC por checksum.
   - Join con entidades/personas/proveedores.

6. **Activity 11 — Playwright Monitoring Foundation**
   - DOM snapshot.
   - selector health.
   - screenshot.
   - XHR capture.

7. **Activity 12 — CGR Informes Collector**
   - Primera fuente dinamica con Playwright.

---

## 13. Enfoque tecnico para desarrollar sin romper el repo

### Principios

1. No duplicar collectors.
2. No reemplazar `cdc/` todavia; envolverlo o dejarlo como comando legacy.
3. No mover data existente.
4. No usar Playwright hasta tener health framework.
5. No hacer UI hasta que radar genere casos pendientes.
6. Todo output investigativo debe tener evidencia, fuente y estado de revision.

### Implementacion segura

```text
radar/ nuevo
  usa collectors existentes
  usa sync/loader.py existente si DB esta disponible
  escribe data/runs siempre
  no rompe cdc run
  no rompe sources pipeline
```

### Estado operacional esperado despues de Activity 8A

```text
Miguel ejecuta:
agenteperry radar run --source ocds_peru --mode incremental --limit 100

Sistema responde:
- records_seen
- records_new
- records_changed
- records_unchanged
- errors
- audit path
- changed_records path
- hashes actualizados
```

---

## 14. Riesgos principales

| Riesgo | Impacto | Mitigacion |
|---|---|---|
| Catalogo dice PLAYWRIGHT pero collector real es bulk | Confusion de arquitectura | Agregar `method_notes` y health check por collector real |
| Datasets grandes OCDS tardan mucho | Corridas lentas | `--limit`, incremental hashes, streaming futuro |
| RUC de proveedores incompleto en OCDS | Joins pobres con SUNAT | Extraer RUC desde `parties[].identifier` y normalizar consorcios |
| PDFs reales vienen escaneados/ZIP/RAR | Analyzer no corre | `needs_ocr` / `archive_pending`, no forzar OCR |
| DB schema no tiene runs/versiones | No hay CDC formal operacional | Activity 8B migration |
| Mezcla de `data/tdrs` y `data/scraped/tdrs` | Confusion de paths | Definir canonical path nuevo en radar |

---

## 15. Conclusion

El repo ya tiene piezas fuertes: collectors, source registry, sync DB, graph mapping, TDR pipeline y dossier generator. Lo que falta no es mas demo: falta **orquestacion incremental**.

La mejor implementacion es:

```text
Radar Core primero
DB + JSONL audit despues
document discovery incremental
OECE/SEACE enrichment
Contraloria sanciones
Playwright foundation
fuentes dinamicas
agentizacion
UI al final
```

Frase de control del equipo:

> El caso demo prueba que el motor puede leer. El radar prueba que AgentePerry puede vigilar fuentes publicas todos los dias sin busqueda manual.

---

## 16. Activity 8A implemented — Radar Core Foundation

Estado: implementado como nucleo filesystem-first, sin reemplazar `cdc/` legacy y sin integrar aun document discovery completo.

### Modulos creados

```text
apps/scrapers/src/agenteperry/radar/__init__.py
apps/scrapers/src/agenteperry/radar/models.py
apps/scrapers/src/agenteperry/radar/cdc.py
apps/scrapers/src/agenteperry/radar/health.py
apps/scrapers/src/agenteperry/radar/orchestrator.py
apps/scrapers/src/agenteperry/radar/cli.py
```

### Comandos disponibles

```bash
agenteperry radar run --source ocds_peru --mode incremental --limit 100
agenteperry radar run --source ocds_peru --mode incremental --limit 100 --analyze-docs
agenteperry radar health --source ocds_peru
agenteperry radar health --all
```

### Outputs de corrida

```text
data/runs/<source_code>/hashes.json
data/runs/<run_id>/audit.json
data/runs/<run_id>/changed_records.jsonl
data/runs/<run_id>/run_manifest.json
```

### Semantica CDC implementada

Key logica:

```text
source_code + external_id
```

Fallback:

```text
source_code + checksum
```

Si no hay `external_id` ni `checksum`, el record se clasifica como `failed`.

Hash normalizado sobre:

```text
external_id
record_type
parsed_data
monto
fecha
supplier_ruc / proveedor_ruc
entity_ruc
```

No se hashea todo `raw_data` para evitar ruido por timestamps o payloads enormes.

### Limitaciones de Activity 8A

- `analyze_docs=True` solo registra warning; la integracion real de document discovery queda para Activity 8C.
- No crea tablas DB nuevas; `source_runs` y `source_record_versions` quedan para Activity 8B.
- Health checks Playwright devuelven `unknown`; no abren browser.
- El orchestrator usa collectors existentes y rutas locales conocidas como fallback cuando el collector requiere input.

### Siguiente actividad

**Activity 8B — DB CDC Schema**

Crear:

```text
source_runs
source_record_versions
source_documents
```

Objetivo: que el radar sea operacional en Postgres/Supabase y no solo auditable por filesystem.
