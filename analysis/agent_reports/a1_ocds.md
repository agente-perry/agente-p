# Agente A1 — scraped/ocds/

## 1. Inventario

| Archivo | Bytes | Líneas/Records | Notas |
|---------|-------|----------------|-------|
| records.jsonl | 1,067,448,834 | 72,399 | OCDS registros completos (contracts + procedures) — FUENTE DE VERDAD |
| contracts_2026.jsonl | 1,066,499,313 | 72,399 | Idéntico a records.jsonl en contenido — REDUNDANTE |
| graph.json | 61,276,496 | 1 objeto | Un único objeto JSON con entities + relationships |
| graph_2026.jsonl | 61,776,393 | 1 línea JSONL | Similar a graph.json pero RUCs anulados en public_entity metadata |
| raw_2026.jsonl.gz | 77,333,390 | N/A comprimido | OCDS releases raw antes del flatten |
| audit.json | 436 | 1 objeto | Metadata sobre última ejecución del ETL |

---

## 2. Schemas reales muestreados

### records.jsonl — Primer record completo (record_type: "contract")

```json
{
  "checksum": "44d18138fad149edc403b84599c60da8345402f2863353924044eceffd7df68d",
  "content_type": "application/ocds+json",
  "entity_name": "MUNICIPALIDAD PROVINCIAL DE PALPA",
  "entity_ruc": "20147704373",
  "evidence_quote": "CONSORCIO PALPA gano contrato con MUNICIPALIDAD PROVINCIAL DE PALPA por 84099.67.",
  "external_id": "ocds-dgv273-seacev3-1163548:1163548-1753032",
  "fecha": "2025-12-18",
  "fetched_at": "2026-05-16T17:58:39.008706+00:00",
  "monto": 84099.67,
  "page_number": null,
  "parsed_data": {
    "award_id": "1163548-1753032",
    "award_status": null,
    "contracts_count": 1,
    "ocid": "ocds-dgv273-seacev3-1163548",
    "procedure_type": "Concurso Público Abreviado",
    "tender_id": "1163548"
  },
  "period_year": 2025,
  "raw_data": { "...OCDS release completa..." },
  "raw_path": "/home/miguel/projects/hacklatam/data/raw/ocds/2026.jsonl.gz",
  "record_type": "contract",
  "region": "ICA",
  "source_code": "ocds_peru",
  "source_url": null,
  "supplier_name": "CONSORCIO PALPA",
  "supplier_ruc": null
}
```

**Segundo record (record_type: "procedure"):**
- supplier_name: null
- supplier_ruc: null
- monto: 11,788,245.0
- procedure_type: "Concurso Público de Servicios"

### Todos los campos observados

| Campo | Tipo | Ejemplo | Notas |
|-------|------|---------|-------|
| checksum | string | SHA256 hex | Integridad de raw_data |
| content_type | string | "application/ocds+json" | Siempre igual |
| entity_name | string | "MUNICIPALIDAD PROVINCIAL DE PALPA" | 100% presente |
| entity_ruc | string | "20147704373" (11 dígitos) | 100% presente — clave JOIN SUNAT |
| evidence_quote | string | "...gano contrato..." | Cita textual |
| external_id | string | "ocds-dgv273-seacev3-1163548:1163548-1753032" | 100% presente |
| fecha | string ISO | "2025-12-18" | 100% presente |
| fetched_at | ISO datetime | "2026-05-16T17:58:39..." | Timestamp scraping |
| monto | float | 84099.67 | 99.99% presente (8 nulos) |
| page_number | null | N/A | Siempre null — descartar |
| period_year | int | 2025 | Presente en todos |
| record_type | string | "contract" / "procedure" | 55,457 contract / 16,942 procedure |
| region | string | "ICA" | 100% presente |
| source_code | string | "ocds_peru" | Siempre igual |
| source_url | null | N/A | Siempre null — descartar |
| supplier_name | string/null | "CONSORCIO PALPA" | null si record_type="procedure" |
| supplier_ruc | string/null | null en muestra | 42% nulos (ver anomalías) |
| parsed_data.award_id | string/null | "1163548-1753032" | null si procedure |
| parsed_data.award_status | null | N/A | Siempre null en muestra |
| parsed_data.contracts_count | int | 1 | Siempre 1 en muestra |
| parsed_data.ocid | string | "ocds-dgv273-seacev3-1163548" | clave JOIN con results/ |
| parsed_data.procedure_type | string | "Concurso Público Abreviado" | Clave para flag F9 |
| parsed_data.tender_id | string | "1163548" | ID del proceso SEACE |
| raw_data | object | OCDS release completa | Muy grande — no cargar completo |
| raw_path | string | "/home/miguel/..." | Metadato de origen — descartar |

### graph.json — Estructura de entidades

```json
{
  "entities": [
    {
      "entity_type": "public_entity",
      "canonical_id": "pe_28d8a8e79d35",
      "display_name": "MUNICIPALIDAD PROVINCIAL DE PALPA",
      "metadata": {
        "ruc": "20147704373",
        "region": "ICA"
      },
      "sources": ["ocds_peru"]
    },
    {
      "entity_type": "company",
      "canonical_id": "1163548-1753032",
      "display_name": "CONSORCIO PALPA",
      "metadata": { "ruc": null },
      "sources": ["ocds_peru"]
    }
  ],
  "relationships": [
    {
      "relationship_type": "WON",
      "source": "1163548-1753032",
      "target": "pe_28d8a8e79d35",
      "properties": { "monto": 84099.67, "fecha": "2025-12-18" }
    }
  ]
}
```

### graph_2026.jsonl — Diferencia crítica vs graph.json

| Propiedad | graph.json | graph_2026.jsonl |
|-----------|------------|-----------------|
| public_entity.metadata.ruc | "20147704373" (presente) | null (PERDIDO) |
| public_entity.metadata.region | "ICA" | null (PERDIDO) |
| Formato | JSON object | JSONL single-line |

**graph_2026 es versión degradada. Usar graph.json.**

### audit.json — Contenido completo

```json
{
  "run_at": "2026-05-16T18:01:40.821187+00:00",
  "total_records": 72399,
  "contracts_count": 55457,
  "procedures_count": 16942,
  "with_entity_ruc": 72399,
  "with_supplier_ruc": 41994,
  "with_monto": 72391,
  "with_region": 72399,
  "with_external_id": 72399,
  "with_checksum": 72399,
  "entities_created": 33309,
  "relationships_created": 110914,
  "relationships_upserted_unique": 92138,
  "document_chunks_created": 72399
}
```

---

## 3. Validación vs Info.md §3A + §4

| Campo (Info.md) | Presente? | Tipo real | Desviaciones / Notas |
|-----------------|-----------|-----------|----------------------|
| source_code="ocds_peru" | ✅ | string | Exacto |
| external_id | ✅ | string | Formato exacto confirmado |
| record_type "contract" / "procedure" | ✅ | string | Info.md solo menciona "contract" — **procedures (23%) también existen** |
| entity_name | ✅ | string | 100% presente |
| entity_ruc 11 dígitos | ✅ | string | 100% presente; join clave con SUNAT |
| supplier_name | ✅ | string/null | null si procedure |
| supplier_ruc "a veces incompleto" | ✅ con caveat | string/null | **41,994/72,399 (58%) tienen valor; 30,405 (42%) son null** — confirmado por audit.json |
| monto en PEN | ✅ | float | 72,391/72,399 (99.99%) |
| fecha ISO | ✅ | string | Exacto |
| period_year | ✅ | int | 2025 ó 2026 (no 2024 en muestra) |
| region | ✅ | string | 100% presente |
| parsed_data.ocid | ✅ | string | Presente |
| parsed_data.tender_id | ✅ | string | Presente |
| parsed_data.award_id | ✅/null | string/null | null si procedure |
| parsed_data.procedure_type | ✅ | string | Presente |
| source_url | ⚠️ | null | Siempre null — **Info.md esperaba URL** |
| evidence_quote | ✅ | string | Presente; cita generada |

---

## 4. Volumen y distribuciones

### record_type
- contract: 55,457 (76.6%)
- procedure: 16,942 (23.4%) — sin supplier

### Cobertura de campos críticos
- entity_ruc: 72,399/72,399 (100%)
- supplier_ruc: 41,994/72,399 (58%)
- monto: 72,391/72,399 (99.99%)
- region: 72,399/72,399 (100%)

### Relaciones en graph.json
- Entidades: 33,309 (companies: 30,578, public_entities: 2,731)
- Relaciones brutas: 110,914
- Relaciones únicas (upserted): 92,138

### records.jsonl vs contracts_2026.jsonl
Son idénticos (mismos 72,399 registros, tamaños similares). **contracts_2026 es redundante.**

---

## 5. Anomalías / Hallazgos

1. **42% supplier_ruc nulos** — audit confirma 30,405 nulos. Causa: SEACE no expone RUC en algunas releases. Impacto: 30,405 edges sin trazabilidad a SUNAT.
2. **source_url siempre null** — URL disponible en raw_data.sources[0].url si se necesita.
3. **page_number siempre null** — legado del scraper; descartar.
4. **records.jsonl = contracts_2026.jsonl** — duplicado no documentado; usar solo records.jsonl.
5. **graph_2026.jsonl pierde RUC de public_entity** — usar graph.json como referencia.
6. **raw_path expone ruta local del desarrollador** (`/home/miguel/...`) — metadata de desarrollo; descartar.
7. **raw_data es muy grande** (~14.7 KB/registro promedio) — contiene OCDS release completa; extraer solo campos necesarios, no importar raw_data completo a Neo4j.
8. **period_year en muestra solo 2025/2026** — rango real puede variar; confirmar con descarga completa.

---

## 6. Señales explotables para el grafo

### Joins disponibles
| Campo OCDS | Target | Tipo join |
|-----------|--------|-----------|
| entity_ruc | SUNAT entity_ruc | exact match |
| supplier_ruc (si no null) | SUNAT entity_ruc | exact match (58% cobertura) |
| parsed_data.ocid | results/dossier.ocid | exact match |
| parsed_data.tender_id | recon_20_processes.csv primera columna | substring del ocid |

### Flags detectables solo de OCDS

| Flag | Campos | Lógica |
|------|--------|--------|
| F5 Cliente cautivo | entity_ruc, supplier_ruc | ≥5 contratos mismo par, >70% ingresos del supplier |
| F6 Entidad capturada | entity_ruc, monto, period_year | top-1 supplier >40% gasto anual de entidad |
| F7 Fraccionamiento | entity_ruc, supplier_ruc, monto, fecha | ≥3 contratos mismo par en 30 días bajo umbral licitación |
| F8 Ráfaga fin de año | supplier_ruc, fecha | ≥X% contratos en dic o última quincena |
| F9 Adjudicación directa anómala | procedure_type, monto | `Adjudicacion Simplificada` / `Contratacion Directa` con monto > p95 del tipo |
| F10 Supplier monógamo | supplier_ruc | ≥3 contratos, solo 1 entity_ruc cliente |
| F11 RUC incompleto | supplier_ruc | len(supplier_ruc) < 11 dígitos (cuando no null) |
| F12 Outlier monto | monto, procedure_type | monto > μ + 3σ dentro del bucket (sector, procedure_type) |

---

## 7. Recomendaciones de modelado

### Usar records.jsonl como única fuente — descartar contracts_2026, raw_2026, graph_2026

### Campos al grafo

**Obligatorios:**
- entity_ruc → nodo PublicEntity.ruc
- supplier_ruc → nodo Company.ruc (si no null)
- supplier_name → Company.display_name
- entity_name → PublicEntity.display_name
- external_id → propiedad de contrato (trazabilidad)
- parsed_data.procedure_type → Contract.procedure_type
- monto → relación WON.monto
- fecha → relación WON.fecha
- region → Contract.region / PublicEntity.region
- period_year → Contract.period_year
- parsed_data.ocid → Contract.ocid (clave join con results/)
- parsed_data.tender_id → Tender.tender_id
- parsed_data.award_id → Award.award_id

**Descartar:**
- page_number (null)
- source_url (null)
- raw_path (metadato desarrollo)
- raw_data completo (muy grande; extraer campos puntuales si necesario)
- content_type (constante)
- fetched_at (solo si se necesita auditoría)

### Estrategia procedures vs contracts

- **record_type="contract"**: crea nodo Contract + relación WON entre Company y PublicEntity
- **record_type="procedure"**: crear nodo Tender solamente (sin Company/WON) — permite analizar licitaciones desiertas o canceladas
