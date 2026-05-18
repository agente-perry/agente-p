# Inventario de Data — agente-perry
Generado: 2026-05-17 | Investigación: 4 agentes Explore sobre `gs://agente-perry-data-prod/`

---

## 1. Tabla maestra de fuentes

| Path | Formato | Bytes | Records | Status vs Info.md | Usar? |
|------|---------|-------|---------|-------------------|-------|
| scraped/ocds/records.jsonl | JSONL | 1,067 MB | 72,399 | ✅ Match completo | ✅ FUENTE PRIMARIA |
| scraped/ocds/contracts_2026.jsonl | JSONL | 1,066 MB | 72,399 | ⚠️ Duplicado de records.jsonl | ❌ Descartar |
| scraped/ocds/graph.json | JSON | 61 MB | 33,309 entidades / 110,914 relaciones | ✅ Match | ⚠️ Opcional (recalculable) |
| scraped/ocds/graph_2026.jsonl | JSONL | 62 MB | similar | ❌ RUC de public_entity anulados | ❌ Descartar |
| scraped/ocds/raw_2026.jsonl.gz | JSONL.gz | 77 MB | N/A comprimido | ⚠️ No documentado | ❌ No prioritario |
| scraped/ocds/audit.json | JSON | 436 B | 1 | ✅ Confiable | ✅ Referencia |
| scraped/collectors/sunat_padron/records.jsonl | JSONL | 32 KB | **25** (Info.md dice 405) | ❌ SAMPLE/fixture | ⚠️ Limitado |
| scraped/collectors/sunat_padron/audit.json | JSON | 566 B | 1 | ✅ Confiable | ✅ Referencia |
| scraped/collectors/sunat_padron/graph.json | JSON | 11 KB | 25 nodos / 0 relaciones | ⚠️ Sin relaciones | ❌ Sub-utilizado |
| scraped/filtered/salud_2024_2025.jsonl | JSONL | 1.66 MB | 2,566 | ✅ Match exacto | ⚠️ Subset de OCDS |
| scraped/filtered/ambiente_2024_2025.jsonl | JSONL | 64 KB | 99 | ✅ Match exacto | ⚠️ Subset de OCDS |
| scraped/filtered/salud_2024_2025_with_documents.jsonl | JSONL | 19.5 MB | 2,566 | ✅ Extra: array `documents` | ✅ Para TDR URLs |
| scraped/filtered/ambiente_2024_2025_with_documents.jsonl | JSONL | 531 KB | 99 | ✅ Extra: array `documents` | ✅ Para TDR URLs |
| scraped/filtered/summary.json | JSON | 10 KB | 1 | ✅ Match | ✅ Referencia |
| scraped/results/*/dossier.json | JSON | ~5 KB c/u | **3 dossiers** | ✅ Nuevo — no documentado en detail | ✅ USAR |
| scraped/results/*/flags.json | JSON | ~1.5 KB c/u | 12 flags totales | ✅ | ✅ USAR |
| scraped/results/*/pages.json | JSON | grande | 181/212/23 páginas c/u | ✅ | ⚠️ Solo si full-text search |
| scraped/results/*/chunks.json | JSON | grande | 365/445/49 chunks c/u | ✅ | ❌ Muy granular |
| scraped/results/demo_case.md | MD | ~8.5 KB | 1 | Dato real (ESSALUD S/ 195M) | ✅ Referencia |
| scraped/tdrs/pdf_usability_audit.json | JSON | 2.4 KB | 1 | ✅ | ✅ Referencia |
| scraped/tdrs/pdf_usability_report.csv | CSV | 2.9 KB | 14 PDFs listados | ✅ | ✅ Referencia |
| scraped/tdr_recon/recon_20_processes.csv | CSV | 7.9 KB | 20 procesos | ✅ | ✅ Índice piloto |
| scraped/manual_tdrs/metadata.csv | CSV | 457 B | 2 | ⚠️ Sin ocid (testing) | ❌ Ignorar |
| downloads/2024/ | PDFs + JSON | ~300 MB | 21 procedimientos MINAM | ❌ No en Info.md | ✅ INCLUIR (ver A4) |
| downloads/2025/ | PDFs + JSON | ~250 MB | 16 procedimientos MINAM | ❌ No en Info.md | ✅ INCLUIR (ver A4) |

---

## 2. Mapa de IDs y joins disponibles

```
ocds/records.jsonl
  parsed_data.ocid  ──────────────────────► results/*/dossier.json → document.ocid
  parsed_data.ocid  ──────────────────────► tdr_recon/recon_20_processes.csv → col[0]
  external_id (= ocid + ":" + award_id)  ─► filtered/*.jsonl → external_id
  supplier_ruc (58% cobertura) ────────────► sunat_padron/records.jsonl → entity_ruc (exact)
  entity_ruc ──────────────────────────────► (futuro: entidades públicas externas)

sunat_padron/records.jsonl
  entity_ruc ──────────────────────────────► ocds.supplier_ruc (join clave, 0.12% cobertura actual)
  parsed_data.domicilio_fiscal ────────────► group by → cluster domicilio compartido

filtered/*.jsonl
  ocid ────────────────────────────────────► ocds/records.jsonl → parsed_data.ocid
  proveedor_ruc ───────────────────────────► sunat_padron → entity_ruc

results/*/dossier.json
  document.ocid ───────────────────────────► ocds/records.jsonl → parsed_data.ocid (exact)

downloads/*/metadata.json
  nomenclatura (AS-SM-1-2024) ────────────► NO join directo con OCDS (UUID distinto)
  cuantia + entidad + fecha ───────────────► join aproximado con OCDS cuando cierre
```

---

## 3. Catálogo de señales de corrupción detectables
*Derivado de evidencia real en reports — no de Info.md*

### GRUPO A — Requieren cruce OCDS × SUNAT (cobertura: 0.12% con sample actual)

| ID | Nombre | Fuentes | Lógica | Cobertura |
|----|--------|---------|--------|-----------|
| F1 | Empresa fantasma activa | OCDS + SUNAT | `sunat.estado=BAJA` OR `sunat.condicion=NO HABIDO` WHERE empresa ganó contrato OCDS | **Baja** (25/30,600 empresas en SUNAT) |
| F2 | Testaferros por domicilio | SUNAT + OCDS | ≥2 empresas con mismo `domicilio_fiscal` ganando del mismo `entity_ruc` | **Baja** (solo 25 empresas enriquecidas) |
| F3 | Domicilio fachada | SUNAT | regex: `domicilio_fiscal` contiene "S/N" o número vacío | **Media** (aplica a las 25 conocidas) |
| F4 | Geo-mismatch | SUNAT + OCDS | `ubigeo[0:2]` (región empresa) ≠ `region` (contrato) | **Baja** (mismo límite) |

### GRUPO B — Solo OCDS (cobertura: 58% supplier_ruc válido; 100% entity_ruc)

| ID | Nombre | Fuentes | Lógica | Cobertura |
|----|--------|---------|--------|-----------|
| F5 | Cliente cautivo | OCDS | par (entity_ruc, supplier_ruc) con ≥5 contratos Y >70% del gasto total del supplier | **Alta** (todos los contratos con supplier_ruc) |
| F6 | Entidad capturada | OCDS | top-1 supplier concentra >40% del gasto anual de una entidad pública | **Alta** (100% entity_ruc) |
| F7 | Fraccionamiento | OCDS | ≥3 contratos del mismo par en ventana 30 días, procedure_type = simplificada/directa, montos bajo umbral licitación | **Media** (requiere supplier_ruc válido) |
| F8 | Ráfaga fin de año | OCDS | supplier con ≥50% de sus contratos anuales en diciembre o última quincena | **Media** |
| F9 | Adjudicación directa anómala | OCDS | `procedure_type ∈ {Adjudicacion Simplificada, Contratacion Directa}` con monto > p95 del tipo | **Alta** |
| F10 | Supplier monógamo | OCDS | supplier con ≥3 contratos y solo 1 entity_ruc cliente en 2+ años | **Media** |
| F11 | RUC incompleto | OCDS | `len(supplier_ruc) < 11` cuando no null (identificación rota) | **Alta** (directamente observable) |
| F12 | Outlier de monto | OCDS | monto > μ + 3σ dentro del bucket (region, procedure_type) | **Alta** |

### GRUPO C — Dossiers TDR (cobertura: 3 procesados, 20 en índice)

| ID | Nombre | Fuentes | Lógica | Cobertura |
|----|--------|---------|--------|-----------|
| F13 | Contrato high-risk | results/dossier.json | `total_score ≥ 40` (MEDIO/ALTO) | **Muy baja** (3 dossiers) |
| F14 | Flags TDR | results/flags.json | `OBSOLETE_PHYSICAL_FORMAT` = menor trazabilidad digital; `LOW_TRACEABILITY_OUTPUT` = entregables vagos | **Muy baja** (3 dossiers, 12 flags) |

### GRUPO D — Métricas derivadas (sin threshold binario)

| Métrica | Cómputo | Uso |
|---------|---------|-----|
| Diversidad de clientes | `count(DISTINCT entity_ruc) / total_contracts` por supplier | Score relativo de monogamia |
| Concentración de proveedor | `max(monto_supplier / monto_total_entidad)` por entidad+año | Identificar monopolios |
| Velocidad de primer contrato | `fecha_primer_contrato - fecha_inicio_act_sunat` en días | Empresas recién creadas |
| Cobertura geográfica | `count(DISTINCT region) por supplier` | Suppliers sin presencia regional |

---

## 4. Desviaciones encontradas vs Info.md

| Sección Info.md | Afirmación | Realidad observada | Impacto |
|-----------------|------------|-------------------|---------|
| §3B "405 empresas SUNAT" | 405 registros en SUNAT padrón | **25 registros** (raw_path muestra fixture/testing) | Alto — join OCDS-SUNAT casi nulo |
| §3A source_url | "URL de la release OCDS" | Siempre null | Bajo — URL disponible en raw_data.sources |
| §3A supplier_ruc | "a veces incompleto" | **42% null** (no solo incompleto, ausente) | Alto — 30,405 contracts sin trazabilidad empresa |
| §5 relaciones modeladas | MISMO_REPR_LEGAL, REPRESENTANTE_DE, FAMILIAR_DE, APORTO_A | **Ninguna de estas tiene data** en el bucket actual | Alto — no modelar sin datos |
| No documentado | contracts_2026.jsonl duplica records.jsonl | Redundante | Bajo |
| No documentado | graph_2026.jsonl pierde RUC de public_entity | Usar graph.json en cambio | Bajo |
| No documentado | downloads/ carpeta con 37 procedimientos MINAM 2024-2025 | Data nueva — no en OCDS | Positivo — incluir |
| No documentado | SUNAT records.jsonl es fixture (raw_path="tests/fixtures/...") | Dataset real de 405 puede no existir en GCS | Alto — verificar |

---

## 5. Decisiones de modelado preliminares

### Nodos que HAY que crear (data existe)

```
(:Company)         ← sunat_padron/records.jsonl + OCDS supplier_name/ruc
(:PublicEntity)    ← OCDS entity_ruc/entity_name
(:Contract)        ← OCDS records.jsonl (record_type="contract")
(:Tender)          ← OCDS records.jsonl (record_type="procedure")
(:Award)           ← OCDS parsed_data.award_id
(:Address)         ← SUNAT raw_data (domicilio desglosado)
(:Dossier)         ← results/*/dossier.json
(:RiskFlag)        ← results/*/flags.json
(:ProcedureSeace)  ← downloads/*/metadata.json (datos MINAM 2024-2025)
```

### Nodos que NO se crean (sin data)

- Person — no hay registros de personas en ningún archivo
- PoliticalOrg — no hay datos ONPE
- Sancion — no hay datos Contraloría
- PDFPage / Chunk — demasiado granular; contenido en RiskFlag.evidence_quote es suficiente

### Relaciones que HAY que crear

```
(:Company)-[:WON {monto, fecha, procedure_type, region}]->(:Contract)
(:Contract)-[:AWARDED_BY]->(:PublicEntity)
(:Contract)-[:UNDER_TENDER]->(:Tender)
(:Award)-[:OF_CONTRACT]->(:Contract)
(:Company)-[:LOCATED_AT]->(:Address)
(:Company)-[:SAME_ADDRESS_AS]->(:Company)          ← DERIVADA de Address
(:Contract)-[:ANALYZED_BY]->(:Dossier)
(:Dossier)-[:HAS_FLAG]->(:RiskFlag)
(:ProcedureSeace)-[:EVENTUAL_CONTRACT]->(:Contract) ← nullable hasta que cierre
```

### Relaciones que NO se crean (sin data)

- REPRESENTANTE_DE, FAMILIAR_DE, APORTO_A, GOVERNS, TIENE_SANCION

---

## 6. Riesgos de calidad de datos

| Riesgo | Severidad | % afectado | Mitigación |
|--------|-----------|------------|------------|
| supplier_ruc null en OCDS | Alta | 42% (30,405/72,399) | Crear Company con hash(supplier_name) como canonical_id cuando no hay RUC |
| SUNAT sample de 25 (no 405) | Alta | Cobertura 0.12% | Verificar si existe dataset completo; los flags F1-F4 serán simbólicos hasta entonces |
| proveedor_ruc < 11 dígitos en filtered | Media | Desconocido | Normalizar: lstrip ceros, padleft hasta 11 dígitos antes del join |
| Procedures (16,942) sin supplier | Media | 23.4% | Crear nodo Tender sin Company; no genera edge WON |
| Solo 3 dossiers procesados | Media | 3/20 procesos TDR | Dossiers dan señal de texto; OCDS flags son independientes |
| downloads/ UUID no joinea con OCDS | Baja | 37 procedimientos | Join aproximado por nomenclatura+fecha cuando cierre proceso |
| graph.json entidades tienen canonical_id como hash (no RUC) para companies sin RUC | Baja | ~30,578 companies | Recalcular desde records.jsonl; usar RUC si existe, hash(name) si no |

---

## 7. Resumen para Fase 2

### Señales confirmadas con evidencia: **14 red flags** (A=4, B=8, C=2)

### Cobertura efectiva por grupo
- Grupo B (solo OCDS): **máxima** — 55,457 contratos, 100% entity_ruc
- Grupo A (OCDS × SUNAT): **mínima** — bloqueado por sample SUNAT de 25
- Grupo C (TDRs): **piloto** — 3 dossiers, 20 en cola

### Estrategia de piloto recomendada
1. Cargar `scraped/filtered/ambiente_2024_2025.jsonl` (99 contratos) → smoke test completo del schema
2. Correr flags Grupo B (F5-F12) → resultados inmediatos, alta cobertura
3. Añadir los 3 dossiers → flags F13-F14
4. Añadir SUNAT (25 empresas) → flags F1-F4 simbólicos pero completan el modelo
5. Añadir `downloads/` procedimientos MINAM → modelo ProcedureSeace

### Próxima acción antes de Fase 2 (Ontología + Cypher)
Verificar si existe SUNAT completo (405 empresas):
```bash
gcloud storage ls --recursive gs://agente-perry-data-prod/ | grep -i sunat
```
Si no existe, los flags F1-F4 serán demostraciones de estructura, no análisis real.
