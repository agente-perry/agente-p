# SEACE Research Report — Sistema Electrónico de Contrataciones del Estado

> **Investigación de scraping:** SEACE (prod.seace.gob.pe)  
> **Fecha:** 2026-05-17  
> **Proyecto:** AgentePerry TDR Scanner  
> **Última actualización del repo:** 2026-05-17  

---

## Resumen Ejecutivo

SEACE es el portal oficial de contrataciones públicas del Estado peruano. El repo AgentePerry ya tiene **datos OCDS** que incluyen URLs directas a documentos SEACE, por lo que **no se requiere scraping HTML masivo** para el MVP actual.

**Hallazgo clave:** Los documentos (bases, pliegos, TDRs) están accesibles via URL directa sin login, captcha ni paywall.

---

## 1. API y Endpoints de SEACE

### 1.1 OCDS como fuente principal (recomendado)

SEACE publica sus datos via el estándar **OCDS (Open Contracting Data Standard)** a través de un nodo de datos abiertos:

| Recurso | URL | Formato |
|---------|-----|---------|
| OCDS Perú | https://data.open-contracting.org/es/publication/135 | JSONL.gz |
| Descarga por año | `https://data.open-contracting.org/es/publication/135/download?name={year}.jsonl.gz` | JSONL.gz |
| Descarga completa | `https://data.open-contracting.org/es/publication/135/download?name=full.jsonl.gz` | JSONL.gz (~2GB) |

**Tamaños aproximados:**
- Full JSONL.gz: ~2,055 MB
- 2025 JSONL: ~170 MB
- 2026 JSONL: ~77 MB
- 2024 JSONL: ~147 MB

**Licencia:** CC BY 4.0

**OCID prefix:** `ocds-dgv273` (Perú - SEACE)

**Rango de datos:** 2003-01 a 2026-05

**Campos OCDS relevantes para TDRs:**
```json
{
  "ocid": "ocds-dgv273-seacev3-988512",
  "tender": {
    "id": "AS-SM-55-2023-ESSALUD/GCL-1",
    "title": "Proceso de contratación...",
    "documents": [
      {
        "title": "Bases Administrativas",
        "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=d0f684bf-...",
        "format": "application/pdf"
      }
    ]
  },
  "awards": [...],
  "contracts": [...]
}
```

### 1.2 OECE/SEACE Datos Abiertos (Pentaho)

Portal alternativo con descarga directa por categorías:

| Aspecto | Detalle |
|---------|---------|
| **URL base** | https://bi.seace.gob.pe/pentaho/api/repos/:public:portal:datosabiertos.html/content?userid=public&password=key |
| **URL real descarga** | https://contratacionesabiertas.oece.gob.pe/descargas |
| **Auth** | Parámetros URL: `userid=public&password=key` |
| **Formato** | CSV / XLSX |
| **Método** | Direct download (no Playwright requerido para archivos) |

**Categorías disponibles:**
```
- procedimientos
- contratos
- pac
- ordenes_compra
- proveedores
- entidades
- comites
- pronunciamientos
```

**Estado en el repo:** Collector `SeaceOeceCollector` implementado en `apps/scrapers/src/agenteperry/collectors/seace.py` pero data local está vacía.

### 1.3 SEACE Web (no recomendado para scraping)

| Aspecto | Detalle |
|---------|---------|
| **Portal principal** | https://prod.seace.gob.pe/ |
| **Portal alternativo** | https://www2.seace.gob.pe/ |
| **Requiere JS** | Sí (SPA/Angular) |
| **Scraping** | No recomendado para MVP — OCDS tiene los datos |

---

## 2. Estructura de URLs del Portal SEACE

### 2.1 URL pattern de documentos (CONFIRMADO)

```
https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>
```

**Ejemplos verificados en el repo:**
```
https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=d0f684bf-...
https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=cee1cdc2-...
```

**Características:**
- `fileCode` es un UUID v4
- No requiere sesión ni cookie
- Rate-limiting no observado en pruebas manuales
- Extensions permitidas: pdf, rar, zip, doc, docx

### 2.2 URL patterns推测 (basado en investigación previa)

```
# Búsqueda de procesos por sector
https://prod.seace.gob.pe/SeaceWeb-PRO/buscarProceso?-sector=salud

# Detalle de proceso
https://prod.seace.gob.pe/SeaceWeb-PRO/detalleProceso?codigo=<process_id>

# Proveedores
https://prod.seace.gob.pe/SeaceWeb-PRO/buscarProveedor?ruc=<ruc>

# Entidades
https://prod.seace.gob.pe/SeaceWeb-PRO/buscarEntidad?nombre=<nombre>
```

> **Nota:** Los patterns acima son推测 basados en análisis del legacy config. Verificar con DevTools antes de usar.

---

## 3. Datos Disponibles por Tipo de Proceso

### 3.1 Procesos de Contratación (contratos)

**Fuente:** OCDS (`contracts` array) + OECE (`contratos` categoría)

| Campo | Disponibilidad | Formato |
|-------|----------------|---------|
| `process_id` / `tender_id` | ✅ OCDS | String |
| `ocid` | ✅ OCDS | `ocds-dgv273-seacev3-<id>` |
| `entity_ruc` | ✅ OCDS | 11 dígitos (RUC) |
| `entity_name` | ✅ OCDS | String |
| `supplier_ruc` | ✅ OCDS | `PE-RUC-XXXXXXXXXXX` |
| `supplier_name` | ✅ OCDS | String |
| `amount` / `monto` | ✅ OCDS | Decimal (PEN) |
| `fecha` | ✅ OCDS | ISO 8601 date |
| `procedure_type` | ✅ OCDS | `open`, `direct`, `simplified`, etc. |
| `sector` | ⚠️ Keyword-based | Filtrado por `entity_name` keywords |
| `tender.documents[]` | ✅ OCDS | URLs directas SEACE |

**Procedure types (modalidades) en SEACE:**
- Open (Licitación Pública)
- Direct (Contratación Directa)
- Simplified (Adjudicación Simplificada)
- Selective (Selección)
- AMC (Articulated Modalidad de Cooperativity)

### 3.2 Documentos de Proceso (bases, TDRs, pliegos)

**Fuente:** `tender.documents[]` en OCDS

| Campo | Disponibilidad |
|-------|----------------|
| `document.title` | ✅ |
| `document.url` | ✅ URL directa SEACE |
| `document.format` | ✅ `application/pdf`, etc. |
| `document.datePublished` | ✅ |

**Tipos de documento encontrados:**
- Bases Administrativas
- Bases Integradas
- Pliego de Absolución de Consultas y Observaciones
- Pliego de Observaciones
- Resumen Ejecutivo
- Documentos de Presentación
- Informe de Desierto

### 3.3 Proveedores

**Fuente:** OECE (`proveedores` categoría) + OCDS (`awards.suppliers`)

| Campo | Disponibilidad |
|-------|----------------|
| `ruc` | ✅ |
| `razon_social` | ✅ |
| `estado` | ✅ SUNAT |
| `condicion` | ✅ SUNAT |
| `ubigeo` | ✅ SUNAT |
| `domicilio_fiscal` | ✅ SUNAT |

### 3.4 Entidades/Compradores

**Fuente:** OCDS (`buyer`, `parties`) + OECE (`entidades`)

| Campo | Disponibilidad |
|-------|----------------|
| `ruc` | ✅ |
| `nombre` | ✅ |
| `sector` | ⚠️ Keyword-based |

---

## 4. Autenticación y Rate Limits

### 4.1 Autenticación

| Método | Estado |
|--------|--------|
| **Documentos OCDS** | Sin auth (público) |
| **URLs documento SEACE** | Sin auth (probado con curl) |
| **OECE Pentaho** | Auth URL params (`userid=public&password=key`) |
| **SEACE Web** | Sin auth para consulta pública |

### 4.2 Rate Limits

| Fuente | Límite observado | Recomendación |
|--------|------------------|---------------|
| URLs documento SEACE | No observado | 1 req/s (cortesía) |
| OECE Pentaho | Desconocido | 1 req/s |
| SEACE Web | Desconocido | 10 req/min |

### 4.3 Bloqueos

| Bloqueo | Encontrado |
|---------|-----------|
| Login requerido | ❌ No |
| CAPTCHA | ❌ No |
| Paywall | ❌ No |
| Rate limiting agresivo | ❌ No |

---

## 5. Data Quality Observations

### 5.1 OCDS Data Quality

**Fortalezas:**
- Estándar internacional OCDS
- `tender.documents[]` incluye URLs directas a documentos SEACE
- `awards.suppliers[]` incluye RUC completo (formato `PE-RUC-XXXXXXXXXXX`)
- Fechas en ISO 8601
- Montos en PEN (nuevo sol peruano)

**Limitaciones:**
- No hay campo `sector` formal — requiere filtrado por keywords en `entity_name`
- Algunos contratos pueden tener `tender.documents` vacío
- RUC de proveedores en `awards.suppliers` puede variar de formato

### 5.2 Documentos TDR Quality

**Hallazgos de investigación (SPEC-0009):**

| Métrica | Valor |
|---------|-------|
| Procesos con TDR disponible | 100% (20/20 muestra) |
| Formatos | PDF v1.3, PDF v1.7, RAR (Win32 v4) |
| Docs por proceso | 4–28 |
| PDFs con texto digital | ~50% |
| PDFs necesitan OCR | ~50% |
| RAR/ZIP pendientes | 5 de 13 auditados |

### 5.3 OECE Data Quality

- Datos en CSV/TSV pipe-delimited
- Encoding: UTF-8 o Latin-1
- Headers variables según categoría

---

## 6. Recomendaciones de Scraping

### 6.1 Estrategia recomendada (MVP)

**Prioridad 1 — OCDS como fuente principal:**
```bash
# Descargar OCDS
https://data.open-contracting.org/es/publication/135/download?name=2025.jsonl.gz

# Datos ya incluyen:
# - tender.documents[].url → URLs SEACE directas
# - awards.suppliers[].id → RUC proveedores
# - buyer.name, buyer.identifier.id → entidad
```

**Ventajas:**
- No requiere scraping de SEACE
- Formato estándar, parser disponible (`ijson` para streaming)
- Atualización mensual (día 1 de cada mes)

### 6.2 Estrategia OECE como enriquecimiento

```bash
# Categorías de enriquecimiento
- contratos: detalle de contratos
- comites: miembros del comité de selección
- ordenes_compra: órdenes generadas
- proveedores: datos de proveedores
```

**Nota:** Collector implementado (`SeaceOeceCollector`) pero no ejecutado aún con datos reales.

### 6.3 Estrategia de documentos (TDRs/bases)

**Flujo recomendado:**
1. Extraer `tender.documents[].url` de OCDS
2. Filtrar por título (`%base%`, `%tdr%`, `%pliego%`, etc.)
3. Descargar con rate limit 1 req/s
4. Calcular checksum SHA256
5. Registrar en `tdr_documents`

**URL directa verificada:**
```
https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>
```

### 6.4 NO recomendado para MVP

| Método | Razón |
|--------|-------|
| Playwright en SEACE Web | No necesario — OCDS tiene los datos |
| Form scraping SEACE | SPA dinámico, alto riesgo de rotura |
| XHR intercept SEACE | Complejo, sin beneficios sobre OCDS |
| Pentaho UI automation | Ya hay download URL directo |

---

## 7. Datos Confirmados en el Repo

### 7.1 Archivos OCDS actuales

| Archivo | Registros | Descripción |
|---------|-----------|-------------|
| `data/scraped/ocds/records.jsonl` | ~72,399 | Records OCDS completos |
| `data/scraped/ocds/contracts_2026.jsonl` | grande | Contratos 2026 |
| `data/scraped/filtered/salud_2024_2025.jsonl` | 2,566 | Salud 2024–2025 |
| `data/scraped/filtered/ambiente_2024_2025.jsonl` | 99 | Ambiente/Minería 2024–2025 |
| `data/scraped/filtered/salud_2024_2025_with_documents.jsonl` | 2,566 | Salud con documentos |
| `data/scraped/filtered/ambiente_2024_2025_with_documents.jsonl` | 99 | Ambiente con documentos |

### 7.2 Estructura de documento en OCDS

```json
{
  "source_code": "ocds_peru",
  "external_id": "ocds-dgv273-seacev3-988512",
  "record_type": "contract",
  "parsed_data": {
    "ocid": "ocds-dgv273-seacev3-988512",
    "tender_id": "AS-SM-55-2023-ESSALUD/GCL-1",
    "procedure_type": "simplified"
  },
  "raw_data": {
    "ocid": "ocds-dgv273-seacev3-988512",
    "tender": {
      "id": "AS-SM-55-2023-ESSALUD/GCL-1",
      "title": "AS-SM-55-2023-ESSALUD/GCL-1",
      "documents": [
        {
          "title": "Bases Administrativas",
          "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=...",
          "format": "application/pdf"
        }
      ]
    },
    "awards": [...],
    "contracts": [...]
  },
  "entity_name": "SEGURO SOCIAL DE SALUD (ESSALUD)",
  "entity_ruc": "20123456789",
  "supplier_name": "VIPROSEG S.A.C.",
  "supplier_ruc": "20123456789",
  "monto": 195383235.96,
  "fecha": "2024-02-14"
}
```

---

## 8. Schema de Base de Datos

### 8.1 Tablas relacionadas con SEACE

```sql
-- source_records (fuente OCDS)
id                  uuid
source_code         text      -- 'ocds_peru'
external_id         text      -- ocid
record_type         text      -- 'contract'
entity_name         text
entity_ruc          text
supplier_name       text
supplier_ruc        text
monto               numeric
fecha               date
raw_data            jsonb     -- OCDS completo
parsed_data         jsonb     -- campos normalizados

-- tdr_documents (documentos descargados)
id                  uuid
external_id         text
title               text
entity_name         text
source_url          text      -- URL SEACE original
file_url            text
procedure_code      text      -- tender.id
sector              text      -- 'salud' | 'ambiente_mineria'
local_path          text
checksum            text
download_status     text      -- 'available' | 'downloaded' | 'failed'
publication_date    date
estimated_value     numeric
source_record_id    uuid
created_at          timestamptz
```

---

## 9. Hallazgos Clave para Anti-Corrupción

### 9.1 Señales de Riesgo Disponibles

| Señal | Fuente | Detalle |
|-------|--------|---------|
| Único postor | OCDS | `tender.numberOfTenderers == 1` |
| Contratación directa | OCDS | `tender.procurementMethod == 'direct'` |
| Monto atípico | OCDS + calculado | Percentil > P95 por modalidad |
| Proveedor no encontrado | SUNAT | Condición `NO HABIDO` |
| Proveedor dado de baja | SUNAT | Estado `BAJA DEFINITIVA` |
| Domicilio compartido | SUNAT | Múltiples empresas en misma dirección |
| Proveedor nuevo | SUNAT | Empresa < 1 año antes de convocatoria |
| Miembro comité sancionado | Contraloria + OECE | Cross-reference pendiente |

### 9.2 Datos requeridos para scoring

```
OCDS:          tender.numberOfTenderers, tender.procurementMethod,
               tender.value.amount, contracts[].value.amount,
               awards[].suppliers[], tender.documents[]

SUNAT:         ruc, estado, condicion, ubigeo, fecha_inicio_actividades

OECE:          comites (miembros), contratos, ordenes_compra

Contraloría:   sanciones vigentes (DNI/RUC)
```

---

## 10. Próximos Pasos Recomendados

### 10.1 Para el MVP (TDR Scanner)

1. **Usar OCDS como fuente** — ya tiene URLs de documentos SEACE
2. **Ejecutar OECE collector** para enriquecer con comités y órdenes
3. **Implementar descarga de TDRs** siguiendo SPEC-0010
4. **Enriquecer con SUNAT** para validar proveedores

### 10.2 Para investigación futura

1. **Playwright para SEACE Web** — solo si se requiere datos no disponibles en OCDS
2. **CGR Informes** — para informes de control por entidad
3. **ONPE/JNE** — solo para casos específicos con alto score

---

## 11. Referencias

| Recurso | URL/Path |
|---------|----------|
| Portal SEACE | https://prod.seace.gob.pe/ |
| OCDS Perú | https://data.open-contracting.org/es/publication/135 |
| OECE Datos Abiertos | https://contratacionesabiertas.oece.gob.pe/descargas |
| Ley 32069 | https://www.gob.pe/institucion/oece/colecciones/45029-ley-n-32069 |
| SPEC-0009 (TDR Discovery) | `specs/active/SPEC-0009-tdr-discovery/spec.md` |
| SPEC-0010 (TDR Downloader) | `specs/active/SPEC-0010-tdr-downloader/spec.md` |
| TDR Discovery Report | `docs/TDR_DISCOVERY_REPORT.md` |
| OECE Collector | `apps/scrapers/src/agenteperry/collectors/seace.py` |

---

*Reporte generado como parte de la investigación de scraping para el proyecto AgentePerry TDR Scanner.*
