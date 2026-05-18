# Data Inventory — AgentePerry

> **Última actualización:** 2026-05-17
> **Estado:** En desarrollo — SPEC-0010 TDR Downloader + Activity 4.2 PDF Usability Gate completados

---

## 1. Resumen de directorios

```
data/
├── README.md              ← política: qué se commitea vs qué se ignora
├── FILTERED.md            ← este archivo
├── filtered/              ← contratos OCDS filtrados por sector
├── derived/ocds/          ← contratos OCDS con raw_data + parsed_data
├── raw/ocds/              ← dumps OCDS originales comprimidos
├── tdrs/                  ← documentos descargados (PDF/RAR/ZIP)
├── tdr_recon/             ← csv de reconocimiento de 20 procesos
├── golden_set/            ← corpus de evaluación con PDFs + metadata
└── manual_tdrs/           ← ejemplo de upload manual con metadata CSV
```

---

## 2. Directorio `data/filtered/`

**Propósito:** Contratos OCDS de SEACE filtrados por sector (Salud / Ambiente) y rango de fechas. Generados por `agenteperry discovery tdr_discovery.py`.

| Archivo | Registros | Descripción |
|---|---|---|
| `salud_2024_2025.jsonl` | 2,566 | Contratos Salud 2024–2025, sin `tender.documents[]` |
| `ambiente_2024_2025.jsonl` | 99 | Contratos Ambiente/Minería 2024–2025, sin `tender.documents[]` |
| `salud_2024_2025_with_documents.jsonl` | 2,566 | Contratos Salud enriquecidos con `tender.documents[]` desde `derived/ocds/contracts_2026.jsonl` |
| `ambiente_2024_2025_with_documents.jsonl` | 99 | Contratos Ambiente enriquecidos con `tender.documents[]` |
| `summary.json` | — | Agregados: total contratos, monto, top entidades por sector |

**Schema de cada línea JSONL (`salud_2024_2025.jsonl`):**

```json
{
  "ocid": "ocds-dgv273-seacev3-1064372",
  "external_id": "ocds-dgv273-seacev3-1064372:1064372-1601907",
  "entity": "SEGURO SOCIAL DE  SALUD",
  "entity_ruc": "20131257750",
  "objeto": "AS-DL 1355-SM-1-2022-GCL/ESSALUD-2",
  "monto": 347883662.85,
  "fecha": "2024-11-22",
  "modalidad": "Adjudicación Simplificada-Decreto Legislativo N° 1355",
  "proveedor_nombre": "CONSORCIO EDIFICADOR SUR",
  "proveedor_ruc": "1601907",
  "source_url": null,
  "parsed_data": {
    "ocid": "ocds-dgv273-seacev3-1064372",
    "award_id": "1064372-1601907",
    "tender_id": "1064372",
    "award_status": null,
    "procedure_type": "Adjudicación Simplificada-Decreto Legislativo N° 1355",
    "contracts_count": 1
  }
}
```

**Schema enriquecido (`salud_2024_2025_with_documents.jsonl`) — agrega:**

```json
{
  "documents": [
    {
      "id": "...",
      "title": "Bases Integradas",
      "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=...",
      "format": "pdf",
      "documentType": "biddingDocuments",
      "datePublished": "2024-11-15",
      "dateModified": "2024-11-15"
    }
  ]
}
```

**Origen:** `apps/scrapers/src/agenteperry/discovery/tdr_discovery.py`

---

## 3. Directorio `data/derived/ocds/`

**Propósito:** Contratos OCDS completos con `raw_data` (JSON OCDS completo) y `parsed_data` enriquecido. Usado como fuente para enriquecer los JSONL filtrados con `tender.documents[]`.

| Archivo | Registros | Tamaño | Descripción |
|---|---|---|---|
| `contracts_2026.jsonl` | 72,399 | ~1 GB | Contratos OCDS 2026 con `raw_data`, `parsed_data`, `fecha`, `monto`, `entity_name` |
| `graph_2026.jsonl` | — | ~61 MB | Entidades + relaciones (GANO_CONTRATO, COMPRO_A) |

**Schema de `contracts_2026.jsonl`:**

```json
{
  "checksum": "44d18138fad149edc403b84599c60da8345402f2863353924044eceffd7df68d",
  "content_type": "application/ocds+json",
  "entity_name": "MUNICIPALIDAD PROVINCIAL DE PALPA",
  "entity_ruc": null,
  "evidence_quote": "CONSORCIO PALPA gano contrato con MUNICIPALIDAD PROVINCIAL DE PALPA por 84099.67.",
  "external_id": "ocds-dgv273-seacev3-1163548:1163548-1753032",
  "fecha": "2025-12-18",
  "fetched_at": "2026-05-16T05:14:09.080288+00:00",
  "monto": 84099.67,
  "page_number": null,
  "parsed_data": {
    "ocid": "ocds-dgv273-seacev3-1163548",
    "award_id": "1163548-1753032",
    "tender_id": "1163548",
    "award_status": null,
    "procedure_type": "Concurso Público Abreviado",
    "contracts_count": 1
  },
  "period_year": 2025,
  "raw_data": {
    "ocid": "ocds-dgv273-seacev3-1163548",
    "id": "ocds-dgv273-seacev3-1163548-...",
    "tender": {
      "id": "1163548",
      "title": "CONTRATACIÓN DE LA SUPERVISIÓN...",
      "documents": [
        {
          "id": "...",
          "title": "Bases Administrativas",
          "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=...",
          "format": "rar",
          "documentType": "biddingDocuments"
        }
      ]
    },
    "awards": [...],
    "contracts": [...]
  }
}
```

**Pipeline:**
1. `agenteperry sources collect ocds_peru --out data/raw/ocds/2026.jsonl.gz` → `data/raw/ocds/2026.jsonl.gz`
2. `agenteperry sources pipeline ocds_peru --input data/raw/ocds/2026.jsonl.gz` → `data/derived/ocds/contracts_2026.jsonl` + `graph_2026.jsonl`

---

## 4. Directorio `data/raw/ocds/`

**Propósito:** Dumps OCDS originales tal como se descargaron.

| Archivo | Tamaño | Descripción |
|---|---|---|
| `2026.jsonl.gz` | ~73 MB | Dump OCDS 2026 comprimido (gzip).中的一行 = un registro OCDS |

**No se usa directamente en el MVP.** Fue el input inicial del pipeline OCDS.

---

## 5. Directorio `data/tdrs/`

**Propósito:** Documentos descargados desde SEACE (bases, pliegos, TDRs) organizados por sector. Generados por `agenteperry tdr download`.

### 5.1 Archivos de auditoría

| Archivo | Descripción |
|---|---|
| `pdf_usability_report.csv` | Auditoría de PDFs: coverage de texto digital por archivo |
| `pdf_usability_audit.json` | Resumen agregado de la auditoría |
| `salud/audit.json` | Métricas de descarga Salud |
| `ambiente_mineria/audit.json` | Métricas de descarga Ambiente/Minería |

**Schema de `pdf_usability_report.csv`:**

```
path,sector,extension,total_pages,pages_with_text,pages_needs_ocr,coverage_pct,tdr_status,is_usable,notes
```

**Status posibles:**
- `available` — coverage ≥ 20%, texto digital suficiente
- `partial` — 5% ≤ coverage < 20%
- `needs_ocr` — coverage < 5% o archivo corrupto
- `archive_pending` — RAR/ZIP pendientes de extracción

### 5.2 Estructura de subdirectorios

```
data/tdrs/
├── pdf_usability_report.csv
├── pdf_usability_audit.json
├── ambiente/
│   └── bases_admin_1307_116.pdf          ← descargado manualmente (MML)
├── ambiente_mineria/
│   ├── audit.json
│   └── ocds_dgv273_seacev3_1157442/
│   │   └── pliego_de_absolucion_de_consultas...pdf  ← 181 páginas, 100% text, USABLE
│   └── ocds_dgv273_seacev3_1188333/
│       └── bases_administrativas...pdf              ← 79 páginas, 100% text, USABLE
└── salud/
    ├── audit.json
    ├── bases_admin_1064372.rar          ← descargado manualmente (ESSALUD)
    ├── bases_integradas_1147660.pdf     ← 143p, 0% text, needs_ocr
    ├── ocds_dgv273_seacev3_1064372/
    │   └── bases_integradas...pdf       ← 150p, 0% text, needs_ocr
    └── ocds_dgv273_seacev3_2024_2543-1184/
        └── bases_integradas...pdf       ← 154p, 0% text, needs_ocr
```

### 5.3 Estado actual de PDFs (Activity 4.2)

| Status | Count |注 |
|---|---|---|
| `available` | 3 | Texts digital usable for parser |
| `partial` | 0 | — |
| `needs_ocr` | 5 | Require OCR before parsing |
| `archive_pending` | 5 | RAR/ZIP pending extraction |

### 5.4 Candidatos recomendados para Golden Set

1. **`ambiente_mineria/ocds_dgv273_seacev3_1157442/pliego...pdf`** — 181 páginas, 100% text, SERNANP
2. **`ambiente/bases_admin_1307_116.pdf`** — 23 páginas, 100% text, MML

---

## 6. Directorio `data/tdr_recon/`

**Propósito:** CSV de reconocimiento que vincula 20 contratos muestreados con URLs SEACE y estado de TDR.

| Archivo | Registros | Descripción |
|---|---|---|
| `recon_20_processes.csv` | 20 | Muestra de 20 contratos priorizados (10 Salud + 10 Ambiente) con estado de TDR |

**Schema:**

```csv
ocid,sector,entidad,objeto,monto,fecha,proveedor_nombre,proveedor_ruc,
source_url,seace_url_candidate,tdr_status,tdr_url,tdr_path,access_method,notes
```

**Generado por:** `apps/scrapers/src/agenteperry/discovery/tdr_discovery.py` → función `pick_sample()` y `write_csv()`

---

## 7. Directorio `data/golden_set/`

**Propósito:** Corpus de evaluación para validar el motor documental. Contiene PDFs reales con metadata que define flags esperados y preguntas de evaluación.

| Archivo/Dir | Descripción |
|---|---|
| `README.md` | Documentación del workflow de evaluación |
| `metadata.example.csv` | Schema de ejemplo (tracked) |
| `metadata.csv` | Metadata real de los PDFs seleccionados (gitignored) |
| `pdfs/` | PDFs reales del corpus (gitignored) |
| `outputs/` | Resultados de análisis (gitignored) |

**Schema de `metadata.csv` (gitignored):**

```csv
id,file_name,sector,entity_name,procedure_code,source_url,file_url,
document_type,pages,reason_selected,expected_flags,question
```

**Proceso de evaluación:**
1. Seleccionar PDFs `available` (coverage ≥ 20%)
2. Llenar `metadata.csv` con `expected_flags` y `question`
3. Correr pipeline: `parse → chunk → flags`
4. Comparar flags detectados vs `expected_flags`
5. Guardar en `outputs/<id>.analysis.json`

---

## 8. Directorio `data/manual_tdrs/`

**Propósito:** Ejemplo de workflow de upload manual. демонстрирует cómo se registraría un TDR cargado manualmente sin passar por el downloader.

| Archivo | Descripción |
|---|---|
| `metadata.csv` | 2 registros de ejemplo con paths locales |
| `dummy.pdf` | Placeholder vacío |

**Schema de `metadata.csv`:**

```csv
external_id,title,entity_name,source_url,file_url,procedure_code,
sector,region,district,publication_date,estimated_value,local_path
```

---

## 9. Pipeline de datos — Vista General

```
SEACE (OCDS JSON API)
  └── data/raw/ocds/2026.jsonl.gz            ← descarga OCDS bulk

data/raw/ocds/2026.jsonl.gz
  └── agenteperry sources pipeline ocds_peru
        ├── data/derived/ocds/contracts_2026.jsonl   (72,399 contracts)
        └── data/derived/ocds/graph_2026.jsonl        (entities + relationships)

data/derived/ocds/contracts_2026.jsonl
  └── agenteperry discovery tdr_discovery.py
        ├── data/filtered/salud_2024_2025.jsonl         (2,566)
        ├── data/filtered/ambiente_2024_2025.jsonl      (99)
        ├── data/tdr_recon/recon_20_processes.csv      (20)
        └── data/filtered/summary.json

data/derived/ocds/contracts_2026.jsonl + data/filtered/*_2024_2025.jsonl
  └── /tmp/opencode/enrich_tdr_filtered_with_documents.py
        ├── data/filtered/salud_2024_2025_with_documents.jsonl
        └── data/filtered/ambiente_2024_2025_with_documents.jsonl

data/filtered/*_2024_2025_with_documents.jsonl
  └── agenteperry tdr download --input ... --sector salud --limit 5
        └── data/tdrs/
              ├── salud/
              └── ambiente_mineria/
                    ├── audit.json
                    └── pdf_usability_report.csv / audit.json

data/tdrs/ (solo PDFs usables)
  └── agenteperry tdr parse → tdr chunk → tdr flags
        └── evaluación con golden_set/metadata.csv
```

---

## 10. Glosario de formatos

| Formato | Descripción | Herramienta de parsing |
|---|---|---|
| `.jsonl` | JSON Lines — un objeto JSON por línea | `json.loads()` por línea |
| `.jsonl.gz` | JSONL comprimido con gzip | `gzip.open()` |
| `.csv` | CSV con headers en primera fila | `csv.DictReader` |
| `.pdf` | PDF con texto digital o escaneado | PyMuPDF (`fitz`) |
| `.rar` / `.zip` | Archivo comprimido | `rarfile` / Python `zipfile` |

---

## 11. Criterios para pasar a la siguiente actividad

| Activity | Criterio de entrada |
|---|---|
| **4.3** Targeted Salud Digital PDF Hunt | Necesita ≥1 PDF Salud `available` |
| **5** Golden Set Real Analysis | ≥1 PDF available por sector |
| **SPEC-0002** TDR PDF Parser | Documento en disco + metadata en `tdr_documents` |

---

## 12. Issues abiertos de data

| Issue | Descripción | Bloquea |
|---|---|---|
| Salud PDF 0% text coverage | Los 3 PDFs Salud necesitan OCR | Activity 4.3 / Activity 5 |
| 5 RAR/ZIP sin extraer | `archive_pending` en audit | SPEC-0002 parser |
| `tdr_documents` sin poblar | No hay `DATABASE_URL` en dev local | Registro de metadata |

---

## 13. Conventions

- **Paths en CSVs/JSONs:** relativos desde `data/` o absolutos completos (evitar paths ambiguos)
- **Fechas:** ISO 8601 (`YYYY-MM-DD`)
- **Montos:** `numeric` en PEN (soles peruanos), sin símbolo
- **OCID:** formato `ocds-dgv273-seacev3-<tender_id>`
- **Sector:** `salud` | `ambiente_mineria`
- **No commitear:** archivos binarios, JSONL reales, CSVs reales, PDFs, credenciales