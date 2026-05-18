# SUNAT Research Report

##调查目标
Investigate SUNAT (Superintendencia Nacional de Aduanas y de Administración Tributaria) public interfaces for company RUC and tax status data collection for anti-corruption monitoring.

**Website:** https://www.sunat.gob.pe/  
**Status:** Active government tax authority of Peru

---

## 1. SUNAT Public APIs and Data Endpoints

### 1.1 Padrón Reducido RUC (Bulk Download) — CONFIRMED

**Landing Page:** https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html  
**Actual ZIP URL:** http://www2.sunat.gob.pe/padron_reducido_ruc.zip  
**Format:** Pipe-delimited TXT inside ZIP  
**Encoding:** ISO-8859-1 (Latin-1)  
**Update frequency:** Monthly (updated ~17th of each month)  
**Size:** ~200 MB ZIP, ~14.5 million records  
**Authentication:** NONE required  
**Captcha:** NONE

**Direct link confirmed from landing page HTML:**
```
http://www2.sunat.gob.pe/padron_reducido_ruc.zip
```

**Secondary file (Local Anexo):**
```
https://www.sunat.gob.pe/descargaPRR/padron_reducido_local_anexo.zip
```

### 1.2 Individual RUC Query (No Auth) — CONFIRMED

**URL:** https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp  
**Parameters:** `RUC` (11 digits), or `DNI`, or `Nombre/Razón Social`  
**No authentication required** for basic search  
**Note:** Contains a CAPTCHA (visual code) that must be solved per request

### 1.3 Multiple RUC Query (No Auth) — CONFIRMED

**URL:** http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias  
**Method:** POST with up to 100 RUCs at once  
**Format:** Plain text file with pipe-delimited RUCs  
**No CAPTCHA visible** for bulk, but rate limiting likely applies  
**Limitation:** Must submit as `.txt` file upload

### 1.4 Agent Retainer Padrones (Text Downloads)

**URL pattern:** https://www.sunat.gob.pe/descarga/AgentRet/*.html  
**Example:** https://www.sunat.gob.pe/descarga/AgentRet/AgenRet0.html  
**Format:** ZIP containing TXT files with RUC + Name + Resolution Number  
**No authentication required**

---

## 2. Data Available Per RUC (from Padrón Reducido)

### 2.1 Fields (Confirmed from Source Data)

| Field | Description | Example |
|-------|-------------|---------|
| `ruc` | 11-digit RUC number | 20555534987 |
| `razon_social` | Business legal name | CONSORCIO LIMA DIRECC SAC |
| `estado` | Tax status | ACTIVO, BAJA |
| `condicion` | Address condition | HABIDO, NO HABIDO |
| `ubigeo` | 6-digit UBIGEO geographic code | 150132 |
| `tipo_via` | Street type abbreviation | AV., JR., CAL. |
| `nombre_via` | Street name | LIMA |
| `codigo_zona` | Zone type code | URB. |
| `tipo_zona` | Zone name | MIRAFLORES |
| `numero` | Street number | 101 |
| `interior` | Interior/unit | S/N, OF. 202 |
| `lote` | Lot number | B |
| `departamento` | Department/floor | 302 |
| `manzana` | Block | 23 |
| `kilometro` | Kilometer marker | 15.50 |

### 2.2 Field Details

**`estado` (Tax Status):**
- `ACTIVO` — Active taxpayer
- `BAJA` — Cancelled/suspended

**`condicion` (Address Condition):**
- `HABIDO` — Found at address (reachable)
- `NO HABIDO` — Not found at address

**`ubigeo` (Geographic Code):**
- 6-digit code where first 2 digits = department
- 150101 = Lima, Cercado
- 040101 = Amazonas, Chachapoyas
- 210401 = Huánuco, Amarilis

### 2.3 Data Quality Observations

- RUC is 11 digits with checksum (last digit is check digit)
- Special characters (ñ, tildes) present in names — requires ISO-8859-1 decoding
- Some fields may contain encoding artifacts in test fixtures (e.g., `Ã` instead of `Ñ`)
- Address is composite; `domicilio_fiscal` built by concatenating type_via + nombre_via + numero + interior

---

## 3. Public Padrón Downloads

### 3.1 CONFIRMED Bulk Downloads

| Name | URL | Format | Auth |
|------|-----|--------|------|
| Padrón Reducido RUC | http://www2.sunat.gob.pe/padron_reducido_ruc.zip | ZIP/TXT pipe-delimited | None |
| Padrón Reducido Local Anexo | https://www.sunat.gob.pe/descargaPRR/padron_reducido_local_anexo.zip | ZIP/TXT | None |
| Agentes de Retención | https://www.sunat.gob.pe/descarga/AgentRet/AgenRet_TXT.zip | ZIP/TXT | None |
| Agentes de Percepción | https://www.sunat.gob.pe/descarga/AgentRet/AgenPerc0.html (links to ZIP) | ZIP/TXT | None |
| Buenos Contribuyentes | https://www.sunat.gob.pe/descarga/BueCont/BueCont0.html | ZIP/TXT | None |
| Padrón Fraccionamiento FRAES | http://www.sunat.gob.pe/cl-ti-itfraccionamiento-consultas/ConsultaPadronFraes.html | HTML form | None |

### 3.2 No CSV/Excel Bulk Download

- No CSV or XLSX format is offered for the main RUC padrón
- All downloads are ZIP files containing pipe-delimited (`|`) TXT files
- Alternative padrones (agents, buenos contribuyentes) also use pipe-delimited TXT format

---

## 4. SUNAT Website URL Structure

### 4.1 RUC Search by Number

**Individual query:**
```
https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp
```
Form parameters:
- Tab: "Por RUC" selected
- Input: 11-digit RUC number
- CAPTCHA image requires solving

**Multiple RUC query:**
```
http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias
```
- Accepts up to 100 RUCs via file upload
- Format: `10000000009|` per line in .txt

### 4.2 Company Information Lookup

The web interface shows:
- RUC number
- Business name (razón social)
- Tax status (estado): ACTIVO / BAJA
- Condition (condición): HABIDO / NO HABIDO
- Fiscal address (domicilio fiscal)
- Economic activity (if available)

### 4.3 URL Patterns for Key Services

```
# Main portal
https://www.sunat.gob.pe/

# SOL (online operations) - requires Clave SOL
https://www.sunat.gob.pe/sol.html

# Type of change query
http://e-consulta.sunat.gob.pe/cl-at-ittipcam/tcS01Alias

# Without Clave SOL operations (partial)
https://www.sunat.gob.pe/sinclavesol/index.html
https://www.sunat.gob.pe/sinclavesol/sinClaveSol-empresas.html

# RUC query without auth
https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp

# Multiple RUC query
http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias

# Padrón downloads
https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html

# Tax transparency
https://www.sunat.gob.pe/estadisticasestudios/transparencia-Tributos-Ad.html
```

---

## 5. Authentication and Rate Limits

### 5.1 Authentication Requirements

| Service | Auth Required | Type |
|---------|--------------|------|
| Padrón Reducido download | NO | Public |
| Individual RUC query | NO (CAPTCHA only) | Public |
| Multiple RUC query | NO | Public |
| Agentes Retención download | NO | Public |
| SOL operations | YES | Clave SOL (OAuth2-like) |
| Clave SOL registration | NO | Self-service |

### 5.2 Rate Limits

- No explicit rate limits documented for public query endpoints
- Individual RUC query is protected by per-request CAPTCHA
- Multiple RUC query may have implicit limits (100 RUCs per submission)
- SOL endpoints use OAuth2 with client credentials (not relevant for public scraping)

### 5.3 Clave SOL

- Clave SOL is a username/password + digital certificate system
- Required for: filing taxes, consulting detailed company data, making payments
- NOT required for: Padrón Reducido download, basic RUC query (with CAPTCHA)

---

## 6. CSV/Excel Downloads of Padrón Único de Contribuyentes

**No CSV or Excel format is available** for the main padrón.

All bulk data is distributed as:
- ZIP archives
- Pipe-delimited (`|`) TXT files
- No XLSX, ODS, or CSV offered

**Alternative:** The agents/retention padrones are also pipe-delimited TXT inside ZIP files.

---

## 7. Data Fields and Formats

### 7.1 Padrón Reducido Field Specification

```
Column order (pipe-delimited, ISO-8859-1 encoded):
1.  ruc             # 11 digits
2.  razon_social     # Business name
3.  estado           # ACTIVO | BAJA
4.  condicion        # HABIDO | NO HABIDO
5.  ubigeo           # 6-digit geographic code
6.  tipo_via         # AV | JR | CAL | PSJE | etc.
7.  nombre_via       # Street name
8.  codigo_zona      # URB | Z.I. | etc.
9.  tipo_zona        # Zone name
10. numero           # Street number
11. interior         # Interior designation
12. lote             # Lot
13. departamento     # Department/floor
14. manzana          # Block
15. kilometro        # Kilometer marker
```

### 7.2 Sample Row (from fixture)

```
20555534987|CONSORCIO LIMA DIRECC SAC|ACTIVO|HABIDO|150132|AV.|LIMA|URB.|MIRAFLORES|101||B|302|23|15.50
```

### 7.3 Parsed domicilio_fiscal Example

```
"AV. LIMA 101 B 302 23 15.50"
# tipo_via + nombre_via + numero + lote + departamento + manzana + kilometro
```

### 7.4 UBIGEO Department Codes (First 2 Digits)

| Code | Department |
|------|------------|
| 01 | Amazonas |
| 02 | Ancash |
| 03 | Apurímac |
| 04 | Arequipa |
| 05 | Ayacucho |
| 06 | Cajamarca |
| 07 | Callao |
| 08 | Cusco |
| 09 | Huancavelica |
| 10 | Huánuco |
| 11 | Ica |
| 12 | Junín |
| 13 | La Libertad |
| 14 | Lambayeque |
| 15 | Lima |
| 16 | Loreto |
| 17 | Madre de Dios |
| 18 | Moquegua |
| 19 | Pasco |
| 20 | Piura |
| 21 | Puno |
| 22 | San Martín |
| 23 | Tacna |
| 24 | Tumbes |
| 25 | Ucayali |

---

## 8. Scraping Approaches

### 8.1 Recommended: Bulk Download + Parser (Best for MVP)

**Approach:** Download ZIP from `http://www2.sunat.gob.pe/padron_reducido_ruc.zip` and parse pipe-delimited TXT.

**Pros:**
- No authentication required
- No CAPTCHA
- Complete dataset (14.5M records)
- Single download, self-contained
- Monthly updates allow incremental refresh

**Cons:**
- Large file (~200 MB compressed)
- Requires ISO-8859-1 decoding
- ZIP structure may change (discovery step needed)

**Implementation:** Already implemented in `apps/scrapers/src/agenteperry/collectors/sunat.py`

```python
# Key constants from source
SUNAT_PADRON_URL = "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html"
SUNAT_COLUMNS = ["ruc", "razon_social", "estado", "condicion", "ubigeo", 
                 "tipo_via", "nombre_via", "codigo_zona", "tipo_zona", 
                 "numero", "interior", "lote", "departamento", "manzana", "kilometro"]
```

**Code snippet for URL discovery:**
```python
def _discover_download_url(self) -> str | None:
    href_patterns = [
        r"href=['\"]([^'\"]*mrc137[^\"']+\.zip[^'\"]*)['\"]",
        r"href=['\"]([^'\"]*padron[^\"']+\.zip[^'\"]*)['\"]",
        r"(https?://www\.sunat\.gob\.pe/descargaPRR/[^\"'<\s]+\.zip)",
    ]
    # Scrapes landing page for ZIP URL
```

### 8.2 Alternative: Web Form Scraping (Individual/Multiple RUC)

**Approach:** POST to `http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias` with RUC list.

**Pros:**
- Real-time data (not monthly)
- More detailed info available per query

**Cons:**
- Requires CAPTCHA solving for individual query
- Multiple RUC query limited to 100 per submission
- Higher risk of blocking
- More complex session management

**Not recommended for bulk** — use Padrón Reducido instead.

### 8.3 Known Issues

- Landing page URL `SUNAT_PADRON_URL` redirects to actual ZIP hosted on `www2.sunat.gob.pe`
- ZIP filename pattern includes date: `padron_reducido_ruc.zip`
- File is pipe-delimited (`|`), not comma-delimited
- Some records may have encoding issues — ISO-8859-1 is required, not UTF-8
- The `codigo_zona` field appears to hold zone type abbreviations (URB., Z.I.) while `tipo_zona` holds zone name

---

## 9. Known Endpoints Summary

| Endpoint | URL | Data | Auth |
|----------|-----|------|------|
| Padrón Reducido ZIP | http://www2.sunat.gob.pe/padron_reducido_ruc.zip | Full RUC padrón (14.5M) | None |
| Padrón Landing | https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html | Discovery page | None |
| Padrón Local Anexo | https://www.sunat.gob.pe/descargaPRR/padron_reducido_local_anexo.zip | Local annex padron | None |
| RUC Individual Query | https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp | Single RUC lookup | CAPTCHA |
| RUC Multiple Query | http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias | Batch 100 RUCs | None |
| Agentes Retención | https://www.sunat.gob.pe/descarga/AgentRet/AgenRet_TXT.zip | Agent list | None |
| Buenos Contribuyentes | https://www.sunat.gob.pe/descarga/BueCont/BueCont0.html | Good taxpayer list | None |
| SOL Portal | https://www.sunat.gob.pe/sol.html | Tax operations | Clave SOL |
| ESSALUD Query | http://www.sunat.gob.pe/cl-ti-itessalud/essaludceS01Alias | Employer consulta | None |

---

## 10. Recommendations for AgentePerry MVP

### 10.1 Primary Approach: Bulk Padrón Download

1. **Implement in `SunatPadronCollector`** (`apps/scrapers/src/agenteperry/collectors/sunat.py`)
   - Already partially implemented
   - Key task: wire `--limit` chunked processing to avoid RAM explosion on full 14.5M load

2. **Update frequency:** Run monthly (coincides with SUNAT update cycle)

3. **Schema enrichment:** Store in `source_records` with:
   - `entity_ruc` = 11-digit RUC
   - `entity_name` = `razon_social`
   - `parsed_data` = `{estado, condicion, ubigeo, domicilio_fiscal}`
   - `region` = first 2 digits of ubigeo

4. **Anti-corruption signals:**
   - `estado = BAJA` → company cancelled but still bidding?
   - `condicion = NO HABIDO` → address not found, possible shell company
   - `ubigeo` mismatch with contracting entity → red flag for review

### 10.2 Secondary: Multiple RUC Lookup

- Use for real-time validation of specific RUCs discovered in OCDS contracts
- Not for bulk; use when Padrón data is stale (> 1 month)
- Requires file upload via POST — more complex than bulk download

### 10.3 Out of Scope for MVP

- CAPTCHA solving (not legal-safe for automated monitoring)
- Clave SOL integration (private tax data)
- Individual RUC web form scraping (too brittle)

### 10.4 Priority Fields for MVP

| Priority | Field | Use for Anti-Corruption |
|----------|-------|------------------------|
| P0 | `ruc` | Unique identifier |
| P0 | `estado` | BAJA = cancelled company |
| P0 | `condicion` | NO HABIDO = unreachable |
| P0 | `ubigeo` | Geographic mismatch detection |
| P1 | `razon_social` | Cross-reference with OCDS |
| P1 | `domicilio_fiscal` | Shared address detection |

---

## 11. Key Implementation Files in This Repo

| File | Purpose |
|------|---------|
| `apps/scrapers/src/agenteperry/collectors/sunat.py` | SUNAT Padrón collector (partial impl) |
| `apps/scrapers/tests/fixtures/sunat_padron_sample.txt` | 25-row fixture for testing |
| `apps/scrapers/tests/test_sunat_enrichment.py` | Non-destructive enrichment tests |
| `specs/active/SPEC-0008-sunat-padron-enrichment/spec.md` | Active spec for padron enrichment |
| `data/scraped/collectors/sunat_padron/records.jsonl` | Fixture output (25 records) |
| `data/scraped/collectors/sunat_padron/audit.json` | Audit metrics from fixture run |

---

## 12. References

- SUNAT Main Portal: https://www.sunat.gob.pe/
- Padrón Reducido Landing: https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html
- Direct ZIP: http://www2.sunat.gob.pe/padron_reducido_ruc.zip
- RUC Query (Individual): https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/FrameCriterioBusquedaWeb.jsp
- RUC Query (Multiple): http://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias
- SUNAT Orientation (RUC): https://orientacion.sunat.gob.pe/
- Clave SOL Info: https://www.sunat.gob.pe/sinclavesol/index.html
- ACTIVE SPEC: `specs/active/SPEC-0008-sunat-padron-enrichment/`
