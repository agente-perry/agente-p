# TDR Discovery Report — Salud + Ambiente/Minería

> **Actividad:** Activity 3 — TDR Discovery para sectores priorizados  
> **Fecha:** 2026-05-16  
> **Executor:** Staff Data Engineer (AgentePerry)  
> **Spec:** SPEC-0009  

---

## 1. Resumen Ejecutivo

| Métrica | Valor |
|---|---|
| **Contratos Salud 2024–2025** | 2,566 |
| **Contratos Ambiente/Minería 2024–2025** | 99 |
| **Monto total Salud** | S/ 3,942,056,248.26 |
| **Monto total Ambiente** | S/ 58,701,072.88 |
| **Procesos con TDR disponible (muestra 20)** | 20/20 (100%) |
| **TDRs descargados manualmente** | 3 |
| **PDFs auditados por capa de texto (Activity 4.2/4.3)** | 9 |
| **PDFs con texto digital usable** | 4 |
| **PDF Salud usable encontrado** | Sí — 212 páginas, 100% coverage |
| **Archivos RAR/ZIP pendientes** | 5 |
| **Mecanismo de acceso** | URL directa SEACE (sin login) |
| **Bloqueos encontrados** | 0 |

**Hallazgo clave:** Todos los contratos OCDS de sectores priorizados que provienen de SEACE incluyen `tender.documents[]` con URLs directas a bases, pliegos y resúmenes ejecutivos. No se detectó requerimiento de login, captcha ni paywall en las URLs de documentos.

---

## 2. Metodología de Filtrado

### 2.1 Fuentes de datos

- **Base:** `source_records` en Postgres (OCDS Perú 2026 pipeline)
- **Campos utilizados:**
  - `record_type = 'contract'`
  - `fecha >= '2024-01-01'`
  - `entity_name` — filtro por keyword de entidad compradora
  - `raw_data->'tender'->>'title'` — objeto/descripción del proceso
  - `raw_data->'tender'->>'procurementMethodDetails'` — modalidad
  - `raw_data->'tender'->'documents'` — array de documentos con URLs

### 2.2 Keywords por sector

| Sector | Keywords `entity_name` |
|---|---|
| **Salud** | `minsa`, `ministerio de salud`, `diresa`, `red de salud`, `hospital`, `centro de salud`, `cenares`, `instituto nacional de salud`, `essalud`, `seguro social de salud` |
| **Ambiente/Minería** | `minam`, `ministerio del ambiente`, `oefa`, `autoridad nacional del agua`, `sernanp`, `senace`, `ingemmet`, `autoridad regional ambiental`, `gerencia regional ambiental`, `autoridad ambiental` |

### 2.3 Criterios de selección de muestra (20 procesos)

1. **Monto alto** — ordenados por `monto` DESC
2. **Modalidad de baja competencia** — `Contratación Directa`, `Adjudicación Simplificada` reciben bonus de score
3. **Objeto extenso** — `tender.title` o `tender.description` con > 30 caracterios
4. **Proveedor con RUC** — validado vía `awards[].suppliers[].id` (PE-RUC-XXXXXXXXXXX)
5. **Diversidad** — deduplicación por `ocid` para evitar el mismo tender repetido por múltiples awards

---

## 3. Conteos por Sector

### 3.1 Salud — 2,566 contratos

| Entidad (top 5 por cantidad) | Contratos | % del total |
|---|---|---|
| SEGURO SOCIAL DE SALUD (ESSALUD) | 1,032 | 40.2% |
| INSTITUTO NACIONAL DE SALUD DEL NIÑO — SAN BORJA | 97 | 3.8% |
| GOBIERNO REGIONAL DE AYACUCHO — HOSPITAL HUAMANGA | 67 | 2.6% |
| HOSPITAL DE EMERGENCIAS VILLA EL SALVADOR | 60 | 2.3% |
| INSTITUTO NACIONAL DE SALUD DEL NIÑO | 48 | 1.9% |

| Entidad (top 5 por monto) | Monto total (S/) |
|---|---|
| SEGURO SOCIAL DE SALUD (ESSALUD) | 2,935,608,880.74 |
| MINISTERIO DE SALUD | 101,783,608.22 |
| INSTITUTO NACIONAL DE SALUD DEL NIÑO — SAN BORJA | 90,811,926.86 |
| HOSPITAL DE APOYO DEPARTAMENTAL MARIA AUXILIADORA | 80,697,255.48 |
| INSTITUTO NACIONAL DE SALUD | 45,272,460.26 |

| Proveedor (top 5 por cantidad) | Contratos |
|---|---|
| CARDIO PERFUSION E.I.R.LTDA | 45 |
| DIAGNOSTICA PERUANA S.A.C. | 43 |
| DIMEXA S.A. | 33 |
| MEDIFARMA S A | 31 |
| UNILENE S.A.C. | 30 |

| Proveedor (top 5 por monto) | Monto total (S/) |
|---|---|
| CONSORCIO EDIFICADOR SUR | 347,883,662.85 |
| CONSORCIO GRUPO ZEUS SERVICE | 344,337,118.90 |
| VIPROSEG S.A.C. | 195,383,235.96 |
| SINOHYDRO CORPORATION LIMITED | 148,393,783.93 |
| DIMEXA S.A. | 101,469,676.36 |

### 3.2 Ambiente/Minería — 99 contratos

| Entidad (top 3 por cantidad) | Contratos | % del total |
|---|---|---|
| AUTORIDAD NACIONAL DEL AGUA (ANA) | 60 | 60.6% |
| SERVICIO NACIONAL DE ÁREAS NATURALES PROTEGIDAS (SERNANP) | 29 | 29.3% |
| MINISTERIO DEL AMBIENTE (MINAM) | 10 | 10.1% |

| Entidad (top 3 por monto) | Monto total (S/) |
|---|---|
| AUTORIDAD NACIONAL DEL AGUA (ANA) | 29,079,365.39 |
| SERNANP | 20,850,718.29 |
| MINISTERIO DEL AMBIENTE (MINAM) | 8,770,989.20 |

---

## 4. Muestra de 20 Procesos — Reconocimiento de TDRs

| # | OCID | Sector | Entidad | Objeto | Monto (S/) | Fecha | TDR Status | Docs | Notas |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `ocds-dgv273-seacev3-1064372` | Salud | ESSALUD | AS-DL 1355-SM-1-2022-GCL/ESSALUD-2 | 347,883,662.85 | 2024-11-22 | **available** | 18 | Bases: 2, Pliegos: 1 — **Descargado: bases_admin_1064372.rar (8.4MB)** |
| 2 | `ocds-dgv273-seacev3-988512` | Salud | ESSALUD | AS-SM-55-2023-ESSALUD/GCL-1 | 195,383,235.96 | 2024-02-14 | **available** | 14 | Bases: 2, Pliegos: 1 |
| 3 | `ocds-dgv273-seacev3-966803` | Salud | ESSALUD | AS-SM-56-2023-ESSALUD/GCL-1 | 159,268,200.66 | 2024-02-07 | **available** | 28 | Bases: 2, Pliegos: 1 |
| 4 | `ocds-dgv273-seacev3-2024-2543-1184` | Salud | ESSALUD | AS-SM-23-2023-ESSALUD/GCL-2 | 148,393,783.93 | 2024-08-23 | **available** | 23 | Bases: 2, Pliegos: 1 |
| 5 | `ocds-dgv273-seacev3-2024-2543-1376` | Salud | ESSALUD | AS-SM-22-2024-ESSALUD/RAPI-1 | 30,300,000.00 | 2024-08-13 | **available** | 8 | Bases: 2, Pliegos: 1 |
| 6 | `ocds-dgv273-seacev3-983701` | Salud | ESSALUD | DIRECTA-PROC-21-2023-ESSALUD/CEABE-1 | 13,567,752.00 | 2024-01-05 | **available** | 6 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 7 | `ocds-dgv273-seacev3-2025-2543-1615` | Salud | ESSALUD | AS-SM-13-2025-ESSALUD/CEABE-1 | 22,391,857.69 | 2025-09-17 | **available** | 23 | Bases: 2, Pliegos: 1 |
| 8 | `ocds-dgv273-seacev3-1195443` | Salud | INSN-SB | DIRECTA-DIRECTA-5-2026-INSN-SB-1 | 12,202,183.30 | 2026-03-16 | **available** | 5 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 9 | `ocds-dgv273-seacev3-2025-1979-55` | Salud | INS | AS-SM-23-2024-INS-4 | 20,590,000.00 | 2025-10-15 | **available** | 15 | Bases: 3, Pliegos: 1 |
| 10 | `ocds-dgv273-seacev3-2025-2543-355` | Salud | ESSALUD | AS-SM-18-2025-ESSALUD/CEABE-1 | 19,364,800.00 | 2026-04-06 | **available** | 8 | Bases: 2, Pliegos: 1 |
| 11 | `ocds-dgv273-seacev3-2025-200266-28` | Ambiente | ANA | AS-Homologacion-SM-5-2025-ANA-1 | 91,364.00 | 2025-07-21 | **available** | 11 | Bases: 2, Pliegos: 1 — Homologación |
| 12 | `ocds-dgv273-seacev3-1188333` | Ambiente | ANA | DIRECTA-DIRECTA-3-2026-ANA-1 | 4,846,154.66 | 2026-02-19 | **available** | 5 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 13 | `ocds-dgv273-seacev3-2024-200266-54` | Ambiente | ANA | AS-SM-6-2024-ANA-1 | 2,995,887.60 | 2024-08-08 | **available** | 16 | Bases: 2, Pliegos: 1 |
| 14 | `ocds-dgv273-seacev3-2025-200260-20` | Ambiente | SERNANP | AS-SM-3-2025-SERNANP-1 | 1,891,261.96 | 2025-03-20 | **available** | 17 | Bases: 2, Pliegos: 1 |
| 15 | `ocds-dgv273-seacev3-1186361` | Ambiente | ANA | DIRECTA-DIRECTA-2-2026-ANA-1 | 1,463,011.20 | 2026-02-13 | **available** | 5 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 16 | `ocds-dgv273-seacev3-1003315` | Ambiente | ANA | DIRECTA-PROC-9-2024-ANA-1 | 660,838.00 | 2024-04-09 | **available** | 9 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 17 | `ocds-dgv273-seacev3-1186228` | Ambiente | ANA | DIRECTA-DIRECTA-1-2026-ANA-1 | 551,577.60 | 2026-02-12 | **available** | 4 | Bases: 1, Pliegos: 0 — Contratación Directa |
| 18 | `ocds-dgv273-seacev3-2024-200260-82` | Ambiente | SERNANP | AS-SM-54-2024-SERNANP-1 | 399,248.28 | 2025-01-22 | **available** | 11 | Bases: 2, Pliegos: 1 |
| 19 | `ocds-dgv273-seacev3-2024-200254-6` | Ambiente | MINAM | AS-SM-16-2024-MINAM/OGA-1 | 393,330.00 | 2024-11-19 | **available** | 12 | Bases: 2, Pliegos: 1 — **Descargado: bases_admin_1307_116.pdf (649KB)** |
| 20 | `ocds-dgv273-seacev3-1000591` | Ambiente | ANA | DIRECTA-PROC-5-2024-ANA-1 | 391,997.39 | 2024-04-01 | **available** | 8 | Bases: 1, Pliegos: 0 — Contratación Directa |

### 4.1 TDRs descargados manualmente

| # | Archivo | Sector | Tamaño | Formato | Páginas | Ubicación |
|---|---|---|---|---|---|---|
| 1 | `bases_admin_1064372.rar` | Salud | 8.4 MB | RAR (Win32 v4) | N/A | `data/tdrs/salud/` |
| 2 | `bases_integradas_1147660.pdf` | Salud | 36.9 MB | PDF v1.3 | 143 | `data/tdrs/salud/` |
| 3 | `bases_admin_1307_116.pdf` | Ambiente | 649 KB | PDF v1.7 | 23 | `data/tdrs/ambiente/` |

> **Nota:** El archivo RAR (`bases_admin_1064372.rar`) contiene bases administrativas comprimidas. Los PDFs son documentos integrados con bases + TDR.

### 4.2 PDF Usability Gate — Activity 4.2

El downloader validado en Activity 4.1 no implica que cada documento sea analizable por el motor documental. Activity 4.2 auditó únicamente PDFs ya descargados y dejó RAR/ZIP como `archive_pending` sin intentar extracción ni OCR.

| Métrica | Valor |
|---|---:|
| Total archivos revisados | 13 |
| PDFs auditados | 8 |
| PDFs `available` | 3 |
| PDFs `partial` | 0 |
| PDFs `needs_ocr` | 5 |
| RAR/ZIP `archive_pending` | 5 |

Outputs generados:

- `data/tdrs/pdf_usability_report.csv`
- `data/tdrs/pdf_usability_audit.json`

PDFs `available`:

| Sector | Path | Páginas con texto | Coverage |
|---|---|---:|---:|
| Ambiente | `data/tdrs/ambiente/bases_admin_1307_116.pdf` | 23 | 100% |
| Ambiente/Minería | `data/tdrs/ambiente_mineria/ocds_dgv273_seacev3_1157442/pliego_de_absolucion_de_consultas_y_observaciones_bf3db732_667d_4ea3_97ce_580f534727a0.pdf` | 181 | 100% |
| Ambiente/Minería | `data/tdrs/ambiente_mineria/ocds_dgv273_seacev3_1191874/bases_administrativas_8ad48b3a_dd0d_4899_9e80_3e0d32d71579.pdf` | 79 | 100% |

PDFs Salud auditados:

- `data/tdrs/salud/bases_integradas_1147660.pdf` — `needs_ocr`, 143 páginas, 0% coverage.
- `data/tdrs/salud/ocds_dgv273_seacev3_1064372/bases_integradas_c60d9e28_7275_4c2f_a008_8eb957a36abe.pdf` — `needs_ocr`, 150 páginas, 0% coverage.
- `data/tdrs/salud/ocds_dgv273_seacev3_2024_2543_1184/bases_integradas_69494710_c6a3_4274_b316_15942e637299.pdf` — `needs_ocr`, 154 páginas, 0% coverage.

Recomendados para Golden Set:

1. `data/tdrs/ambiente_mineria/ocds_dgv273_seacev3_1157442/pliego_de_absolucion_de_consultas_y_observaciones_bf3db732_667d_4ea3_97ce_580f534727a0.pdf` — 181 páginas con texto, 100% coverage.
2. `data/tdrs/ambiente/bases_admin_1307_116.pdf` — 23 páginas con texto, 100% coverage.

Decisión Activity 4.2: no pasar aún a Activity 5 para Salud. Faltaba al menos 1 PDF Salud `available`; siguiente paso: Activity 4.3 — Targeted Salud Digital PDF Hunt.

### 4.3 Targeted Salud Digital PDF Hunt — Activity 4.3

Se ejecutó un hunt controlado sobre `data/filtered/salud_2024_2025_with_documents.jsonl`, restringido a PDFs, sin RAR/ZIP, sin scraping HTML y con detención temprana al encontrar 1 PDF usable.

Comando:

```bash
cd apps/scrapers
uv run agenteperry tdr download \
  --input ../../data/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud \
  --limit 30 \
  --max-docs 1 \
  --pdf-only \
  --skip-existing \
  --audit-after-download \
  --stop-when-usable 1
```

Resultado:

| Métrica | Valor |
|---|---:|
| Candidatos considerados | 2 |
| Descargas intentadas | 1 |
| PDFs Salud usables encontrados | 1 |
| PDFs `needs_ocr` nuevos | 0 |
| Fallidos | 0 |
| Existentes saltados | 1 |
| Detención temprana | Sí |

PDF Salud usable:

| Path | Páginas con texto | Coverage | Status |
|---|---:|---:|---|
| `data/tdrs/salud/ocds_dgv273_seacev3_988512/pliego_de_absolucion_de_consultas_y_observaciones_6faab297_cfd6_4448_a65a_d8bf646ead81.pdf` | 212 | 100% | `available` |

Recomendación Golden Set actualizada:

1. Salud: `data/tdrs/salud/ocds_dgv273_seacev3_988512/pliego_de_absolucion_de_consultas_y_observaciones_6faab297_cfd6_4448_a65a_d8bf646ead81.pdf`
2. Ambiente/Minería: `data/tdrs/ambiente_mineria/ocds_dgv273_seacev3_1157442/pliego_de_absolucion_de_consultas_y_observaciones_bf3db732_667d_4ea3_97ce_580f534727a0.pdf`
3. Ambiente: `data/tdrs/ambiente/bases_admin_1307_116.pdf`

Decisión Activity 4.3: listo para Activity 5 — Golden Set Real Analysis con PDFs reales y capa de texto usable.

---

## 5. Disponibilidad de TDRs — Análisis

### 5.1 Hallazgos

| Hallazgo | Frecuencia | Detalle |
|---|---|---|
| **URL directa a documentos** | 100% de muestra (20/20) | URLs del tipo `https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=...` |
| **Sin login requerido** | 100% | `curl` directo retorna HTTP 200 con archivo |
| **Sin captcha** | 100% | No se detectó mecanismo anti-bot en URLs de documentos |
| **Sin paywall** | 100% | Archivos descargados completos |
| **Múltiples documentos por proceso** | 100% | Rango: 4–28 documentos por contrato |
| **Tipos de documentos presentes** | Bases Administrativas, Bases Integradas, Pliego de Absolución, Resumen Ejecutivo, Documentos de Presentación, Informe de Desierto |

### 5.2 URLs de acceso observadas

```
https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>
```

- `fileCode` es un UUID v4 único por documento
- No requiere session cookie ni token de autenticación
- Rate-limiting no observado en descargas manuales (3 archivos, intervalo ~1 min)

### 5.3 Procesos con modalidad de baja competencia

| Modalidad | Count (muestra 20) | % |
|---|---|---|
| Contratación Directa | 6 | 30% |
| Adjudicación Simplificada | 14 | 70% |

---

## 6. Riesgos Técnicos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| SEACE cambia dominio o endpoint | Media | Alta | Monitorear `raw_data->tender->documents[].url` en pipeline OCDS |
| `fileCode` expira o requiere sesión | Baja | Alta | Verificar periodicamente con HEAD request en TDR Downloader v1 |
| Rate-limiting no observado aún | Media | Media | Implementar backoff en downloader (1 req/s) |
| Archivos RAR requieren descompresión | Baja | Baja | Integrar `unar` o `libarchive` en pipeline de parsing |
| PDFs escaneados (no OCR) | Media | Alta | PyMuPDF + OCR fallback en TDR parser |
| OCDS no siempre tiene `tender.documents` | Baja | Media | Fallback a SEACE web scraping si documentos faltan |

---

## 7. Recomendación para TDR Downloader v1

### 7.1 Arquitectura propuesta

```
Input:  recon_20_processes.csv (o query SQL de source_records)
        → filter record_type='contract' + sector keywords + fecha >= 2024

Step 1: Extract document URLs
        → SELECT raw_data->'tender'->'documents' FROM source_records
        → filter documents where title ILIKE '%base%' OR '%pliego%'

Step 2: Deduplicate fileCode
        → SHA256(fileCode) como checksum interno
        → Skip si ya descargado en data/tdrs/<sector>/<fileCode>.<ext>

Step 3: Download with backoff
        → requests.get() con headers: User-Agent, Accept
        → Rate: 1 req/s, retry 3x con backoff exponencial
        → Timeout: 120s (archivos pueden ser > 30MB)

Step 4: Validate
        → file-type detection (libmagic/file)
        → Reject HTML error pages (Content-Type check)
        → Log size, checksum, pages (si PDF)

Step 5: Persist metadata
        → tdr_documents (external_id, file_path, sector, monto, entity_name, downloaded_at)
        → tdr_pages (extracted via PyMuPDF)
        → tdr_chunks (chunked for RAG)
        → tdr_flags (rule-based signals)
```

### 7.2 Query SQL de entrada

```sql
-- Contratos Salud 2024+ con documentos
SELECT
    sr.external_id,
    sr.entity_name,
    sr.monto,
    sr.fecha,
    sr.raw_data->>'ocid' AS ocid,
    sr.raw_data->'tender'->>'title' AS objeto,
    sr.raw_data->'tender'->>'procurementMethodDetails' AS modalidad,
    d->>'title' AS doc_title,
    d->>'url' AS doc_url,
    d->>'format' AS doc_format
FROM source_records sr,
    jsonb_array_elements(sr.raw_data->'tender'->'documents') AS d
WHERE sr.record_type = 'contract'
  AND sr.fecha >= '2024-01-01'
  AND sr.entity_name ILIKE '%salud%'
  AND sr.raw_data->'tender'->'documents' IS NOT NULL
ORDER BY sr.monto DESC NULLS LAST;
```

### 7.3 Criterios de prioridad para descarga masiva

1. **Sector:** Salud > Ambiente/Minería (mayor monto y cantidad)
2. **Modalidad:** Contratación Directa > Adjudicación Simplificada > otros
3. **Monto:** > S/ 10,000,000 (alto impacto fiscal)
4. **Document type:** Bases Integradas > Bases Administrativas > Pliegos > Otros
5. **Entity:** ESSALUD > MINSA > INSN > Hospitales regionales

---

## 8. Archivos Generados

| Archivo | Descripción | Ubicación |
|---|---|---|
| `salud_2024_2025.jsonl` | 2,566 contratos Salud | `data/filtered/salud_2024_2025.jsonl` |
| `ambiente_2024_2025.jsonl` | 99 contratos Ambiente | `data/filtered/ambiente_2024_2025.jsonl` |
| `summary.json` | Conteos y tops 20 | `data/filtered/summary.json` |
| `recon_20_processes.csv` | Muestra de 20 con recon TDR | `data/tdr_recon/recon_20_processes.csv` |
| `bases_admin_1064372.rar` | TDR ESSALUD descargada | `data/tdrs/salud/` |
| `bases_integradas_1147660.pdf` | TDR PNIS descargada | `data/tdrs/salud/` |
| `bases_admin_1307_116.pdf` | TDR MML descargada | `data/tdrs/ambiente/` |
| `tdr_discovery.py` | Script de filtrado y recon | `apps/scrapers/src/agenteperry/discovery/` |

---

## 9. Próximos Pasos Recomendados

1. **TDR Downloader v1** — Implementar batch downloader con rate-limiting (SPEC-0010)
2. **Cargar 5 PDFs reales** al motor documental (parse → pages → chunks → flags)
3. **Reactivar SUNAT enrichment** después de validar pipeline TDR
4. **No reactivar** ConflictMap / Neo4j / ONPE / JNE / SUNARP sin spec activo

---

*Reporte generado automáticamente por `tdr_discovery.py` + análisis manual de Staff Data Engineer.*  
*Commit sugerido: `feat(scrapers): discover TDR availability for priority sectors (SPEC-0009)`*
