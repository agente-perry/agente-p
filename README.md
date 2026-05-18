# AGENTE P.E.R.R.Y

**Procurement Evidence & Risk Recognition sYstem**

Knowledge Graph anticorrupción para la detección automatizada de patrones inusuales en contrataciones públicas del Perú. Cruza datos de SEACE (OCDS), SUNAT e-consultaruc y TDRs para identificar 19 señales de alerta.

---

## Estructura del repositorio

```
agente-p/
├── analysis/               # Fase 1 — inventario de data
│   ├── agent_reports/      # Reports por fuente (A1-A4)
│   └── data_inventory.md   # Inventario consolidado + mapa de joins
├── ontology/               # Fase 2 — ontología Neo4j
│   ├── schema.md           # Spec completa + Mermaid + decisiones de diseño
│   ├── schema.cypher       # Constraints + índices (DDL)
│   ├── flags.cypher        # 19 queries de detección de red flags
│   └── metrics.cypher      # Métricas derivadas (M1-M6)
├── ingest/                 # Pipeline GCS → Neo4j AuraDB
│   ├── main.py             # Entry point (schema|ocds|sunat|dossiers|seace|derived|all|verify)
│   ├── load_ocds.py        # 72,399 OCDS records → Company, PublicEntity, Contract, Tender
│   ├── load_sunat.py       # SUNAT e-consultaruc → enrich Company + Person + Address
│   ├── load_dossiers.py    # scraped/results/ → Dossier + RiskFlag
│   ├── load_seace.py       # downloads/2024-2025/ → ProcedureSeace
│   ├── run_derived.py      # SAME_ADDRESS_AS, SAME_REPR_AS, risk_score_v2
│   ├── neo4j_utils.py      # Driver con retry + batch runner
│   ├── gcs_utils.py        # GCS streaming + listing
│   ├── checkpoint.py       # Checkpoints para reinicio de ingest
│   ├── config.py           # Variables de entorno
│   └── requirements.txt
├── frontend-perry/         # Next.js — dashboard de señales de alerta
│   └── app/page.tsx
├── .env.example            # Plantilla de variables de entorno
└── Info.md                 # Descripción de fuentes de data (referencia)
```

---

## Setup rápido

### 1. Variables de entorno

```bash
cp .env.example .env
# Edita .env con las credenciales de Neo4j AuraDB
```

### 2. Instalar dependencias Python

```bash
cd ingest
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### 3. Autenticar GCS

```bash
gcloud auth application-default login
gcloud config set project agente-perry
```

### 4. Correr el ingest

```bash
cd ingest
python main.py schema      # Aplica constraints + índices en Neo4j
python main.py ocds        # Carga 72k contratos OCDS (~10 min)
python main.py sunat       # Enriquece empresas con SUNAT e-consultaruc
python main.py dossiers    # Carga Dossiers y RiskFlags de TDRs
python main.py seace       # Carga procedimientos MINAM de downloads/
python main.py derived     # Calcula SAME_ADDRESS_AS, SAME_REPR_AS, métricas
python main.py verify      # Imprime conteos de nodos y relaciones
```

O todo en un paso:

```bash
python main.py all
```

El ingest es **resumable**: si se interrumpe, vuelve a correr el mismo comando. Los checkpoints están en `ingest/.checkpoints/`.

---

## Grafo — nodos y relaciones

| Nodo | Records | Fuente |
|------|---------|--------|
| Company | ~30,578 | OCDS + SUNAT |
| PublicEntity | ~2,731 | OCDS |
| Contract | ~55,457 | OCDS |
| Tender | ~16,942 | OCDS |
| Address | variable | SUNAT domicilio_fiscal |
| Person | variable | SUNAT representantes_legales |
| Dossier | 3+ | scraped/results/ |
| RiskFlag | 12+ | scraped/results/flags.json |
| ProcedureSeace | 37 | downloads/ |

| Relación | Descripción |
|----------|-------------|
| WON | Empresa → Contrato |
| AWARDED_BY | Contrato → EntidadPública |
| UNDER_TENDER | Contrato → Licitación |
| LOCATED_AT | Empresa → Dirección |
| SAME_ADDRESS_AS | Empresa ↔ Empresa (domicilio compartido) |
| REPRESENTS | Persona → Empresa |
| SAME_REPR_AS | Empresa ↔ Empresa (representante legal compartido) |
| ANALYZED_BY | Contrato → Dossier |
| HAS_FLAG | Dossier → RiskFlag |

---

## Red flags detectables

Los 19 flags están en `ontology/flags.cypher`. Ejemplos:

- **F1** — Empresa fantasma: estado BAJA o condición NO HABIDO ganando contratos activos
- **F2** — Domicilio compartido: ≥3 empresas en la misma dirección no genérica
- **F3** — Sin trabajadores: empresa con 0-2 trabajadores y >S/100k en contratos
- **F4** — Empresa reciente: primer contrato <365 días tras inicio de actividades
- **F5** — Deuda coactiva activa mientras gana contratos del Estado
- **F9** — Concentración extrema: proveedor con >80% del gasto de una entidad en un año
- **F11** — Red de representante: mismo represente en ≥3 empresas que compiten
- **F14** — Velocidad anormal: ≥3 contratos de la misma entidad en 90 días

Ver `ontology/flags.cypher` para todos los flags con Cypher ejecutable.

---

## Frontend

```bash
cd frontend-perry
npm install
npm run dev     # http://localhost:3000
```

Dashboard estático (mockup) con las señales detectadas, estadísticas del grafo y previsualización del agente conversacional.

---

## Fuentes de datos

- **SEACE / OCDS Perú**: 72,399 contratos 2024-2026 en `gs://agente-perry-data-prod/scraped/ocds/`
- **SUNAT e-consultaruc**: datos ricos de empresas (representantes, trabajadores, CIIU, deuda coactiva)
- **TDRs / Dossiers**: análisis de riesgo de PDFs de términos de referencia en `scraped/results/`
- **Downloads MINAM**: 37 procedimientos SEACE en ejecución en `downloads/2024/` y `downloads/2025/`

Todos los datos son de **fuentes públicas**. Las señales de alerta son indicadores estadísticos — no conclusiones jurídicas.
