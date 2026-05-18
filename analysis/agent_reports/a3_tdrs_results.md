# Agente A3 — tdrs + tdr_recon + manual_tdrs + results

## 1. Inventario

| Archivo | Bytes | Descripción |
|---------|-------|-------------|
| tdrs/pdf_usability_audit.json | 2,362 | Metadata de usabilidad: 4 usables, 5 needs_ocr, 5 archives pendientes |
| tdrs/pdf_usability_report.csv | 2,903 | Cobertura de extracción de texto por PDF |
| tdrs/ambiente/*.pdf | ~649 KB | 1 PDF, 23 páginas, 100% cobertura texto |
| tdrs/ambiente_mineria/**/ | múltiple | 5 subdirs con ocids: 1 pliego (181p), 3 bases (79-150p), 2 archives (ZIP) |
| tdrs/salud/**/ | múltiple | 7 subdirs con ocids: 1 pliego (212p, 100%), 4 bases (needs OCR), 3 archives (RAR) |
| tdr_recon/recon_20_processes.csv | 7,885 | 20 procesos reconciliados manualmente con OCDS |
| manual_tdrs/metadata.csv | 457 | 2 registros de entrada manual (Sedapal, Callao) |
| manual_tdrs/dummy.pdf | pequeño | Archivo dummy — no procesado |
| results/demo_case.md | ~8.5 KB | Análisis real de contrato ESSALUD S/ 195.3M vigilancia |
| results/ocds_dgv273_seacev3_1157442/dossier.json | 5,509 | 4 flags, score 40, RIESGO MEDIO — ANA S/ 2.99M |
| results/ocds_dgv273_seacev3_1157442/flags.json | ~1.5 KB | 4 flags con evidence_quote |
| results/ocds_dgv273_seacev3_1157442/pages.json | grande | 181 páginas con text_content |
| results/ocds_dgv273_seacev3_1157442/chunks.json | grande | 365 chunks con índices de página y carácter |
| results/ocds_dgv273_seacev3_1157442/dossier.md | ~2.5 KB | Resumen legible del dossier.json |
| results/ocds_dgv273_seacev3_988512/dossier.json | similar | 6 flags, score 60, RIESGO ALTO — ESSALUD S/ 195.38M |
| results/ocds_dgv273_seacev3_988512/flags.json | similar | 3 OBSOLETE_PHYSICAL_FORMAT + 3 LOW_TRACEABILITY_OUTPUT |
| results/ocds_dgv273_seacev3_2024_200254_6/dossier.json | similar | 2 flags, score 20, RIESGO BAJO — MINAM S/ 393K |
| results/ocds_dgv273_seacev3_2024_200254_6/flags.json | similar | 2 LOW_TRACEABILITY_OUTPUT |

---

## 2. Schemas reales

### results/dossier.json — Estructura completa (ocds_dgv273_seacev3_1157442)

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 timestamp",
  "document": {
    "ocid": "ocds-dgv273-seacev3-1157442",
    "sector": "ambiente_mineria",
    "entity_name": "AUTORIDAD NACIONAL DEL AGUA (ANA)",
    "procedure_code": "AS-SM-6-2024-ANA-1",
    "monto": 2995887.6,
    "storage_path": "local path to PDF",
    "checksum": "sha256:...",
    "parse_status": "parsed",
    "total_pages": 181,
    "total_chunks": 365,
    "coverage_pct": 100.0
  },
  "risk_summary": {
    "total_flags": 4,
    "high_flags": 0,
    "medium_flags": 0,
    "low_flags": 4,
    "total_score": 40,
    "risk_level": "MEDIO"
  },
  "flags": [
    {
      "flag_code": "LOW_TRACEABILITY_OUTPUT",
      "flag_name": "Entregable de baja trazabilidad",
      "severity": "LOW",
      "score_contribution": 10,
      "page_number": 4,
      "evidence_quote": "..extracto textual del PDF..",
      "explanation": "El entregable descrito parece poco estructurado...",
      "detection_method": "rule",
      "rule_id": "TDR-R005"
    }
  ],
  "questions_for_authority": ["¿Como se verificara...?"],
  "transparency_request": "Solicito copia digital del expediente...",
  "disclaimer": "Este dossier es un analisis preventivo automatico..."
}
```

**El `risk_summary.total_score` está en `dossier["risk_summary"]["total_score"]` — NO anidado más profundo.**

### results/flags.json — Estructura completa

```json
{
  "source_pages": "../../data/results/ocds_dgv273_seacev3_1157442/pages.json",
  "ocid": "ocds-dgv273-seacev3-1157442",
  "flags": [
    {
      "tdr_id": "ocds-dgv273-seacev3-1157442",
      "chunk_id": null,
      "flag_code": "LOW_TRACEABILITY_OUTPUT",
      "flag_name": "Entregable de baja trazabilidad",
      "severity": "LOW",
      "score_contribution": 10,
      "evidence_quote": "..cita textual del PDF..",
      "page_number": 4,
      "explanation": "El entregable descrito parece poco estructurado...",
      "detection_method": "rule",
      "rule_id": "TDR-R005"
    }
  ]
}
```

### Comparación entre los 3 dossiers

| Propiedad | 1157442 | 988512 | 2024_200254_6 |
|-----------|---------|--------|---------------|
| ocid | ocds-dgv273-seacev3-1157442 | ocds-dgv273-seacev3-988512 | ocds-dgv273-seacev3-2024-200254-6 |
| sector | ambiente_mineria | salud | ambiente |
| entity_name | ANA | ESSALUD | MINAM |
| monto | S/ 2.99M | S/ 195.38M | S/ 393K |
| total_pages | 181 | 212 | 23 |
| total_chunks | 365 | 445 | 49 |
| total_flags | 4 | 6 | 2 |
| HIGH flags | 0 | 0 | 0 |
| MEDIUM flags | 0 | 0 | 0 |
| LOW flags | 4 | 6 | 2 |
| total_score | 40 | 60 | 20 |
| risk_level | MEDIO | ALTO | BAJO |
| Tipos de flags | LOW_TRACEABILITY(3) + OBSOLETE(1) | OBSOLETE(3) + LOW_TRACEABILITY(3) | LOW_TRACEABILITY(2) |

**Estructura idéntica en los 3. Scores: 20, 40, 60 (múltiplos de 20 = 2×10 por flag LOW).**

### tdr_recon/recon_20_processes.csv — Columnas y primeras filas

Columnas: `ocid, sector, entidad, objeto, monto, fecha, proveedor_nombre, proveedor_ruc, source_url, seace_url_candidate, tdr_status, tdr_url, tdr_path, access_method, notes`

Ejemplo fila 1:
```
ocds-dgv273-seacev3-1064372, salud, SEGURO SOCIAL DE SALUD,
AS-DL 1355-SM-1-2022-GCL/ESSALUD-2, 347883662.85, 2024-11-22,
CONSORCIO EDIFICADOR SUR, 1601907, ...
```

Ejemplo fila 2:
```
ocds-dgv273-seacev3-988512, salud, SEGURO SOCIAL DE SALUD,
AS-SM-55-2023-ESSALUD/GCL-1, 195383235.96, 2024-02-14,
VIPROSEG SOCIEDAD ANONIMA CERRADA, 20605681281, ...
```

### manual_tdrs/metadata.csv — Columnas

Columnas: `external_id, title, entity_name, source_url, file_url, procedure_code, sector, region, district, publication_date, estimated_value, local_path`

Datos:
- TDR-001: Sedapal, Mantenimiento Redes Agua, sector Vivienda, Lima, S/ 50,000
- TDR-002: Gobierno Regional Callao, Adquisicion Laptops, Educacion, Callao, S/ 120,000

**NO tiene ocid — no conecta con OCDS ni dossiers.**

### pdf_usability_report.csv — Columnas

Columnas: `path, sector, extension, total_pages, pages_with_text, pages_needs_ocr, coverage_pct, tdr_status, is_usable, notes`

Ejemplo usable: `tdrs/ambiente/bases_admin_1307_116.pdf, ambiente, pdf, 23, 23, 0, 100.0, available, True`
Ejemplo needs_ocr: `tdrs/salud/.../bases_integradas.pdf, salud, pdf, 150, 0, 150, 0.0, available, False`

---

## 3. Join con OCDS

### Clave de cruce

| Origen | Campo | Ejemplo |
|--------|-------|---------|
| dossier.json | `document.ocid` | "ocds-dgv273-seacev3-1157442" |
| flags.json | `ocid` | "ocds-dgv273-seacev3-1157442" |
| recon_20_processes.csv | primera columna `ocid` | "ocds-dgv273-seacev3-988512" |
| ocds/records.jsonl | `parsed_data.ocid` | "ocds-dgv273-seacev3-1163548" |
| filtered/*.jsonl | campo `ocid` | "ocds-dgv273-seacev3-1064372" |

**Estrategia: exact string match de ocid.** El external_id de OCDS tiene formato `{ocid}:{award_id}` — para cruzar dossier↔contract: `external_id.split(":")[0] == dossier.ocid`.

### Cobertura del join

- 3 dossiers procesados con ocid completo
- 20 procesos en recon_20_processes.csv con ocid → joinables con OCDS
- manual_tdrs/metadata.csv: NO tiene ocid → no joinable directamente

---

## 4. Tipos de flags encontrados

### Flags únicos en los 3 dossiers

1. **`LOW_TRACEABILITY_OUTPUT`** (rule TDR-R005)
   - "Entregable de baja trazabilidad"
   - 8 instancias totales (3+3+2)
   - score_contribution: 10 por instancia
   - detection_method: "rule"

2. **`OBSOLETE_PHYSICAL_FORMAT`** (rule TDR-R002)
   - "Formato físico u obsoleto"
   - 4 instancias (1+3+0)
   - score_contribution: 10 por instancia
   - detection_method: "rule"

**Total tipos únicos: 2. Todos LOW severity.**

### Propiedades de cada flag

- `flag_code`: enum (2 valores conocidos)
- `flag_name`: string legible
- `severity`: LOW/MEDIUM/HIGH (solo LOW en muestra)
- `score_contribution`: int (10 × severity LOW)
- `page_number`: int (página del PDF origen)
- `evidence_quote`: extracto textual del PDF (~50-150 chars)
- `explanation`: plantilla automática
- `detection_method`: "rule" (no "ai" en muestra)
- `rule_id`: "TDR-R005" / "TDR-R002"
- `chunk_id`: null en todos los observados

### Referencias a personas en flags

**NO hay.** Los flags actuales analizan especificaciones técnicas y formatos de entregables. Nombres de personas/comités no aparecen en evidence_quote.

### Evidence quotes — tipo de contenido

Son **extractos textuales de PDFs**, no campos OCDS. Ejemplo:
```
"mo, se precisa que el tipo de cambio a considerar en la oferta económica será 
al tipo de cambio venta SBS del día de la presentación de ofertas..."
```

---

## 5. Anomalías / Hallazgos

1. **demo_case.md es dato real, no ficticio.** Análisis del contrato ESSALUD AS-SM-55-2023-ESSALUD/GCL-1 (S/ 195.3M vigilancia, 3 años). Identifica 5 empresas participantes y señal de firma presencial en Jr. Domingo Cueto N° 120, Jesús María, Lima.

2. **dossier.md duplica dossier.json** en formato legible. No aporta info nueva. Ignorar en modelo de grafo.

3. **PDFs sin procesar (5 con needs_ocr):** Son imágenes escaneadas sin texto digital extraíble. El pipeline actual (rule-based sobre texto) NO puede analizarlos.

4. **Archives pendientes (5 ZIP/RAR):** No han sido descomprimidos ni procesados.

5. **manual_tdrs/metadata.csv desconectado de OCDS.** Sin ocid → no se puede vincular al grafo automáticamente. Probablemente datos de entrada manual para testing.

6. **recon_20_processes.csv tiene proveedor_ruc incompleto.** Fila 1: "1601907" (7 dígitos) — mismo problema que ocds/records.jsonl.

7. **Riesgo calculado como count × 10.** No hay flags HIGH/MEDIUM observados. Si en producción aparecen flags de mayor severidad, el score puede cambiar drásticamente.

---

## 6. Señales explotables para el grafo

### Nodo Dossier

```
(:Dossier {
  ocid: string PK,
  entity_name: string,
  sector: string,
  procedure_code: string,
  monto: float,
  total_score: int,
  risk_level: string,
  total_flags: int,
  total_pages: int,
  coverage_pct: float,
  generated_at: datetime
})
```

### Nodo RiskFlag

```
(:RiskFlag {
  flag_id: string PK (= ocid + "_" + flag_code + "_" + page_number),
  flag_code: string,
  flag_name: string,
  severity: string,
  score_contribution: int,
  page_number: int,
  evidence_quote: string,
  rule_id: string,
  detection_method: string
})
```

### Relaciones

```
(:Contract {ocid})-[:ANALYZED_BY]->(:Dossier {ocid})
(:Dossier)-[:HAS_FLAG]->(:RiskFlag)
```

### Señales de flag para detección de corrupción

- **F13 Dossier high-risk:** total_score ≥ umbral. ESSALUD 988512 score=60 ALTO.
- **F14 Flags TDR pre-calculados:** `OBSOLETE_PHYSICAL_FORMAT` podría indicar requisitos en papel → menor transparencia digital → flag de opacidad.
- **Score normalizado:** total_score / (max posible por sector) → score de riesgo relativo para comparar entre contratos.

---

## 7. Recomendaciones de modelado

### chunks.json y pages.json — NO como nodos

Los flags ya capturan las citas textuales relevantes (`evidence_quote`). Crear nodos por chunk (365 por dossier) es sobre-granular para análisis de riesgo.

**Opción recomendada:** Almacenar pages como propiedad blob del Dossier solo si se necesita full-text search. Para el grafo de corrupción, RiskFlag con evidence_quote es suficiente.

### Distribución Dossier vs Contract

| Propiedad | Nodo | Razón |
|-----------|------|-------|
| ocid | Contract + Dossier | clave de cruce |
| monto | Contract | viene de OCDS |
| procedure_code | Dossier | viene del TDR PDF |
| total_score | Dossier | calculado por pipeline |
| risk_level | Dossier | calculado |
| evidence_quote | RiskFlag | extracto del PDF |

Separar en 2 nodos mantiene OCDS y análisis TDR independientes.

### Piloto: 3 dossiers completos

3 dossiers (1157442, 988512, 2024_200254_6) son suficientes para MVP. 17 procesos restantes en recon_20 pueden incorporarse cuando OCR esté disponible.

### recon_20_processes.csv — Usar como índice de procesos con TDR

Las 20 filas son contratos de alto valor con TDRs identificados manualmente. Todos tienen ocid → join directo con OCDS. Usar como subset de alta prioridad para pilotos de flag.
