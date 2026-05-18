# Scraping Roadmap — AgentePerry

> Mapa vivo de todas las fuentes de datos, su estado, columnas,
> relaciones cruzadas y siguiente paso concreto.
>
> **Última actualización:** 2026-05-16
> **Fuentes registradas:** 20 | **Collectors implementados:** 4 | **Pipelines end-to-end:** 2 (ocds_peru, sunat_padron) | **Data en disco:** OCDS 2026 (66,751 releases), SUNAT fixture (25 filas), TDR Discovery (2,565 Salud + 99 Ambiente, 3 PDFs descargados)

---

## Índice

1. [Modelo de trazabilidad](#1-modelo-de-trazabilidad)
2. [Inventario de data cruda](#2-inventario-de-data-cruda)
3. [Fuentes implementadas con detalle](#3-fuentes-implementadas)
4. [Fuentes pendientes](#4-fuentes-pendientes)
5. [Mapa de relaciones cruzadas](#5-mapa-de-relaciones-cruzadas)
6. [Diagrama de flujo completo](#6-diagrama-de-flujo)
7. [Checklist de desarrollo por fuente](#7-checklist-de-desarrollo)
8. [Próximos pasos](#8-próximos-pasos)

---

## 1. Modelo de trazabilidad

```
Fuente pública
  → archivo_raw  (checksum SHA256, fecha, tamaño)
  → records.jsonl  (source_records normalizado)
  → source_records (Postgres)
  → graph.json  (source_entities + source_relationships)
  → source_entities (Postgres)
  → source_relationships (Postgres)
  → audit.json  (resumen de corrida)
  → evidence_flags  (señales con evidencia)
```

### Contrato común — todos los scrapers producen este shape

```python
CollectionResult(
    source_code=str,          # identificador de fuente
    external_id=str,          # clave única del registro en la fuente
    raw_data=dict,            # JSON original completo
    parsed_data=dict,         # campos normalizados adicionales
    raw_path=str,            # ruta al archivo raw en data/raw/
    checksum=str,            # SHA256 del raw_path
    content_type=str,        # MIME type
    record_type=str,         # contract | company | person | sanction | ...
    period_year=int,
    region=str,
    entity_name=str,         # nombre de la entidad compradora
    entity_ruc=str,         # RUC de la entidad (11 dígitos)
    supplier_name=str,      # nombre del proveedor
    supplier_ruc=str,       # RUC del proveedor (11 dígitos)
    monto=float,             # monto del contrato
    fecha=date,
    source_url=str,          # URL original del registro
    page_number=int,         # página de referencia (si aplica)
    evidence_quote=str,     # cita textual de la señal
    fetched_at=datetime,     # cuándo se capturó
)
```

### Artefactos por corrida

```
data/raw/<source_code>/
  <run_id>/
    raw.ext              # archivo original bajado
    records.jsonl       # registros normalizados
    graph.json          # entidades y relaciones (si aplica)
    audit.json          # resumen de la corrida
```

---

## 2. Inventario de data cruda

### 2.1 OCDS Peru 2026

| Propiedad | Detalle |
|---|---|
| **Archivo** | `data/raw/ocds/2026.jsonl.gz` |
| **Tamaño** | ~74 MB comprimido |
| **Registros** | 66,751 releases |
| **Formato** | JSONL.gz — un JSON OCDS por línea |
| **可用性** | 100% de releases contienen `parties` con RUC en `additionalIdentifiers` |
| **Collector** | `apps/scrapers/src/agenteperry/collectors/ocds.py` ✅ Implementado |
| **Problema conocido** | Ninguno crítico. 42% de registros sin `supplier_ruc` (requiere match con SUNAT). Multi-contract edges: 18,776 contratos adicionales entre pares ya existentes se deduplican en grafo. |

#### Columnas top-level disponibles en cada release OCDS

| Columna OCDS | Frecuencia | Contenido |
|---|---|---|
| `id` | 100% | identificador único del release |
| `ocid` | 100% | Open Contracting ID |
| `tag` | 100% | tipo de release: tender, award, contract… |
| `date` | 100% | fecha del release |
| `buyer` | 100% | `{id, name}` — id es CONSUCODE, NO RUC |
| `tender` | 100% | `{id, title, value, procurementMethodDetails…}` |
| `parties` | 100% | array de participantes; contiene RUC real |
| `awards` | 78% | awards con `suppliers`, `value.amount`, `date` |
| `contracts` | 73% | contratos con `value.amount`, `awardID`, `period`, `documents` |
| `planning` | 100% | información de planificación |
| `sources` | 100% | URLs fuente |
| `publishedDate` | 100% | fecha de publicación |
| `initiationType` | 100% | tipo: tender |
| `dataSegmentation` | 100% | metadatos de segmentación |

#### Cómo obtener RUC de parties (CRÍTICO —fix pendiente)

```python
# El buyer.id viene como PE-CONSUCODE-1055 — NO es RUC
buyer.id  # "PE-CONSUCODE-1055"  ← WRONG para grafo

# El RUC real está en parties[].additionalIdentifiers
for party in parties:
    for aid in party.get("additionalIdentifiers", []):
        if aid.get("scheme") == "PE-RUC":
            ruc = aid.get("id")  # "20147704373"  ← CORRECTO

# También se puede usar awards[].suppliers[].id
# que también viene como PE-RUC-XXXXXXX
```

#### contracts vs awards — usar contracts para monto

```python
# awards.value.amount puede estar vacío
awards[0].get("value", {}).get("amount")  # puede ser None

# contracts tiene el monto real del contrato firmado
contracts[0].get("value", {}).get("amount")  # 84099.67 PEN  ← CORRECTO
```

#### Campos extraídos de OCDS (estado post-fix)

| Campo | Extraído | Fuente |
|---|---|---|
| `entity_ruc` | ✅ 100% | `parties[role=buyer].additionalIdentifiers[scheme=PE-RUC]` |
| `supplier_ruc` | ✅ 64.7% | `parties[role=supplier].identifier[scheme=PE-RUC]` |
| `region` | ✅ 100% | `parties[role=buyer].address.department` |
| `monto` | ✅ 100% | `contracts[0].value.amount` o `awards.value.amount` |
| `procedure_type` | ✅ | `tender.procurementMethodDetails` |
| `contracts_count` | ✅ | `len(contracts)` |
| `committee_members` | ⏳ Pendiente | `tender.tenderers` |
| `tender.description` | ⏳ Pendiente | `tender.description` |

---

### 2.2 TDR Manuales

| Propiedad | Detalle |
|---|---|
| **Archivo** | `data/manual_tdrs/metadata.csv` |
| **Registros** | 2 TDRs de prueba |
| **Formato** | CSV |

#### Columnas

| Columna | Ejemplo | Notas |
|---|---|---|
| `external_id` | `TDR-001` | clave primaria |
| `title` | `Mantenimiento de Redes de Agua` | nombre del servicio |
| `entity_name` | `Sedapal` | entidad que pública |
| `source_url` | `https://source.com/1` | URL de origen |
| `file_url` | `https://file.com/1` | URL del PDF |
| `procedure_code` | `AS-001-2024` | código de procedimiento |
| `sector` | `Vivienda` | sector |
| `region` | `Lima` | región |
| `district` | `Lima` | distrito |
| `publication_date` | `2024-05-01` | fecha de publicación |
| `estimated_value` | `50000.0` | valor estimado |
| `local_path` | `dummy.pdf` | ruta local del PDF |

> **Nota:** Los PDFs reales aún no están en disco. `local_path: dummy.pdf` es un placeholder.
> El pipeline real necesita: PDF → parsing → pages → chunks → flags.

---

## 3. Fuentes implementadas

### 3.1 `ocds_peru` ✅ Implementado + Pipeline Cerrado (2026-05-16)

```
Estado: pipeline end-to-end operativo — raw → records → DB → graph → chunks → audit
Última corrida: 2026-05-16 | 72,399 records | 33,284 entities | 92,138 relationships
```
✅ entity_ruc de parties[].additionalIdentifiers[scheme=PE-RUC]  (antes: buyer.id = CONSUCODE)
✅ supplier_ruc de parties[].identifier[scheme=PE-RUC] + additionalIdentifiers
✅ region de parties[].address.department
✅ monto de contracts[].value.amount cuando awards vacío
✅ Pipeline end-to-end: raw → records → DB → graph → chunks → audit
✅ 72,399 records en source_records
✅ 33,284 entities en source_entities (100% public_entity con RUC real)
✅ 92,138 unique relationships en source_relationships
✅ Produce records.jsonl + graph.json + audit.json
✅ Mapea a public_entity + company + GANO_CONTRATO/COMPRO_A
⚠️  supplier_ruc: 58.0% en corrida completa — resto requiere match con SUNAT
```

#### Auditoría corrida completa (66,751 releases → 72,399 records)

| Métrica | Valor |
|---|---|
| `total_records` | 72,399 |
| `contracts_count` | 55,457 |
| `procedures_count` | 16,942 |
| `with_entity_ruc` | 72,399 (100%) |
| `with_supplier_ruc` | 41,994 (58.0%) |
| `with_monto` | 72,391 (99.99%) |
| `with_region` | 72,399 (100%) |
| `entities_created` | 33,284 |
| `public_entities_with_ruc` | 2,709 (100%) |
| `companies_with_ruc` | 20,496 (67.0%) |
| `relationships_mapped` | 110,914 |
| `relationships_upserted_unique` | 92,138 |
| `document_chunks_created` | 72,399 |

#### Record types producidos

```python
record_type = "contract"   # cuando hay awards
record_type = "procedure"  # cuando no hay awards (tender only)
```

#### Relaciones de grafo

```python
company --GANO_CONTRATO--> public_entity
public_entity --COMPRO_A--> company
```

---

### 3.2 `sunat_padron` ✅ Pipeline Cerrado con Enrichment (2026-05-16)

```
Estado: pipeline end-to-end operativo — raw → records → DB → graph → enrichment → audit
Última corrida (fixture): 2026-05-16 | 25 records | 25 entities | 0 relationships (company-only)
Última corrida (fixture+DB): 25 source_records, 25 source_entities, 25 companies enriched
Match rate OCDS con SUNAT: 7.86% (1,747 de 22,219 companies con RUC)
```

| Atributo | Detalle |
|---|---|
| **Prioridad** | P0 |
| **Tipo** | `bulk_download` |
| **URL** | `https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html` |
| **Data en disco** | `data/raw/sunat_padron/records.jsonl` (fixture), `data/raw/sunat_padron/graph.json`, `data/raw/sunat_padron/audit.json` |
| **Owner** | Anthony |
| **Collector** | `collectors/sunat.py` ✅ |
| **Enrichment** | `sync/loader.py::enrich_companies_from_sunat()` ✅ |
| **Audit** | `cli.py::_build_sunat_audit()` ✅ |
| **Aporte al modelo** | `company` entities con estado, condición, ubigeo; enrich OCDS companies |

#### Comando de corrida (fixture)

```bash
cd apps/scrapers
uv run agenteperry sources pipeline sunat_padron \
  --input tests/fixtures/sunat_padron_sample.txt \
  --limit 25
```

#### Comando de corrida (descarga real)

```bash
cd apps/scrapers
uv run agenteperry sources pipeline sunat_padron --limit 1000
```

#### Campos que produce

| Campo SUNAT | Mapeo |
|---|---|
| `ruc` | `entity_ruc` (11 dígitos) |
| `razon_social` | `entity_name` |
| `estado` | `parsed_data.estado` |
| `condicion` | `parsed_data.condicion` |
| `ubigeo` | `parsed_data.ubigeo`, `region` |
| `domicilio_fiscal` | `parsed_data.domicilio_fiscal` |

#### Estado del collector

```
✅ Implementado en collectors/sunat.py
✅ Pipeline end-to-end: collect → records → DB → graph → enrichment → audit
✅ Enrichment no destructivo: preserva display_name OCDS, agrega sunat_* metadata
✅ Fixture tests/fixtures/sunat_padron_sample.txt con 25 filas reales + encoding ISO-8859-1
✅ Audit específico SUNAT: _build_sunat_audit() con active_count, baja_count, no_habido_count, ocds_match_rate
✅ Steps 1–7 cerrados en cli.py::sources_pipeline para source_code == "sunat_padron"
⚠️  Data de descarga real no cargada aún (pendiente: descargar y correr padrón completo / limitado)
⚠️  Match rate actual bajo (7.86%) porque fixture tiene pocos RUC comunes con OCDS
```

#### Auditoría corrida completa (fixture — 25 registros)

| Métrica | Valor |
|---|---|
| `total_records` | 25 |
| `with_valid_ruc` | 25 (100%) |
| `with_name` | 25 (100%) |
| `with_estado` | 25 (100%) |
| `with_condicion` | 25 (100%) |
| `with_ubigeo` | 25 (100%) |
| `entities_created` | 25 |
| `relationships_created` | 0 |
| `companies_enriched` | 25 |
| `companies_unmatched` | 0 |
| `active_count` | 21 |
| `baja_count` | 4 |
| `no_habido_count` | 7 |
| `ocds_companies_total` | 30,600 |
| `ocds_companies_with_ruc` | 20,521 |
| `ocds_match_rate` | 7.86% |

#### Record types producidos

```python
record_type = "company"   # un company entity por registro SUNAT
```

#### Enrichment: cómo funciona

```python
# Pipeline ejecuta automáticamente Step 5 para sunat_padron:
# enrich_companies_from_sunat(records_jsonl, batch_size=500)
# 
# Lógica:
# 1. Lee source_records SUNAT con entity_ruc de 11 dígitos
# 2. Busca match en source_entities WHERE entity_type='company' AND canonical_id = RUC
# 3. Merge metadata: ocds_name (DISPLAY_NAME original), sunat_razon_social, sunat_estado, 
#    sunat_condicion, sunat_ubigeo, sunat_domicilio_fiscal, sunat_last_seen_at
# 4. Merge sources array: agrega "sunat_padron" sin duplicar
# 5. Batch UPDATE source_entities
```

---

### 3.3 `seace_oece` ✅ Implementado

| Atributo | Detalle |
|---|---|
| **Prioridad** | P0 |
| **Tipo** | `bulk_download` |
| **URL** | `https://bi.seace.gob.pe/pentaho/api/repos/…` |
| **Data en disco** | `data/raw/seace_oece/` (vacío — pendiente de corrida) |
| **Owner** | John |
| **Collector** | `collectors/seace.py` ✅, `collectors/oece_collector.py` ✅ |
| **Aporte al modelo** | Contratos oficiales, órdenes de compra, comités |

#### Categorías disponibles

```
pac | procedimientos | convocatorias | contratos
ordenes_compra | proveedores | entidades
comites | pronunciamientos | consorcios
```

#### Record types producidos

```python
record_type = "contract"
record_type = "purchase_order"
record_type = "committee_member"
```

#### Estado

```
✅ Collector implementado
⚠️  Sin corrida completa en data/raw/
⚠️  Sin upsert a source_records
```

---

### 3.4 `contraloria_sanciones` ✅ Implementado

| Atributo | Detalle |
|---|---|
| **Prioridad** | P0 |
| **Tipo** | `playwright` |
| **URL** | `https://www.gob.pe/institucion/contraloria/…` |
| **Data en disco** | `data/raw/contraloria_sanciones/` (vacío) |
| **Owner** | John |
| **Collector** | `collectors/sanciones.py` ✅ |
| **Aporte al modelo** | `person` + `sancion` entities, `TIENE_SANCION` relationships |

#### Campos que produce

| Campo | Mapeo |
|---|---|
| `dni` | `entity_ruc` (11 dígitos DNI) |
| `nombres` | `entity_name` |
| `tipo_sancion` | `parsed_data.tipo_sancion` |
| `vigencia` | `parsed_data.vigencia` |
| `entidad` | `parsed_data.entidad` |

#### Relaciones de grafo

```python
person --TIENE_SANCION--> sancion
person --MENCIONADO_EN--> public_entity  # si tiene vínculo a entidad
```

#### Estado

```
✅ Collector implementado
⚠️  Sin corrida en data/raw/
⚠️  Sin upsert a source_records
```

---

### 3.5 `ley_32069` 📋 Referencia

| Atributo | Detalle |
|---|---|
| **Prioridad** | P0 |
| **Tipo** | `reference` |
| **URL** | `https://www.gob.pe/institucion/oece/…` |
| **Collector** | No necesario — solo almacenamiento del PDF |
| **Aporte** | RAG legal para explicar señales, no es scraper transaccional |

---

## 4. Fuentes pendientes

| Código | Prioridad | Tipo | Owner | Estado |
|---|---|---|---|---|
| `sunat_multi_ruc` | P1 | form_scraping | Anthony | ⏳ Sin collector |
| `cgr_informes` | P1 | playwright | John | ⏳ Sin collector |
| `sidji_dji` | P1 | playwright | Miguel | ⏳ Sin collector |
| `mef_datos_abiertos` | P1 | ckan | Anthony | ⏳ Sin collector |
| `onpe_claridad` | P1 | playwright | Noelia | ⏳ Sin collector |
| `jne_voto_informado` | P1 | playwright | Noelia | ⏳ Sin collector |
| `jne_plataforma` | P1 | playwright | Noelia | ⏳ Sin collector |
| `congreso_leyes` | P1 | form_scraping | Miguel | ⏳ Sin collector |
| `ojo_publico_funes` | P1 | reference | John | 📋 Solo referencia |
| `open_contracting_memoria` | P1 | reference | Anthony | 📋 Solo referencia |
| `convoca_contrataciones` | P1 | form_scraping | Noelia | ⏳ Sin collector |
| `congreso_proyectos` | P2 | form_scraping | Miguel | ⏳ Sin collector |
| `sunarp_conoce` | P2 | manual | John | ⏳ Sin collector |
| `sunarp_sprl` | P3 | manual | John | ⏳ Sin collector |
| `sunarp_pj` | P2 | form_scraping | John | ⏳ Sin collector |
| `poder_judicial` | P3 | manual | Miguel | ⏳ Sin collector |
| `ministerio_publico` | P3 | manual | Miguel | ⏳ Sin collector |
| `convoca_pandemia` | P2 | form_scraping | Noelia | ⏳ Sin collector |

---

## 5. Mapa de relaciones cruzadas

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLAVES DE ENLACE CRUZADO                       │
│                                                                  │
│  entity_ruc (11 dígitos) → SUNAT Padron → company entity         │
│  supplier_ruc (11 dígitos) → SUNAT Padron → company state       │
│  entity_ruc → SEACE/OECE → contract detail + committee          │
│  supplier_ruc → SEACE/OECE → contract history + count           │
│  dni → Contraloria Sanciones → person + sancion                 │
│  entity_ruc → Contraloria Sanciones → entidad vinculada          │
│  ocid → SEACE codigo_proceso → cross-reference                  │
│  external_id → source_records → audit trail                      │
└──────────────────────────────────────────────────────────────────┘
```

### Claves de enlace por fuente

| Fuente | Clave primaria | Clave de enlace cruzado |
|---|---|---|
| OCDS Peru | `ocid` + `award_id` + `supplier_ruc` | `entity_ruc` → SUNAT, SEACE |
| SUNAT Padrón | `ruc` (11 dígitos) | `ruc` → valida cualquier entity_ruc |
| SEACE/OECE | `codigo_proceso`, `ruc_entidad`, `ruc_proveedor` | `ruc_entidad` → OCDS buyer, `ruc_proveedor` → SUNAT |
| Contraloría Sanciones | `dni`, `entidad` | `dni` → SIDJI DJI, `entidad` → entidad OCDS/SEACE |
| TDR | `external_id` | linked a `source_records` por `file_url` |
| Ley 32069 | `articulo` | RAG para explicar señales |

### Cómo enriquecen las fuentes

```
                    ┌─────────────────┐
                    │  OCDS  Peru     │ ← fuente base de contratos
                    │  entity_name    │
                    │  supplier_name  │
                    │  monto, fecha  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
     ┌────────────┐ ┌──────────────┐ ┌─────────────────┐
     │ SUNAT      │ │ SEACE/OECE   │ │ Contraloria     │
     │ Padron     │ │              │ │ Sanciones       │
     │            │ │              │ │                 │
     │ Valida:    │ │ Enriquece:   │ │ Agrega:        │
     │ RUC existe │ │ committee    │ │ dni vinculado   │
     │ estado     │ │ ruc_real     │ │ tipo sancion    │
     │ condicion  │ │ procedimiento│ │ vigencia        │
     │ ubigeo    │ │ orden_compra │ │ entidad         │
     └────────────┘ └──────────────┘ └─────────────────┘
```

---

## 6. Diagrama de flujo

### 6.1 Flujo de datos completo

```mermaid
flowchart TD
    subgraphFuentes[Fuentes públicas]
        OCDS[OCDS Peru 2026<br/>data/raw/ocds/2026.jsonl.gz]
        SUNAT[SUNAT Padrón<br/>ZIP descarga]
        SEACE[SEACE/OECE<br/>CSV/XLSX por categoría]
        CGR[Contraloría Sanciones<br/>Playwright SPA]
        TDR[TDR Manuales<br/>metadata.csv + PDF]
        LEY[Ley 32069<br/>PDF referencia]
    end

    subgraphCollectors[Collectors]
        OC[ocds.py<br/>flatten_ocds_release]
        SUN[sunat.py<br/>parse_padron]
        SEA[seace.py<br/>parse_oece]
        SAN[sanciones.py<br/>parse_sanciones]
    end

    subgraphRaw[Disco — data/raw]
        RAW_OCDS[data/raw/ocds/]
        RAW_SUNAT[data/raw/sunat_padron/]
        RAW_SEACE[data/raw/seace_oece/]
        RAW_SAN[data/raw/contraloria_sanciones/]
    end

    subgraphDB[Postgres]
        SR[source_records]
        SE[source_entities]
        SR2[source_relationships]
        SC[source_catalog]
        DC[document_chunks]
        DE[document_embeddings]
        EF[evidence_flags]
        TD[tdr_documents]
        TP[tdr_pages]
        TC[tdr_chunks]
        TF[tdr_flags]
    end

    subgraphAPI[API]
        DOS[GET /api/tdr/{id}<br/>dossier legal-safe]
        AUD[GET /api/contracts/audit<br/>auditoría]
        SEA[GET /api/search<br/>búsqueda]
    end

    OCDS --> OC
    SUNAT --> SUN
    SEACE --> SEA
    CGR --> SAN

    OC --> RAW_OCDS
    SUN --> RAW_SUNAT
    SEA --> RAW_SEACE
    SAN --> RAW_SAN

    RAW_OCDS -->|"records.jsonl"| SR
    RAW_SUNAT -->|"records.jsonl"| SR
    RAW_SEACE -->|"records.jsonl"| SR
    RAW_SAN -->|"records.jsonl"| SR

    RAW_OCDS -->|"graph.json"| SE
    RAW_OCDS -->|"graph.json"| SR2

    SR -->|"enriquecer"| SE
    SE -->|"relaciones"| SR2
    SR -->|"chunks"| DC
    DC -->|"embeddings"| DE
    SR -->|"evidence"| EF
    TDR --> TD
    TD --> TP
    TP --> TC
    TC --> TF

    SC -.->|"registro"| SR
    SE -.->|"explorar"| DOS
    SR2 -.->|"explorar"| DOS
    TF -.->|"flags"| DOS
    SR -.->|"auditar"| AUD
    DC -.->|"buscar"| SEA
```

### 6.2 Flujo de grafo

```mermaid
graph LR
    subgraphNodos[Nodos]
        PE[public_entity<br/>Entidad pública]
        CO[company<br/>Empresa/Proveedor]
        PERS[person<br/>Persona]
        SAN[sancion<br/>Sanción]
    end

    subgraphRels[Relaciones]
        GANO[GANO_CONTRATO<br/>empresa gana contrato<br/>con entidad]
        COMPRO[COMPRO_A<br/>entidad compra a<br/>empresa]
        MIEMBRO[MIEMBRO_COMITE<br/>persona es miembro<br/>de comité]
        SANCION[TIENE_SANCION<br/>persona tiene<br/>sanción]
        MENCION[MENCIONADO_EN<br/>persona mencionada<br/>en entidad]
    end

    PE -.->|"identifica por"| RUC_OCDS[entity_ruc]
    CO -.->|"identifica por"| RUC_SUNAT[supplier_ruc]
    RUC_OCDS -.->|"match"| RUC_SUNAT

    CO --> GANO
    GANO --> PE
    PE --> COMPRO
    COMPRO --> CO
    PERS --> MIEMBRO
    MIEMBRO --> PE
    PERS --> SANCION
    SANCION --> SAN
```

---

## 7. Checklist de desarrollo

### 7.1 `ocds_peru` — Completado ✅ (2026-05-16)

```
Estado: pipeline end-to-end operativo, trazable y auditable

✅ Fix: entity_ruc de parties[].additionalIdentifiers[scheme=PE-RUC] — 100%
✅ Fix: region de parties[].address.department — 100%
✅ Fix: monto de contracts[].value.amount cuando awards vacío
✅ Agregar: supplier_ruc de parties[].identifier y additionalIdentifiers — 58.0%
✅ Correr pipeline completo: collect → records.jsonl → source_records (Postgres)
✅ Upsert: source_entities + source_relationships (Postgres)
✅ Generar audit.json
✅ Contar: 72,399 records, 41,994 with supplier_ruc, 72,391 with monto, 72,399 with ruc
✅ Test: 53 tests pasando (incl. 2 tests de pipeline audit)
✅ Verificar: canonical_id = RUC real (11 dígitos) en source_entities
✅ Documentar: columnas extraídas vs faltantes
⚠️ Pendiente: extraer tenderers como committee_members
```

### 7.2 `sunat_padron` — Completado ✅ (2026-05-16)

```
Estado: pipeline end-to-end operativo con enrichment no destructivo y audit SUNAT específico

✅ Correr descarga del ZIP desde fuente (o usar fixture)
✅ Guardar raw en data/raw/sunat_padron/ (fixture: tests/fixtures/sunat_padron_sample.txt)
✅ Parsear TXT pipe-delimited ISO-8859-1
✅ Generar records.jsonl con record_type=company
✅ Upsert a source_records
✅ Generar audit.json con métricas SUNAT: active_count, baja_count, no_habido_count, ocds_match_rate
✅ Verificar: entity_ruc 11 dígitos en ≥ 99% de registros (fixture: 100%)
✅ Verificar: estado y condición extraídos (fixture: 100%)
✅ Enriquecer: companies de OCDS con estado SUNAT (merge no destructivo)
✅ Hook pipeline: cli.py::sources_pipeline ejecuta enrichment automáticamente para source_code == "sunat_padron"
✅ Fixture: 25 filas reales con encoding ISO-8859-1 (Ñ, tildes, acentos)
✅ Test: test_sunat_pipeline.py (8 tests) + test_sunat_enrichment.py (6 tests)
✅ Documentar: campos disponibles vs schema + enrichment flow
⚠️ Pendiente: descarga real de padrón 14.5M y corrida limitada / completa
⚠️ Pendiente: match rate real con OCDS (actual: 7.86% porque fixture pequeño)
```

### 7.3 `seace_oece` — Completar

```
□ Correr descarga de CSVs por categoría prioritaria:
  - procedimientos (contratos)
  - entidades
  - proveedores
  - comites
□ Guardar raw en data/raw/seace_oece/
□ Generar records.jsonl con record_type correcto
□ Upsert a source_records
□ Generar audit.json
□ Contar: total, con ruc_entidad, con ruc_proveedor, con monto
□ Verificar: mapeo correct a public_entity + company
□ Agregar: committee_members como record_type=committee_member
□ Enriquecer: contratos OCDS con codigo_proceso SEACE
□ Test: 10 registros de cada categoría
□ Documentar: categorías disponibles y campos
```

### 7.4 `contraloria_sanciones` — Completar

```
□ Implementar Playwright intercept de XLSX
□ Guardar raw en data/raw/contraloria_sanciones/
□ Generar records.jsonl con record_type=sanction
□ Upsert a source_records
□ Generar audit.json
□ Contar: total, con dni, con entidad
□ Verificar: mapeo a person + sancion + TIENE_SANCION
□ Verificar: vigencia correcta (vigente/vencido)
□ Test: match de dni con SIDJI si disponible
□ Documentar: campos disponibles
```

### 7.5 TDR Scanner — Completar

```
□ Obtener PDFs reales (no dummy.pdf)
□ Correr extract_pdf_pages con PyMuPDF
□ Persistir tdr_pages en Postgres
□ Correr chunk_pages
□ Persistir tdr_chunks en Postgres
□ Detectar flags con detect_flags_in_pages
□ Persistir tdr_flags en Postgres
□ GET /api/tdr/{id} enriquecido con metadata completa
□ Test: payload legal-safe con risk_score y questions
□ Contar: pages extraídas, chunks, flags detectados
□ Documentar: payload de ejemplo
```

### 7.6 Dashboard de auditoría — Nuevo

```
□ Crear endpoint GET /api/sources/audit
□ Mostrar por source_code: total records, checksum coverage, missing fields
□ Mostrar por collector: implementado o pendiente
□ Incluir: last_run, records_count, entity_count, rel_count
□ Incluir: quality metrics (% con supplier, % con monto, % con ruc)
□ Frontend: tabla de fuentes con estado de pipeline
```

---

## 8. Próximos pasos

### Inmediato (esta semana)

**Paso 1: Cerrar OCDS Peru** ✅ HECHO

```bash
# Pipeline completo ejecutado:
cd apps/scrapers
uv run agenteperry sources pipeline ocds_peru \
  --input data/raw/ocds/2026.jsonl.gz

# Resultado:
- 72,399 source_records (55,457 contracts + 16,942 procedures)
- 33,284 source_entities (2,709 public_entities con RUC real + 30,575 companies)
- 92,138 unique relationships (GANO_CONTRATO + COMPRO_A)
- 72,399 document_chunks
- audit.json generado con métricas completas
- 53 tests pasando
```

**Paso 2: Enriquecimiento cruzado SUNAT** ✅ HECHO

```bash
# Pipeline con fixture (smoke test sin descargar 200MB)
cd apps/scrapers
uv run agenteperry sources pipeline sunat_padron \
  --input tests/fixtures/sunat_padron_sample.txt \
  --limit 25

# Pipeline con descarga real (limitado para dev)
uv run agenteperry sources pipeline sunat_padron --limit 1000

# Resultado (fixture):
- 25 source_records (record_type=company)
- 25 source_entities (canonical_id = RUC 11 dígitos)
- 25 companies enriched con metadata SUNAT
- 21 ACTIVO / 4 BAJA / 7 NO HABIDO
- Enrichment no destructivo: display_name OCDS preservado; metadata.ocds_name + metadata.sunat_razon_social coexisten
- audit.json generado con métricas SUNAT específicas
- 69 tests pasando (incl. 8 tests de pipeline SUNAT)

# Match rate OCDS → SUNAT (fixture muestra 7.86%; subirá con padrón real)
```

**Paso 3: TDR Discovery — Salud + Ambiente/Minería** ✅ HECHO (2026-05-16)

```bash
# Filtro de contratos OCDS por sectores priorizados
cd apps/scrapers
uv run python src/agenteperry/discovery/tdr_discovery.py

# Resultado:
- 2,566 contratos Salud 2024-2025 (ESSALUD, MINSA, Hospitales, INSN)
- 99 contratos Ambiente/Minería 2024-2025 (ANA, SERNANP, MINAM)
- data/filtered/salud_2024_2025.jsonl
- data/filtered/ambiente_2024_2025.jsonl
- data/tdr_recon/recon_20_processes.csv (20 procesos muestreados)
- docs/TDR_DISCOVERY_REPORT.md

# TDRs descargados manualmente (sin scraping masivo):
- data/tdrs/salud/bases_admin_1064372.rar (8.4MB, ESSALUD)
- data/tdrs/salud/bases_integradas_1147660.pdf (36.9MB, 143p, PNIS)
- data/tdrs/ambiente/bases_admin_1307_116.pdf (649KB, 23p, MML)

# Hallazgo clave: 100% de muestra tiene URLs directas a documentos SEACE
# URLs del tipo: https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=<UUID>
# No requiere login, captcha ni paywall
```

**Paso 4: TDR Downloader v1** — SPEC-0010 código + descarga real ✅

```
Spec: specs/active/SPEC-0010-tdr-downloader/spec.md
Estado:
  - Activity 4.1 validada por Ruta B (JSONL enriquecido con tender.documents[])
  - 5 descargas HTTP exitosas Salud, 5 Ambiente/Minería
  - No Playwright, no scraping HTML, no descarga masiva

CLI:
  agenteperry tdr download --input ../../data/filtered/salud_2024_2025_with_documents.jsonl --sector salud --limit 5 --max-docs 1
  agenteperry tdr download --input ../../data/filtered/ambiente_2024_2025_with_documents.jsonl --sector ambiente --limit 5 --max-docs 1

Módulo: apps/scrapers/src/agenteperry/tdr/downloader.py
Fuente: raw_data->tender->documents[] en source_records (sin scraping SEACE)
Output: data/tdrs/<sector>/<ocid>/<filename> + upsert tdr_documents
```

**Paso 4.2: PDF Usability Gate** ✅ HECHO

```bash
cd apps/scrapers
uv run agenteperry tdr audit-pdfs --base ../../data/tdrs

# Resultado inicial:
- total_files: 13
- pdf_files: 8
- pdf_available: 3
- pdf_partial: 0
- pdf_needs_ocr: 5
- archives_pending: 5
- data/tdrs/pdf_usability_report.csv
- data/tdrs/pdf_usability_audit.json

# Decisión:
# Ambiente tiene PDFs usables.
# Salud requería hunt dirigido.
```

**Paso 4.3: Targeted Salud Digital PDF Hunt** ✅ HECHO

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

# Resultado:
- total_candidates_considered: 2
- attempted_downloads: 1
- usable_found: 1
- stopped_early: true
- first_usable_path: data/tdrs/salud/ocds_dgv273_seacev3_988512/pliego_de_absolucion_de_consultas_y_observaciones_6faab297_cfd6_4448_a65a_d8bf646ead81.pdf
- coverage: 100%, pages_with_text: 212
```

**Paso 5: Golden Set Real Analysis** (SIGUIENTE)

```bash
# Parseo PyMuPDF → pages → chunks → flags
# Validar pipeline TDR end-to-end con PDFs reales que tengan texto digital usable

# Inputs recomendados:
- Salud usable: data/tdrs/salud/ocds_dgv273_seacev3_988512/pliego_de_absolucion_de_consultas_y_observaciones_6faab297_cfd6_4448_a65a_d8bf646ead81.pdf
- Ambiente usable 1: data/tdrs/ambiente_mineria/ocds_dgv273_seacev3_1157442/pliego_de_absolucion_de_consultas_y_observaciones_bf3db732_667d_4ea3_97ce_580f534727a0.pdf
- Ambiente usable 2: data/tdrs/ambiente/bases_admin_1307_116.pdf
```

**Paso 6: SUNAT Padrón — descarga real y hook pipeline** (PAUSADO temporalmente)

```bash
# SUNAT enrichment ya funciona con fixture (SPEC-0008 completo)
# Se reactiva después de validar TDR pipeline con 5 PDFs reales
# Task: descargar padrón limitado (--limit 1000) y correr enrichment completo
```

**Paso 7: SEACE/OECE por categorías prioritarias** (POSTERIOR)

```bash
# Categorías P0: procedimientos, contratos, ordenes_compra
# Cerrar pipeline end-to-end con los mismos 7 steps de OCDS/SUNAT
agenteperry sources pipeline seace_oece --category procedimientos --year 2026
```

### Corto plazo (2-3 semanas)

```
✅ TDR Downloader v1: batch download desde URLs SEACE en raw_data (SPEC-0010)
✅ PDF Usability Gate: clasificar PDFs available/partial/needs_ocr
✅ Targeted Salud Digital PDF Hunt: encontrar 1 PDF Salud usable
□ TDR Pipeline: parse → pages → chunks → flags con PDFs usables
□ SUNAT: reactivar descarga real + hook pipeline después de TDR validado
□ SEACE: correr categorías prioritarias + upsert (después de TDR)
□ Contraloria: Playwright + parse + upsert (después de SEACE)
□ Dashboard: endpoint /api/sources/audit
```

### Medio plazo (1-2 meses)

```
□ Enriquecimiento cruzado: OCDS + SUNAT + SEACE
□ evidence_flags: generar señales legal-safe con evidencia
□ Grafo completo: public_entity + company + person + sancion
□ RAG legal: Ley 32069 indexada para explicar señales
□ Dashboard web: fuentes, contratos, grafo, dossier TDR
```

---

## Anexo: SQL de auditoría rápida

```sql
-- Por fuente: calidad de source_records
SELECT
    sc.source_code,
    COUNT(sr.id) AS total_records,
    COUNT(DISTINCT sr.external_id) AS unique_external_ids,
    COUNT(DISTINCT sr.entity_ruc) FILTER (WHERE sr.entity_ruc ~ '^[0-9]{11}$') AS with_valid_ruc,
    COUNT(DISTINCT sr.supplier_ruc) FILTER (WHERE sr.supplier_ruc ~ '^[0-9]{11}$') AS with_supplier_ruc,
    COUNT(sr.monto) FILTER (WHERE sr.monto > 0) AS with_monto,
    COUNT(sr.fecha) AS with_fecha,
    COUNT(DISTINCT sr.raw_path) AS with_raw_path,
    COUNT(DISTINCT sr.checksum) AS with_checksum,
    COUNT(sr.evidence_quote) AS with_evidence
FROM source_catalog sc
LEFT JOIN source_records sr ON sr.source_id = sc.id
GROUP BY sc.source_code
ORDER BY total_records DESC;

-- Grafo: conteo de entidades y relaciones por tipo
SELECT
    entity_type,
    COUNT(*) AS entity_count
FROM source_entities
GROUP BY entity_type
ORDER BY entity_count DESC;

SELECT
    rel_type,
    COUNT(*) AS rel_count
FROM source_relationships
GROUP BY rel_type
ORDER BY rel_count DESC;

-- source_records sin match en source_entities (huérfanos)
SELECT
    sr.external_id,
    sr.entity_name,
    sr.supplier_name,
    sr.monto,
    sr.source_code
FROM source_records sr
LEFT JOIN source_entities se
    ON se.canonical_id = sr.entity_ruc
    OR se.display_name = sr.entity_name
WHERE se.id IS NULL
  AND sr.record_type = 'contract'
LIMIT 20;
```
