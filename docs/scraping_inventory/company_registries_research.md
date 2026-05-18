# Peruvian Company and Legal Entity Registries — Anti-Corruption Data Research

**Date:** 2026-05-17
**Objective:** Investigate public data sources for tracing company ownership, representatives, and political connections in Peru.
**Output path:** `docs/scraping_inventory/company_registries_research.md`

---

## Executive Summary

| Registry | Public Data | Searchable by Rep? | Shareholder Data | API/Bulk | Status |
|---|---|---|---|---|---|
| **SUNARP** | Yes — partial | Via form (no API) | Not in public view | None | Viable for targeted queries |
| **SUNAT RUC** | Yes — basic | No (name/RUC only) | No | Bulk download (padron reducido) | P0 implemented |
| **SIDJI/DJI** | Yes — limited | On-demand only | No (family ties only) | None (CAPTCHA required) | P1 deferred, legal-safe |
| **ONPE Claridad** | Partial | No | No | None known | P1 deferred |
| **JNE Voto Informado** | Yes | No | No | None | P1 deferred |
| **JNE Plataforma Electoral** | Yes | No | No | None | P1 deferred |
| **RCC** | Not confirmed | — | — | — | Not a public registry |

---

## 1. SUNARP — Superintendencia Nacional de los Registros Públicos

### Website
- **Main portal:** https://www.sunarp.gob.pe/
- **Servicios en linea:** https://www.sunarp.gob.pe/serviciosenlinea/portal/index.html
- **SPRL (Publicidad Registral en Linea):** https://sprl.sunarp.gob.pe/ (requires login)
- **Directorio Nacional de Personas Juridicas:** https://www.sunarp.gob.pe/dn-personas-juridicas.asp

### What Public Data Is Available

SUNARP maintains several public-facing services:

#### 1.1 Directorio Nacional de Personas Juridicas
- **URL:** https://www.sunarp.gob.pe/dn-personas-juridicas.asp
- **Data:** Search for registered legal entities (sociedades, EIRLs, cooperativas)
- **Fields available via search:** Razon social, numero de partida, zona registral
- **Limits:** Rate-limited (5 requests/minute observed); large result sets trigger Excel download instead of browser display

#### 1.2 Consulta de Sociedades (DL 1427)
- **URL:** https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-pj-dl-1427.asp
- **Data:** Societies subject to extinction for prolonged inactivity
- **Search options:** Por razon social, por numero de partida, por ano de proceso
- **Output:** When results exceed 5000 records, system offers Excel download
- **Notes:** This covers societies being dissolved by SUNAT referral

#### 1.3 Consulta de EIRLs
- **URL:** https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-eirls.asp
- **Data:** Empresa Individuales de Responsabilidad Limitada
- **Search:** Por razon social, zona registral, mes/ano

#### 1.4 Consulta de Cooperativas
- **URL:** https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-cooperativas.asp
- **Sub-categories:** Cooperativas, Cooperativas Agrarias, COOPAC (Cooperativas de Ahorro y Credito)

#### 1.5 Consulta de Sociedades BIC
- **URL:** https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-sociedades-bic.asp
- **Data:** Companies under BIC regime (Ley 26887)

### Are There Searches for Representatives (Representantes Legales)?

**Direct search: NO** — There is no public SUNARP form that accepts a representative's DNI or name and returns all companies they represent.

**Indirect path:**
1. Search company by name/partida → get partida registral
2. Request "copia literal" of the company registration
3. The copia literal contains the representative(s) data

However, copia literal is accessed through SPRL (paid service) or "copia literal al toque" (free but limited).

### Shareholder Information

**Direct public access: NO** — SUNARP does not publish shareholder lists in its public web forms. The company registration contains "poderes" and "gerentes" but not necessarily the equity holders. The "capital social" amount appears in the registration but not the individual shareholders' stakes.

To get shareholder structure, one must request a copia literal which includes the "acta de constitucion" and any subsequent modifications. This is a paid service via SPRL.

### Scraping / API Access

| Aspect | Status |
|---|---|
| Public API | None |
| Bulk download | None (only per-query results) |
| Form-based search | Yes — classic ASP forms, works with HTTP POST |
| CAPTCHA | None on main public forms |
| Rate limit | Observed ~5 req/min on some endpoints |
| Login required | SPRL requires login; basic search does not |
| Known anti-scraping | Large result sets redirect to Excel download; no JSON API |

**Scraping viability:** Medium. Forms work with plain HTTP POST without heavy anti-bot measures. However, there is no structured data output (no JSON API), results come as HTML tables or Excel files. The directory national search at `dn-personas-juridicas.asp` requires form interaction. Rate limiting exists.

### Data Formats Available

- **HTML** — displayed in browser for small result sets
- **Excel (.xls)** — triggered automatically when results exceed ~5000 rows
- **Copia literal PDF** — available via SPRL (paid)
- **No JSON, no CSV, no open data endpoint**

### Key Anti-Corruption Use Cases

1. **Verify company representative** — search by company name, get partida, request copia literal for current representatives
2. **Detect shell companies** — cross-reference companies with same address or same representatives (requires multiple queries)
3. **Track cooperative governance** — COOPAC and cooperativas agrarias have searchable directories
4. **Verify company age and status** — DL 1427 section shows companies being dissolved for inactivity (signal of shell company pattern)

### Forward-Compatibility Notes for Anti-Corruption Graph

- **Entity key:** `partida_registral` (SUNARP's internal ID) + RUC for cross-linking
- **Link to OCDS:** Can join via `supplier_ruc` to get contracts won by a company
- **Link to SIDJI/DJI:** Representatives appearing in SUNARP can be cross-referenced with DJI family declarations
- **Limitations:** SUNARP does not expose an API; scaling requires form automation with polite rate limiting. Shareholder data requires paid copia literal access.

---

## 2. SUNAT — Padron Reducido del RUC

### Website
- **Bulk download:** https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html

### What Public Data Is Available

The padron reduzido (reduced registry) contains basic company data for all active RUCs in Peru (~14.5 million records):

| Field | Description |
|---|---|
| `ruc` | 11-digit tax ID |
| `razon_social` | Company legal name |
| `estado` | Status: activo, baja, etc. |
| `condicion` | Condition: habido, no habido, etc. |
| `ubigeo` | Geographic code |
| `domicilio_fiscal` | Full fiscal address |
| `tipo_via`, `nombre_via`, `numero`, etc. | Address components |

### Are There Searches for Representatives?

No. The padron reduzido is a flat file with no representative data. For individual RUC queries (including representative info), use the "Consulta Multiple de RUC" service:

- **URL:** https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias
- **Method:** Form POST with up to 100 RUCs at once
- **CAPTCHA:** Yes — requires manual or OCR-based solving
- **Data per RUC:** Basic fields + `actividad_economica`
- **Representative data:** Not included in this service either

### Shareholder Information

**Not available** via any SUNAT public service.

### Scraping / API Access

| Aspect | Status |
|---|---|
| Bulk download | Yes — ZIP file with pipe-delimited TXT (ISO-8859-1) |
| API | None |
| Historical data | No — only current version |
| Update frequency | Not publicly stated; appears quarterly |

**Collector implemented:** `SunatPadronCollector` in `sources/catalog.py` (P0).

### Data Formats Available

- **ZIP** → `.txt` pipe-delimited (`|`), ISO-8859-1 encoding
- **No JSON, no CSV from SUNAT directly** — conversion required in pipeline

---

## 3. SIDJI/DJI — Declaraciones Juradas de Intereses

### Website
- **System URL:** https://appdji.contraloria.gob.pe/djic/
- **Public search:** Accessible without login via "Buscar Declaracion Jurada de Intereses" option
- **Family search:** "Buscar familiares" option for declared family ties

### What Public Data Is Available

The DJI system collects asset declarations from:
- Public officials (funcionarios y servidores publicos)
- Candidates to public office (candidatos a cargos publicos)

**Publicly accessible data:**
- Official's name and entity
- Declared family ties (spouse, children, other relatives)
- Declarations are linked to public roles

**NOT publicly accessible:**
- Specific asset values (only the existence of conflict is flagged)
- Detailed company ownership percentages
- Bank account details

### Are There Searches for Representatives?

Yes — you can search by the official's name or document number to retrieve their declared ties. However, this is on-demand only; there is no bulk export.

### Anti-Corruption Value

Critical for "El Socio Invisible" pattern detection:
- Cross-reference committee members' family ties with contract winners
- Verify declared conflicts match actual contract awards

### Scraping / API Access

| Aspect | Status |
|---|---|
| Public API | None |
| Bulk download | None |
| CAPTCHA | Yes — on all search forms |
| Login required | For filing; public search is separate |
| Mass scraping | Explicitly blocked — "on-demand only" per catalog |

**Collector status:** `sidji_dji` registered in `sources/catalog.py` as P1/Playwright, currently "Sin collector."

### Data Formats Available

- **HTML results** displayed in browser
- **No JSON, no CSV, no bulk**
- Each search requires CAPTCHA solving

### Forward-Compatibility Notes for Anti-Corruption Graph

- **Entity key:** DNI of declarant
- **Link to OCDS:** Declarant's employer entity can be cross-referenced with contracting entities
- **Link to SUNARP:** Family members may be legal representatives of companies
- **Pattern:** `CONFLICT_OF_INTEREST_FAMILY`, `DECLARED_CONFLICT_IGNORED`
- **Legal-safe note:** DJI data is sensitive — use only for pattern detection, not accusations

---

## 4. ONPE — Oficina Nacional de Procesos Electorales

### Website
- **Main portal:** https://www.onpe.gob.pe/ (returns 403)
- **Claridad portal:** https://claridadportal.onpe.gob.pe/ (returns 403)

### What Public Data Is Available

ONPE is the national electoral authority. The "Claridad" portal was created for electoral transparency but is currently inaccessible via automated tools (returns 403 on all direct HTTP requests).

Based on known ONPE data offerings:
- Electoral processes and results
- Political financing reports (prestamos y donaciones a organizaciones politicas)
- Campaign expenditure limits
- List of precinct workers

### Political Financing / Campaign Contributions

ONPE does collect data on contributions to political parties and candidates, but the public portal is not accessible via automated tools in current testing.

The repo catalog references:
- `onpe_claridad` — Playwright method, owner Noelia, P1
- Source URL: `https://claridadportal.onpe.gob.pe/`
- Method notes: "XHR intercept. Search by RUC/DNI/org."
- Fields: `aportante`, `organizacion_politica`, `monto`, `fecha`, `campana`

### Scraping / API Access

| Aspect | Status |
|---|---|
| Public API | Unknown — portal is Angular SPA, XHR requests are intercepted |
| Bulk download | Not confirmed |
| Direct HTML access | Blocked (403) |
| Playwright approach | Required — XHR intercept during browser session |

**Collector status:** `onpe_claridad` is P1/Playwright, "Sin collector." Deferred per SPEC roadmap.

### Data Formats Available

- **JSON via XHR** — Angular SPA, data loaded dynamically
- **No public bulk endpoint confirmed**

### Forward-Compatibility Notes for Anti-Corruption Graph

- **Entity key:** RUC/DNI of aportante + organizacion_politica ID
- **Link to OCDS:** Cross-reference campaign donors with contract winners (pattern: "El Aportante Favorito")
- **Pattern:** `ELECTORAL_INVESTMENT_RETURN` — company contributes to party that governs contracting entity, then wins contracts

---

## 5. JNE — Jurado Nacional de Elecciones

### Websites
- **Main portal:** https://www.jne.gob.pe/
- **Voto Informado:** https://votoinformado.jne.gob.pe/
- **Plataforma Electoral:** https://plataformaelectoral.jne.gob.pe/

### What Public Data Is Available

JNE maintains:

1. **Voto Informado** — Candidate information including professional experience and any sentences (sentencias)
2. **Plataforma Electoral** — Electoral organization data, candidate lists, expediente information
3. **Candidate disclosures** — Financial and asset information submitted during candidacy

### Anti-Corruption Data Available

- Candidate backgrounds (work history, education)
- Sentencias (court judgments) against candidates
- Financial disclosures filed during candidacy
- Party and movement affiliations

### Scraping / API Access

| Aspect | Status |
|---|---|
| Public API | None confirmed |
| Bulk download | None confirmed |
| Web scraping | Angular SPA — requires XHR intercept |
| Access method | Playwright with XHR interception |

**Catalog entries:**
- `jne_voto_informado` — P1, owner Noelia, XHR intercept Angular SPA
- `jne_plataforma` — P1, owner Noelia, XHR intercept

Both deferred per SPEC roadmap.

### Data Formats Available

- **JSON via XHR** — Dynamic Angular content
- **No bulk, no public API confirmed**

### Forward-Compatibility Notes for Anti-Corruption Graph

- **Entity key:** DNI + candidate ID
- **Link to OCDS:** Candidates who win government contracts post-election
- **Pattern:** Track candidate → elected official → contracting decisions → company wins
- **Note:** JNE data has high value for post-election analysis of officials' previous disclosures vs. contract behavior

---

## 6. RCC — Registro de Cuentas Corrientes

### Status

The Registro de Cuentas Corrientes (RCC) was a banking registry maintained by the SBS (Superintendencia de Banca, Seguros y AFPs). However:

- The RCC is **not a public registry** for anti-corruption tracing
- It contains bank account holder information accessible only to financial system regulators
- No public scraping or API access exists for RCC
- Not relevant to the current MVP scope

**Conclusion:** RCC is not a viable source for AgentePerry's anti-corruption graph. Focus should remain on public registries (SUNARP, SUNAT) and political transparency portals (ONPE, JNE, DJI).

---

## 7. Other Relevant Databases

### 7.1 MEF — Datos Abiertos
- **URL:** https://datosabiertos.mef.gob.pe/dataset
- **Type:** CKAN API
- **Data:** Budget execution (pim, devengado, girado), economic data
- **Collector:** `MefCkanCollector` implemented but data not yet persisted
- **Anti-corruption use:** Detect entities with high budget execution but few contracts (potential fund diversion)

### 7.2 Contraloria — Registro de Sanciones
- **URL:** https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes
- **Type:** Playwright (XLSX download intercept)
- **Data:** Sanctioned individuals and companies — DNI, names, sanction type, validity, entity
- **Collector:** `SancionesCollector` implemented but data not yet locally persisted
- **Anti-corruption use:** Cross-reference sanctioned representatives with contract committee members

### 7.3 SEACE/OECE — Portal de Datos Abiertos
- **URL:** https://contratacionesabiertas.oece.gob.pe/descargas
- **Data:** Procedures, contracts, committees, purchase orders, suppliers, consortia
- **Type:** Pentaho/Angular SPA, XHR intercept required
- **Collector:** `OeceCollector` implemented; local data not yet populated
- **Anti-corruption use:** Committees, suppliers, consortia — primary source after OCDS

### 7.4 Congreso — Archivo Digital de Legislacion
- **URL:** https://www.leyes.congreso.gob.pe/
- **Type:** ASP.NET WebForms scraping + PDF
- **Data:** Normas, leyes, proyectos de ley
- **Collector:** P1, form_scraping, owner Miguel
- **Anti-corruption use:** RAG foundation for legal context

---

## 8. Comprehensive Assessment

### Confirmed Data Sources and URLs

| Source | URL | Status | Data Format |
|---|---|---|---|
| SUNARP DN PJ | https://www.sunarp.gob.pe/dn-personas-juridicas.asp | Viable | HTML + Excel |
| SUNARP Sociedades DL1427 | https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-pj-dl-1427.asp | Viable | HTML + Excel |
| SUNARP EIRLs | https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-eirls.asp | Viable | HTML + Excel |
| SUNARP Cooperativas | https://www.sunarp.gob.pe/seccion/servicios/App/sociedades/consulta-cooperativas.asp | Viable | HTML + Excel |
| SUNAT Padron Reducido | https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html | P0 implemented | ZIP/TXT |
| SUNAT Consulta Multiple | https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsmulruc/jrmS00Alias | Viable with CAPTCHA | HTML |
| SIDJI/DJI Publico | https://appdji.contraloria.gob.pe/djic/Publico/ | Legal-safe on-demand | HTML |
| ONPE Claridad | https://claridadportal.onpe.gob.pe/ | 403 blocked | XHR/JSON (Angular) |
| JNE Voto Informado | https://votoinformado.jne.gob.pe/ | Angular SPA | XHR/JSON |
| JNE Plataforma | https://plataformaelectoral.jne.gob.pe/ | Angular SPA | XHR/JSON |
| MEF Datos Abiertos | https://datosabiertos.mef.gob.pe/dataset | CKAN API | CSV/JSON |
| Contraloria Sanciones | https://www.gob.pe/institucion/contraloria/informes-publicaciones/2706979-registro-de-sanciones-inscritas-y-vigentes | Playwright | XLSX |
| SEACE/OECE | https://contratacionesabiertas.oece.gob.pe/descargas | Pentaho/Angular | CSV/XLSX via XHR |

### Scraping Viability by Source

| Source | Viability | Method | Difficulty | Notes |
|---|---|---|---|---|
| SUNARP DN PJ | Medium | Form POST | Medium | Rate limited, no JSON, Excel fallback |
| SUNARP Sociedades | Medium | Form POST | Medium | Large results trigger Excel download |
| SUNAT Padron | High | Bulk download | Low | ZIP/TXT implemented in collector |
| SIDJI/DJI | Low | Playwright + CAPTCHA | High | On-demand only, no mass scraping |
| ONPE Claridad | Low | Playwright XHR | High | Portal blocked (403), requires interception |
| JNE Voto Informado | Medium | Playwright XHR | High | Angular SPA, requires browser |
| JNE Plataforma | Medium | Playwright XHR | High | Angular SPA, requires browser |
| MEF CKAN | High | CKAN API | Low | Direct REST, implemented |
| Contraloria Sanciones | High | Playwright XLSX | Medium | Intercept download, implemented |
| SEACE/OECE | Medium | XHR intercept | High | Pentaho dynamic endpoints |

### Data Quality Assessment

| Source | Completeness | Accuracy | Timeliness | Structuring |
|---|---|---|---|---|
| SUNARP | Partial (no shareholders) | High (official registry) | Real-time | Poor (HTML only) |
| SUNAT Padron | Good (basic fields) | High | Quarterly | Good (pipe-delimited) |
| SIDJI/DJI | Limited (family ties only) | High (self-reported) | Upon filing | Poor (on-demand search) |
| ONPE Claridad | Unknown (blocked) | Unknown | Unknown | Unknown |
| JNE | Good (candidate data) | Medium (self-reported) | Per election | Medium |
| Contraloria Sanciones | Good (sanctioned persons) | High (official) | Periodic | Good (XLSX) |

### Forward-Compatibility Notes for Anti-Corruption Graph

#### Core Linkage Keys
```
ruc (11 digitos) → SUNAT Padron + SUNARP companies
partida_registral → SUNARP specific company record
dni → SIDJI/DJI declarations + JNE candidates
ocid → OCDS contracts + SEACE procedures
organizacion_politica_id → ONPE + JNE
```

#### Priority Linkages for Graph
1. **Company → Contracts:** SUNARP (partida/ruc) + OCDS (supplier_ruc)
2. **Representative → Company:** SUNARP copia literal + SIDJI family ties
3. **Donor → Party → Government contracts:** ONPE Claridad + OCDS + entity
4. **Sanctioned → Contract committee:** Contraloria Sanciones + SEACE committees

#### Patterns Supported
- `CONFLICT_OF_INTEREST_FAMILY` — SIDJI + SUNARP + OCDS
- `ELECTORAL_INVESTMENT_RETURN` — ONPE + OCDS + entity
- `GHOST_COMPANY` — SUNAT age/domicilio + OCDS
- `SANCTIONED_REPRESENTATIVE` — Contraloria + SUNARP + OCDS
- `COMMITTEE_BIAS` — SEACE/OECE committees + OCDS awards

---

## 9. Recommendations by Priority

### P0 (Already Implemented / Active)
- **SUNAT Padron:** Maintain collector; ensure bulk ZIP is processed routinely
- **OCDS Peru:** Continue as primary backbone
- **SEACE/OECE:** Execute `OeceCollector` to populate committees and suppliers
- **Contraloria Sanciones:** Run `SancionesCollector` to produce local data

### P1 (High Value, Needs Spec Before Implementing)
- **SIDJI/DJI:** Create spec for legal-safe on-demand lookup. Do not mass scrape. Use for case-specific investigation only.
- **ONPE Claridad:** Requires Playwright with XHR interception. Blocked by 403 currently; may need alternative URL or auth.
- **JNE Voto Informado + Plataforma:** Similar to ONPE — Angular SPA requires Playwright. Lower priority than ONPE for anti-corruption tracing.
- **SUNAT Consulta Multiple:** Form with CAPTCHA, semi-manual. Low priority vs. padron bulk.

### P2 (Manual-Assisted or Deferred)
- **SUNARP Personas Juridicas:** Good for case-specific company verification. Not for mass scraping. Use when specific company is identified from OCDS/SUNAT.
- **SUNARP SPRL:** Paid service for copia literal — use for detailed company record when needed (not batch).

### P3 (Out of Scope for MVP)
- **RCC:** Not public, not relevant
- **Poder Judicial:** Only firm sentences — manual only
- **Ministerio Publico:** Official communications only — manual only

---

## 10. Legal-Safe Language Notes

When using these sources for pattern detection in dossiers:

| Use | Language |
|---|---|
| Company won contract | "La empresa [name] fue adjudicataria del contrato [OCID]" |
| Representative appears in DJI | "Se identifico vinculo familiar declarado por [name]" |
| Company shows ghost pattern | "La empresa presenta senales de riesgo: registro reciente, domicilio compartido" |
| Donor-contribution pattern | "Se identifico aportacion de [company] a [party] en [year], previamente contratada por [entity]" |
| Sanctioned linked to contract | "La empresa [name] tiene representante con sancion vigente segun Contraloria" |

**Prohibited:** "corrupto", "robo", "mafioso", "culpable", "delincuente", "delito"

---

*Research completed 2026-05-17. Source catalog reference: `apps/scrapers/src/agenteperry/sources/catalog.py`. Scraping roadmap: `docs/SCRAPING_ROADMAP.md`.*
