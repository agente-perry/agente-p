# OSCE, Contraloria y RNP: Research Report for Anti-Corruption Data

**Date:** May 17, 2026  
**Author:** AgentePerry Research  
**Purpose:** TDR Scanner MVP - Supplier blacklists and sanctions data inventory

---

## Executive Summary

This report investigates Peruvian government sources for anti-corruption data, specifically:
- **OSCE/OECE** (Organismo Especializado para las Contrataciones Públicas Eficientes) - procurement oversight
- **Contraloría General de la República** - state audit
- **RNP** (Registro Nacional de Proveedores y Contratistas) - supplier registry

**Key Finding:** OSCE publishes extensive procurement data via SEACE and Pentaho BI portals, but **direct blacklist/inhabilitado data requires scraping Tribunal resolutions**. The RNP does NOT expose a public blacklist API. Contraloria was unreachable during research.

---

## 1. OSCE / OECE (Organismo Especializado para las Contrataciones Públicas Eficientes)

### 1.1 Overview

**Main Portal:** https://www.gob.pe/oece (redirects from older osce.gob.pe)

The organization has evolved:
- Previously: **OSCE** (Organismo Supervisor de las Contrataciones del Estado)
- Currently: **OECE** (Organismo Especializado para las Contrataciones Públicas Eficientes) per Ley N° 32069

### 1.2 Procurement Data Available

#### SEACE (Sistema Electrónico de Contrataciones del Estado)

**Public Search Interface:**
- URL: https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml
- Provides search for:
  - Procedimientos de selección (selection procedures)
  - Órdenes de compra y servicio
  - Expresiones de interés
  - Anuncios de contratación futura
  - Condiciones de contratación
- **Export to Excel** available for most searches
- Data from 2004-present
- **Status:** Active, working (tested successfully)

#### CONOSCE - Sistema de Inteligencia de Negocios

**Pentaho-based BI Portal:**
- URL: https://bi.seace.gob.pe/pentaho/api/repos/%3Apublic%3Aportal%3Adatosabiertos.html/content?userid=public&password=key
- Provides:
  - Plan Anual de Contrataciones (PAC)
  - Procedimientos Adjudicados (convocatorias y contratos)
  - Proveedores Adjudicados
  - Datos Complementarios (entidades, órdenes de compra, miembros comité)
- **Update frequency:** Monthly within first 5 days
- **Data range:** From 2018
- **Status:** Returns "CONOSCE - DATOS ABIERTOS" page - needs further investigation

### 1.3 Proveedores Sancionados / Inhabilitados

#### Tribunal de Contrataciones del Estado - Resoluciones

**URL:** https://www.gob.pe/institucion/oece/colecciones/716-resoluciones-del-tribunal-de-contrataciones-del-estado

**Content:**
- 61,229+ resoluciónes (as of research date)
- Contains "Procedimiento administrativo sancionador" against suppliers
- Each resolución available as PDF
- Searchable by keyword, date
- Paginated (2450 pages)

**Sample entries observed:**
```
- Resolución N.° 1820-2026-TCP-S6: Procedimiento administrativo sancionador seguido al proveedor Confecciones Textiles BF Sport E.I.R.L.
- Resolución N.° 2919-2025-TCE-S1: Procedimiento administrativo sancionador contra CORPORACION EMPRESARIAL ZASOJARI S.A.C.
```

**Scraping viability:** HIGH
- Paginated list with PDF links
- Pattern: `/institucion/oece/normas-legales/{ID}-{number}` 
- Direct PDF links available

#### Tribunal de Contrataciones Públicas - Resoluciones (New system)

**URL:** https://www.gob.pe/institucion/oece/colecciones/68030-resoluciones-del-tribunal-de-contrataciones-publicas

**Content:**
- 8,611+ resoluciónes from the new TCP system
- Updated to May 2026

#### Pronunciamientos

**URL:** https://www.gob.pe/institucion/oece/colecciones/2033-pronunciamientos-del-osce

**Content:**
- 6,026+ pronunciamientos from Dirección de Supervisión y Asistencia Técnica
- Not sanctions directly, but supervisory observations
- PDF format

### 1.4 Buscador de Proveedores Adjudicados (CONOSCE)

**URL:** https://bi.seace.gob.pe/pentaho/api/repos/:public:ANTECEDENTES_PROVEEDORES:ANTECEDENTES_PROVEEDORES.wcdf/generatedContent?userid=public&password=key

**Features:**
- Query by DNI or RUC
- Shows:
  - Vigencias en RNP (registration status, NOT habilitation/inhibition status)
  - Composición de accionistas/representantes legales
  - Buenas pro obtenidas
  - Órdenes de compra y servicios recibidos
- **Data from 2008-present**
- **Update:** Weekly
- **IMPORTANT NOTE:** "no indica las inhabilitaciones" - does NOT show inhibitions/blacklists

### 1.5 Ficha Única del Proveedor

**URL:** https://apps.oece.gob.pe/perfilprov-ui/

**Status:** Transport error during research - may require specific browser or authentication

### 1.6 RNOSC / Registro Nacional de Proveedores

**RNP Portal (Bienes y Servicios):**
- URL: http://www.rnp.gob.pe/Constancia/RNP_Constancia/ConsultaRuc.asp
- **Requires CAPTCHA** for RUC verification
- Shows registration status only, NOT sanctions

**RNP Portal (Ejecutores y Consultores):**
- URL: https://www.rnp.gob.pe/consulta//
- **Requires CAPTCHA**
- Query by region, year, trámite número

**RNP Resoluciones (Nulidades):**
- URL: https://www.rnp.gob.pe/webresolucion/default.asp
- Searchable by:
  - Tipo: Nulidad, Recnsideración de Nulidad
  - Año: 2013-2026
  - Mes
  - Búsqueda por: Razón Social, RUC, Nro. Resolución
- **Requires CAPTCHA**

### 1.7 Medidas Cautelares

**URL:** https://portal.osce.gob.pe/osce/medidas-cautelares

**Status:** Transport error during research

### 1.8 OSCe Data - APIs / Downloads

| Source | URL | Format | Auth Required |
|--------|-----|--------|---------------|
| Portal Datos Abiertos | https://bi.seace.gob.pe/pentaho/... | Pentaho/HTML | No (public key) |
| SEACE Public Buscador | https://prod2.seace.gob.pe/seacebus-uiwd-pub/ | JSF/EJB | No |
| Buscador Proveedores Adjudicados | https://bi.seace.gob.pe/pentaho/... | Tableau | No (public key) |
| Tribunal Resoluciones | https://www.gob.pe/institucion/oece/colecciones/716 | HTML/PDF | No |
| Pronunciamientos | https://www.gob.pe/institucion/oece/colecciones/2033 | HTML/PDF | No |
| RNP Resolution Search | https://www.rnp.gob.pe/webresolucion/default.asp | HTML | CAPTCHA |

---

## 2. Contraloria General de la República

### 2.1 Overview

**Main Portal:** https://www.contraloria.gob.pe/

**Status:** **UNREACHABLE** during research (transport error on all tested URLs)

### 2.2 Known Services

Based on prior documentation in the repo:

**Sanciones Collector (from SCRAPING_RADAR_IMPLEMENTATION_PLAN.md):**
- Collector: `SancionesCollector`
- Status: "playwright en catalogo, collector bulk CSV implementado"
- Source: "catalogo"
- Target: "Registro de sanciones"

This suggests Contraloria does publish sanction data, but direct URL access was not available during research.

### 2.3 Scraping Opportunities

Based on repo documentation, potential Contraloria data:
- **Sanciones** - Sanctions against persons/suppliers
- Possibly accessible via their public catalog

**Recommendation:** When Contraloria is accessible, search for:
- `/wps/portal/contraloria/` 
- `/contraloria.gob.pe/sanciones`
- `/contraloria.gob.pe/registros`
- Data.gov.pe platform (Plataforma Nacional de Datos Abiertos)

---

## 3. RNOSC / Registro Nacional de Proveedores y Contratistas

### 3.1 Public Registry Status

**Finding: NO direct public blacklist/blacklist API exists**

The RNP system provides:
- Registration status verification (Inscrito/No inscrito)
- Registration printouts (Constancia de inscripción)
- Resolution search for nullities

**Does NOT provide:**
- Inhabilitado/ sancionaddo status
- Blacklist data
- Active sanctions list

### 3.2 Available RNP Services

| Service | URL | Data Available |
|---------|-----|----------------|
| Consulta RUC (Bienes y Servicios) | http://www.rnp.gob.pe/Constancia/RNP_Constancia/ConsultaRuc.asp | Registration status |
| Consulta Estado Trámite (Ejecutores) | https://www.rnp.gob.pe/consulta// | Trámite status |
| Validación Constancia | http://www.rnp.gob.pe/Constancia/RNP_Constancia/ValidaCertificadoTodos.asp | Certificate validation |
| Resolución Nulidades | https://www.rnp.gob.pe/webresolucion/default.asp | Nulidad resolutions |

**All services require CAPTCHA**

---

## 4. Other Government Sources for Blacklists/Sanctions

### 4.1 Plataforma Nacional de Datos Abiertos

**URL:** https://www.datosabiertos.gob.pe/

**Statistics:**
- 20,244 datasets
- 15,302 resources
- 4,547 datasets
- 366 entities

**Search tags relevant to sanctions:**
- "Transparencia" (392)
- "Gobernabilidad" (116)
- "Poder ejecutivo" (86)

**Format availability:**
- CSV (2,169)
- XLSX (1,954)
- JSON (60)
- PDF (642)

### 4.2 Gob.pe Access to Information

**URL:** https://www.gob.pe/9232-organismo-supervisor-de-las-contrataciones-del-estado-solicitar-acceso-a-la-informacion-publica-del-organismo-supervisor-de-las-contrataciones-del-estado-osce

Formal access to information request possible via:
- Online: https://apps.osce.gob.pe/mesa-partes-digital/
- Email: cajaprincipal@oece.gob.pe

### 4.3 Declaraciones Juradas de Intereses (DJIC)

**URL:** https://appdji.contraloria.gob.pe/DJIC/ConsultaPublicaDJICRUC.aspx?ruc=20419026809

**Note:** This is Contraloria's DJI system - requires RUC parameter

---

## 5. Scraping Viability Assessment

### 5.1 High Priority Sources

| Source | URL Pattern | scraping Method | Difficulty |
|--------|-------------|-----------------|------------|
| Tribunal Resoluciones (OLD) | `/institucion/oece/normas-legales/*` | Pagination + PDF download | Medium |
| Tribunal Resoluciones (New) | `/institucion/oece/normas-legales/*` | Pagination + PDF download | Medium |
| Pronunciamientos | `/institucion/oece/informes-publicaciones/*` | Pagination + PDF download | Medium |
| SEACE Buscador | prod2.seace.gob.pe | POST form + Excel export | Medium |

### 5.2 Medium Priority Sources

| Source | URL Pattern | scraping Method | Difficulty |
|--------|-------------|-----------------|------------|
| RNP Resolution Search | rnp.gob.pe/webresolucion | POST + CAPTCHA | High |
| CONOSCE BI | bi.seace.gob.pe | Pentaho API | Medium |

### 5.3 Low Priority (Technical Barriers)

| Source | Issue |
|--------|-------|
| RNP RUC Consulta | CAPTCHA |
| Ficha Única Proveedor | App transport error |
| Contraloria Portal | Unreachable |

---

## 6. Recommendations for Sanctions/Blacklist Data Collection

### 6.1 Primary Recommendation: Tribunal Resoluciones

**Rationale:** Most direct source of supplier sanctions

**Approach:**
1. Scrape paginated list from: https://www.gob.pe/institucion/oece/colecciones/716-resoluciones-del-tribunal-de-contrataciones-del-estado
2. Extract PDF links from each resolución entry
3. Parse PDFs for:
   - Company name (razón social)
   - RUC
   - Sanction type (multa, inhabilitación, etc.)
   - Duration (if applicable)
   - Resolution number and date
4. Store structured data in `tdr_sanctions` table

**Data Model:**
```sql
tdr_sanctions (
  id, resolution_number, resolution_date,
  supplier_name, supplier_ruc,
  sanction_type, sanction_duration,
  cause, source_url, pdf_path,
  created_at
)
```

### 6.2 Secondary: SEACE Contractual Data

**Rationale:** Cross-reference with sanctioned suppliers

**Approach:**
1. Use SEACE Excel exports for contract awards
2. Cross-reference with Tribunal sanctions list
3. Flag contracts with sanctioned suppliers (for risk scoring)

### 6.3 Tertiary: Buscador Proveedores Adjudicados

**Rationale:** Historical company relationships (shareholders, representatives)

**Note:** Does NOT show sanctions but helps establish:
- Corporate networks
- Beneficial ownership
- Contract history

### 6.4 Future: Contraloria Sanciones

When accessible, the `SancionesCollector` mentioned in repo documentation suggests Contraloria publishes sanction data. Priority should increase when:
1. Portal becomes accessible
2. `SancionesCollector` implementation details are reviewed

---

## 7. Confirmed Data Sources Summary

### 7.1 URLs and Data Formats

| Category | Source | URL | Format |
|----------|--------|-----|--------|
| Procurement Procedures | SEACE Buscador | https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml | HTML + Excel export |
| Supplier Awards | CONOSCE | https://bi.seace.gob.pe/pentaho/api/repos/:public:ANTECEDENTES_PROVEEDORES:ANTECEDENTES_PROVEEDORES.wcdf | Tableau |
| Open Data | CONOSCE | https://bi.seace.gob.pe/pentaho/api/repos/%3Apublic%3Aportal%3Adatosabiertos.html | Pentaho |
| Tribunal Sanctions (Old) | OECE | https://www.gob.pe/institucion/oece/colecciones/716-resoluciones-del-tribunal-de-contrataciones-del-estado | HTML + PDF |
| Tribunal Sanctions (New) | OECE | https://www.gob.pe/institucion/oece/colecciones/68030-resoluciones-del-tribunal-de-contrataciones-publicas | HTML + PDF |
| Pronunciamientos | OECE | https://www.gob.pe/institucion/oece/colecciones/2033-pronunciamientos-del-osce | HTML + PDF |
| RNP Status | RNP | http://www.rnp.gob.pe/Constancia/RNP_Constancia/ConsultaRuc.asp | HTML + CAPTCHA |
| RNP Resolutions | RNP | https://www.rnp.gob.pe/webresolucion/default.asp | HTML + CAPTCHA |
| Public Data Portal | datosabiertos.gob.pe | https://www.datosabiertos.gob.pe/ | CKAN API |

### 7.2 NOT Available (Gaps)

- Public RNP blacklist/inhabilitado registry
- Direct OSCe API for sanctions
- Contraloria sanctions accessible via web scraping

---

## 8. Legal-Safe Language Guidelines

When documenting sanctions data, use:
- "presenta senales de riesgo" (presents risk signals)
- "merece revision" (deserves review)
- "requiere explicacion" (requires explanation)
- "patron atipico" (atypical pattern)

Avoid:
- "robo", "corrupto", "mafioso", "culpable", "delincuente", "delito"

All evidence must include:
- Textual citation
- Page number
- Source reference

---

## 9. Next Steps

1. **SPEC-0004** should specify Tribunal resoluciones as primary sanctions source
2. Implement pagination scraper for Tribunal resoluciones (old and new)
3. Create PDF parser for resolución content
4. Establish RUC/name extraction from resolución text
5. Monitor Contraloria accessibility for future integration

---

## Appendix: URLs Catalog

### OSCE/OECE
```
Main:                https://www.gob.pe/oece
SEACE Buscador:      https://prod2.seace.gob.pe/seacebus-uiwd-pub/buscadorPublico/buscadorPublico.xhtml
CONOSCE Datos:       https://bi.seace.gob.pe/pentaho/api/repos/%3Apublic%3Aportal%3Adatosabiertos.html/content?userid=public&password=key
CONOSCE Proveedores: https://bi.seace.gob.pe/pentaho/api/repos/:public:ANTECEDENTES_PROVEEDORES:ANTECEDENTES_PROVEEDORES.wcdf/generatedContent?userid=public&password=key
Tribunal Old:        https://www.gob.pe/institucion/oece/colecciones/716-resoluciones-del-tribunal-de-contrataciones-del-estado
Tribunal New:        https://www.gob.pe/institucion/oece/colecciones/68030-resoluciones-del-tribunal-de-contrataciones-publicas
Pronunciamientos:    https://www.gob.pe/institucion/oece/colecciones/2033-pronunciamientos-del-osce
RNP Bienes:          http://www.rnp.gob.pe/Constancia/RNP_Constancia/ConsultaRuc.asp
RNP Ejecutores:      https://www.rnp.gob.pe/consulta//
RNP Resoluciones:    https://www.rnp.gob.pe/webresolucion/default.asp
Acceso Info:         https://apps.osce.gob.pe/mesa-partes-digital/
```

### Contraloria
```
Main:                https://www.contraloria.gob.pe/ (UNREACHABLE)
DJIC:                https://appdji.contraloria.gob.pe/DJIC/ConsultaPublicaDJICRUC.aspx
```

### National Data Portal
```
Main:                https://www.datosabiertos.gob.pe/
```
