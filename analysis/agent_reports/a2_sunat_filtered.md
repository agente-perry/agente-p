# Agente A2 — sunat_padron + filtered

## 1. Inventario

| Archivo | Bytes | Records | Notas |
|---------|-------|---------|-------|
| sunat_padron/records.jsonl | 31,836 | **25** (Info.md dice 405 — DISCREPANCIA) | MUESTRA/fixture, no dataset completo |
| sunat_padron/audit.json | 566 | 1 | Estadísticas ETL |
| sunat_padron/graph.json | 11,564 | 25 entidades, 0 relaciones | Nodos sin aristas |
| filtered/salud_2024_2025.jsonl | 1,657,111 | 2,566 | Contratos salud 2024-2025 — match Info.md |
| filtered/ambiente_2024_2025.jsonl | 64,077 | 99 | Contratos ambiente — match Info.md |
| filtered/salud_2024_2025_with_documents.jsonl | 19,455,459 | 2,566 | Salud + array `documents` SEACE adjuntos |
| filtered/ambiente_2024_2025_with_documents.jsonl | 530,627 | 99 | Ambiente + array `documents` |
| filtered/summary.json | 10,398 | 1 | Estadísticas agregadas por sector |

---

## 2. Schemas reales muestreados

### sunat_padron/records.jsonl — Primer record completo

```json
{
  "checksum": "857ecd4573082c1068e7c01fdd998944d03b9ed9907c100b5538048316e4b7e5",
  "content_type": "text/plain",
  "entity_name": "CONSORCIO LIMA DIRECC SAC",
  "entity_ruc": "20555534987",
  "evidence_quote": "SUNAT registra a CONSORCIO LIMA DIRECC SAC con RUC 20555534987 en estado ACTIVO.",
  "external_id": "20555534987",
  "fecha": null,
  "fetched_at": "2026-05-16T23:17:14.142694+00:00",
  "monto": null,
  "page_number": null,
  "parsed_data": {
    "condicion": "HABIDO",
    "domicilio_fiscal": "AV. LIMA 101 B 302 23 15.50",
    "estado": "ACTIVO",
    "razon_social": "CONSORCIO LIMA DIRECC SAC",
    "ruc": "20555534987",
    "ubigeo": "150132"
  },
  "period_year": null,
  "raw_data": {
    "codigo_zona": "URB.",
    "condicion": "HABIDO",
    "departamento": "302",
    "estado": "ACTIVO",
    "interior": "",
    "kilometro": "15.50",
    "lote": "B",
    "manzana": "23",
    "nombre_via": "LIMA",
    "numero": "101",
    "razon_social": "CONSORCIO LIMA DIRECC SAC",
    "ruc": "20555534987",
    "tipo_via": "AV.",
    "tipo_zona": "MIRAFLORES",
    "ubigeo": "150132"
  },
  "raw_path": "tests/fixtures/sunat_padron_sample.txt",
  "record_type": "company",
  "region": "15",
  "source_code": "sunat_padron",
  "source_url": "https://www.sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html",
  "supplier_name": null,
  "supplier_ruc": null
}
```

**Todos los campos observados en SUNAT:**
- Top-level: checksum, content_type, entity_name, entity_ruc, evidence_quote, external_id, fecha (null), fetched_at, monto (null), page_number (null), period_year (null), record_type, region (código numérico "15"), source_code, source_url, supplier_name (null), supplier_ruc (null)
- parsed_data: condicion, domicilio_fiscal, estado, razon_social, ruc, ubigeo
- raw_data: codigo_zona, condicion, departamento, estado, interior, kilometro, lote, manzana, nombre_via, numero, razon_social, ruc, tipo_via, tipo_zona, ubigeo

### sunat_padron/audit.json — Contenido completo

```json
{
  "run_at": "2026-05-16T23:17:14.585884+00:00",
  "source_code": "sunat_padron",
  "total_records": 25,
  "with_valid_ruc": 25,
  "with_name": 25,
  "with_estado": 25,
  "with_condicion": 25,
  "with_ubigeo": 25,
  "entities_created": 25,
  "relationships_created": 0,
  "companies_enriched": 25,
  "companies_unmatched": 0,
  "records_skipped": 0,
  "errors": 0,
  "active_count": 21,
  "baja_count": 4,
  "no_habido_count": 7,
  "ocds_companies_total": 30600,
  "ocds_companies_with_ruc": 20521,
  "ocds_companies_matched_sunat": 25,
  "ocds_match_rate": 0.12
}
```

**Datos críticos del audit:**
- 21 ACTIVO, 4 BAJA
- 7 NO HABIDO (de 25)
- Match rate OCDS-SUNAT: **0.12%** (25 de 20,521 con RUC en OCDS)
- OCDS tiene 30,600 proveedores totales; solo 20,521 con RUC válido

### sunat_padron/graph.json — Estructura

```json
{
  "entities": [
    {
      "entity_type": "company",
      "canonical_id": "20555534987",
      "display_name": "CONSORCIO LIMA DIRECC SAC",
      "metadata": {
        "ruc": "20555534987",
        "razon_social": "CONSORCIO LIMA DIRECC SAC",
        "estado": "ACTIVO",
        "condicion": "HABIDO",
        "ubigeo": "150132",
        "domicilio_fiscal": "AV. LIMA 101 B 302 23 15.50"
      },
      "sources": ["sunat_padron"]
    }
  ],
  "relationships": []
}
```

graph.json SUNAT: 25 nodos, **0 relaciones** — sub-utilizado.

### filtered/salud_2024_2025.jsonl — Primer record

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

**Nota:** Schema distinto a records.jsonl de OCDS. Campos: `entity` (no `entity_name`), `proveedor_nombre` (no `supplier_name`), `proveedor_ruc` (no `supplier_ruc`), `modalidad` (no `procedure_type` top-level), `objeto` (nombre del proceso).

### filtered/*_with_documents.jsonl — Campo adicional

```json
"documents": [
  {
    "dateModified": "2024-10-24T23:21:28-05:00",
    "datePublished": "2024-08-05T12:50:00-05:00",
    "documentType": "biddingDocuments",
    "format": "rar",
    "id": "24831474985187568",
    "language": "es",
    "title": "Bases Administrativas",
    "url": "https://prod1.seace.gob.pe/SeaceWeb-PRO/SdescargarArchivoAlfresco?fileCode=..."
  }
]
```

Tipos de `documentType` observados: `biddingDocuments`, `evaluationReports`, `awardNotice`, `contractSigned`, `contractAnnexe`, `clarifications`.
Tamaño: salud 19.46 MB vs salud_base 1.66 MB (11.7x).

### filtered/summary.json — Datos agregados clave

```json
{
  "salud": {
    "sector": "salud",
    "total_records": 2566,
    "total_monto": 3942056248.26
  },
  "ambiente": {
    "sector": "ambiente_mineria",
    "total_records": 99,
    "total_monto": 58701072.88
  }
}
```

Top entidad salud por monto: ESSALUD → S/ 2,935,608,880.74 (74.5% del total sector)
Top entidad ambiente por monto: ANA → S/ 29,079,365.39 (49.5% del total sector)

---

## 3. Validación vs Info.md §3B + §3C

| Campo (Info.md) | Presente? | Tipo real | Desviaciones |
|-----------------|-----------|-----------|--------------|
| source_code="sunat_padron" | ✅ | string | Exacto |
| record_type="company" | ✅ | string | Exacto |
| entity_ruc 11 dígitos | ✅ | string | Exacto |
| entity_name | ✅ | string | = razon_social |
| parsed_data.estado | ✅ | "ACTIVO"/"BAJA" | Exacto |
| parsed_data.condicion | ✅ | "HABIDO"/"NO HABIDO" | Exacto |
| parsed_data.razon_social | ✅ | string | Exacto |
| parsed_data.ubigeo | ✅ | string 6 dígitos | Exacto |
| parsed_data.domicilio_fiscal | ✅ | string concatenado | Exacto |
| raw_data.nombre_via | ✅ | string | En raw_data (no en parsed_data) |
| raw_data.numero | ✅ | string | En raw_data |
| raw_data.tipo_via | ✅ | string | En raw_data |
| raw_data.tipo_zona | ✅ | string | En raw_data |
| **405 empresas** | ⚠️ DISCREPANCIA | **25 en realidad** | raw_path="tests/fixtures/..." indica MUESTRA |
| salud_2024_2025.jsonl 2,566 contratos | ✅ | 2,566 | Match exacto |
| ambiente 99 contratos | ✅ | 99 | Match exacto |
| salud S/ 3,942M | ✅ | S/ 3,942,056,248 | Match exacto |
| ambiente S/ 58M | ✅ | S/ 58,701,072 | Match exacto |

---

## 4. Volumen y distribuciones

### SUNAT (25 registros — sample)
- ACTIVO: 21 (84%) | BAJA: 4 (16%)
- HABIDO: 18 (72%) | NO HABIDO: 7 (28%)
- Empresas estado=BAJA: TECNOSUR PERU S.A.C., SERVICIOS AMBIENTALES DEL ORIENTE S.A.C., TEXTILES ANDINOS E.I.R.L., AGROINDUSTRIAL SAN MARTÍN S.A.C.
- Empresas NO HABIDO: INVERSIONES DEL NORTE E.I.R.L., CONSORCIO PIURA RÍO E.I.R.L., ELECTRODOMÉSTICOS DEL PACÍFICO E.I.R.L., LOGÍSTICA INTEGRAL DEL PERÚ S.R.L., ESCUELA DE CONDUCTORES DEL SUR S.R.L. + 2 más

### Match rate OCDS-SUNAT
- OCDS proveedores totales: 30,600
- Con RUC: 20,521 (67%)
- Matchean con SUNAT: 25 (0.12%)
- **Cobertura real es muy baja con dataset sample**

---

## 5. Anomalías / Hallazgos

1. **DATASET SUNAT ES SAMPLE (NO 405):** raw_path="tests/fixtures/sunat_padron_sample.txt" confirma que es fixture de prueba. Info.md promete 405. Necesita verificar si existe dataset completo en otra ruta GCS.
2. **Domicilios sospechosos en muestra:**
   - "JR. BOLOGNESI S/N" — INVERSIONES DEL NORTE E.I.R.L., condicion=NO HABIDO
   - "CAL. LIMA 88 DPTO 5 6 M 1301 0.00" — TEXTILES ANDINOS E.I.R.L., estado=BAJA
3. **graph.json SUNAT tiene relationships=[]** — no detecta domicilios compartidos; debe calcularse en el pipeline de grafos.
4. **filtered usa nombres de campo distintos a OCDS:** `entity` vs `entity_name`, `proveedor_ruc` vs `supplier_ruc`, `modalidad` vs `procedure_type`. Requiere mapping al importar.
5. **proveedor_ruc en filtered a veces < 11 dígitos:** "1601907" (7 dígitos) — confirma el problema de Info.md §3A sobre RUCs incompletos.
6. **_with_documents no agrega campos estructurales** — solo array `documents`; mismo conteo de registros.

---

## 6. Señales explotables para el grafo

### Flag F1 (Fantasma activo)
- Join: `ocds.supplier_ruc` ↔ `sunat.entity_ruc` (exact)
- Señal: estado=BAJA o condicion=NO HABIDO en empresa ganadora
- Cobertura actual: 0.12% con sample — necesita SUNAT completo

### Flag F2 (Testaferro por domicilio)
- Campo: `parsed_data.domicilio_fiscal` (o reconstruido de raw_data)
- Señal: ≥2 empresas con misma dirección ganando del mismo entity_ruc
- graph.json de SUNAT NO lo calcula — hay que derivarlo

### Flag F3 (Domicilio genérico/fachada)
- Regex sobre `domicilio_fiscal`: patrón "S/N", sin número, kilómetro=0.00
- En muestra: "JR. BOLOGNESI S/N" detectado

### Flag F4 (Geo-mismatch)
- `ubigeo[0:2]` (región SUNAT) vs `region` del contrato OCDS
- Ejemplo: empresa ubigeo "15" (Lima) ganando contrato region "CUSCO" sin presencia

### Address como nodo (cruce domicilio)
- `raw_data.tipo_via + nombre_via + numero + tipo_zona + ubigeo` → hash → nodo Address
- Permite query "empresas en mismo domicilio"

---

## 7. Recomendaciones de modelado

### Modelar Address como nodo separado

```
(:Address {
  address_hash: md5(domicilio_fiscal+ubigeo),
  domicilio_fiscal: string,
  ubigeo: string,
  tipo_via: string,
  nombre_via: string,
  numero: string,
  tipo_zona: string,
  is_generic: boolean  // "S/N" o número ausente
})
(:Company)-[:LOCATED_AT]->(:Address)
(:Company)-[:SAME_ADDRESS_AS]->(:Company)  // derivada
```

### Filtered — NO importar como tabla nueva

Son subsets de ocds/records.jsonl + renaming de campos. El grafo puede filtrar por `entity_ruc` de entidades de salud/ambiente.
**Excepción:** `_with_documents` para indexar URLs de TDRs descargables.

### graph.json SUNAT — IGNORAR

relationships=[] — no aporta. Usar records.jsonl directamente.

### Acción urgente
Verificar si existe dataset SUNAT completo (405 empresas) en otra ruta del bucket:
```
gcloud storage ls --recursive gs://agente-perry-data-prod/ | grep sunat
```
Si no existe, la cobertura real del join OCDS-SUNAT será 0.12% = señal muy débil.
