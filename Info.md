Guía Práctica de Datos para el Equipo de Grafos
Esta es la guía que necesitas. Voy a hacer un documento claro y completo.
1. ¿Dónde está la data?
Ubicación	Qué
GCP Bucket gs://agente-perry-data-prod/	Todo el dataset completo (~2 GB)
GitHub Release	Archivo .tar.gz con todo
Para bajar todo desde GCP:
gcloud storage cp -r gs://agente-perry-data-prod/scraped ./data/
gcloud storage cp -r gs://agente-perry-data-prod/golden_set ./data/
2. Estructura General de la Data
data/scraped/
├── ocds/                    ← CONTRATOS PÚBLICOS (OCDS PERU)
├── filtered/                ← CONTRATOS FILTRADOS (SALUD + AMBIENTE)
├── collectors/
│   └── sunat_padron/        ← REGISTRO DE EMPRESAS (SUNAT)
├── tdrs/                    ← PDFs de Términos de Referencia
├── tdr_recon/               ← 20 procesos reconciliados manualmente
├── manual_tdrs/             ← TDRs cargados por CSV
└── results/                 ← Output del pipeline (pages, chunks, flags, dossier)
3. La Data Más Importante para Grafos
3A. OCDS Peru — Contrataciones Públicas (FUENTE PRINCIPAL)
Archivo clave: data/scraped/ocds/records.jsonl (72,399 registros, 1 GB)
Cada registro tiene esta estructura exacta:
Campo              Ejemplo
─────────────────────────────────────────────────────────────────────
source_code        "ocds_peru"
external_id        "ocds-dgv273-seacev3-988512:988512-1753032"
record_type        "contract"  (o "procedure")
entity_name        "SEGURO SOCIAL DE SALUD"
entity_ruc         "20131257750"  (11 dígitos, RUC de entidad)
supplier_name      "CONSORCIO EDIFICADOR SUR"
supplier_ruc       "1601907"  (RUC del proveedor — CUIDADO: a veces viene incompleto)
monto              347883662.85  (en PEN)
fecha              "2024-11-22"
period_year        2024
region             "LIMA"
parsed_data.ocid   "ocds-dgv273-seacev3-988512"
parsed_data.tender_id    "988512"
parsed_data.award_id     "988512-1601907"
parsed_data.procedure_type  "Adjudicacion Simplificada"
source_url         URL de la release OCDS
evidence_quote     "CONSORCIO EDIFICADOR SUR gano contrato..."
Para crear el grafo, el campo crítico es supplier_ruc — ese es el identificador que cruza con SUNAT.
Archivo de grafo pre-calculado: data/scraped/ocds/graph.json (61 MB)
- 
33,309 entidades (companies + public_entities)
- 
110,914 relaciones (GANO_CONTRATO y COMPRO_A)
- 
Listo para cargar directo a source_entities + source_relationships
3B. SUNAT Padrón — Registro de Empresas
Archivo clave: data/scraped/collectors/sunat_padron/records.jsonl
Cada registro tiene:
Campo              Ejemplo
─────────────────────────────────────────────────────────────────────
source_code        "sunat_padron"
record_type        "company"
entity_ruc         "20555534987"  (RUC de la empresa)
entity_name        "CONSORCIO LIMA DIRECC SAC"
parsed_data.estado "ACTIVO"  (o "BAJA")
parsed_data.condicion  "HABIDO"  (o "NO HABIDO")
parsed_data.razon_social  "CONSORCIO LIMA DIRECC SAC"
parsed_data.ubigeo  "150132"
parsed_data.domicilio_fiscal  "AV. LIMA 101 B 302..."
parsed_data.nombre_via  "LIMA"
parsed_data.numero  "101"
parsed_data.tipo_via  "AV."
parsed_data.tipo_zona  "MIRAFLORES"
Este archivo permite:
- 
Enriquecer empresas del OCDS con estado/condición SUNAT
- 
Detectar fantasmas: empresas con estado "BAJA" o "NO HABIDO"
- 
Cruzar por domicilio fiscal: empresas en misma dirección → MISMO_DOMICILIO
3C. Datos Enriquecidos por Sector
Salud: data/scraped/filtered/salud_2024_2025.jsonl (2,566 contratos, S/ 3,942M)
Ambiente: data/scraped/filtered/ambiente_2024_2025.jsonl (99 contratos, S/ 58M)
Estos ya tienen filtrados solo los contratos relevantes para el piloto TDR.
4. Los Campos Clave para Armar el Grafo
Para conectar EMPRESA → CONTRATO → ENTIDAD PÚBLICA
Campo en OCDS	Qué es	Para qué sirve
entity_ruc	RUC de la entidad pública (11 dígitos)	Nodo destino en GANO_CONTRATO
supplier_ruc	RUC del proveedor (11 dígitos, a veces incompleto)	Nodo origen en GANO_CONTRATO — CRÍTICO
monto	Monto del contrato en PEN	Peso de la relación
fecha	Fecha de adjudicación	Para análisis temporal
external_id	OCID único del contrato	Trazabilidad
Para conectar EMPRESA → SUNAT (estado legal)
Campo en SUNAT	Qué es	Para qué sirve
entity_ruc	RUC de la empresa	Cruce con supplier_ruc del OCDS
estado	ACTIVO / BAJA	Detectar empresas dadas de baja
condicion	HABIDO / NO HABIDO	Detectar empresas no localizadas
domicilio_fiscal	Dirección completa	Cruce MISMO_DOMICILIO
Para cruzar con TDRs (documentos)
Campo en TDR results	Qué es	Para qué sirve
ocid	ID del proceso SEACE	Cruce con OCDS
pages[].text_content	Texto extraído	Búsqueda de patrones (comités, cláusulas)
flags[].evidence_quote	Cita textual del flag	Evidencia para risk flags
dossier.risk_summary.total_score	Score de riesgo	Priorización
5. Las Relaciones de Grafos Ya Modeladas
COMPANY ──GANO_CONTRATO──► PUBLIC_ENTITY
                            ▲
                            │
                       COMPRO_A
COMPANY ──MISMO_DOMICILIO──► COMPANY
COMPANY ──MISMO_REPR_LEGAL──► COMPANY
PERSON ──REPRESENTANTE_DE──► COMPANY
PERSON ──MIEMBRO_COMITE──► PUBLIC_ENTITY
PERSON ──FAMILIAR_DE──► PERSON
COMPANY ──APORTO_A──► POLITICAL_ORG
POLITICAL_ORG ──GOVERNS──► PUBLIC_ENTITY
COMPANY ──TIENE_SANCION──► SANCION
6. Lo Que Existe vs Lo Que Faltaría
✅ YA EXISTE (disponible ahora)
Fuente	Estado	Qué hay
OCDS Peru	✅ Listo	72,399 contratos, 33k entidades, 110k relaciones
SUNAT Padrón	✅ Listo	405 empresas con estado/domicilio
TDRs descargados	✅ Listo	14 archivos salud + 6 ambiente
Pipeline TDR completo	✅ Listo	3 dossiers con flags ejecutados
❌ FALTA (para el roadmap completo de grafos)
Fuente	Prioridad	Qué agregar
SEACE/OECE	P0	Descargar bulk de documentos de SEACE
Contraloria Sanciones	P0	Obtener TIENE_SANCION
SUNAT Consulta múltiple RUC	P1	Enriquecer RUCs incompletos del OCDS
DJI (Declaraciones de Intereses)	P1	Vínculos familiares, empresariales
ONPE Claridad	P1	Aportantes a partidos políticos
JNE Voto Informado	P1	Candidatos, hojas de vida
SUNARP Conoce/SPRL	P2	Personas jurídicas, poderes
7. Queries SQL Clave para Empezar
-- 1. Ver todos los contratos de una empresa específica
SELECT entity_name, monto, fecha, external_id
FROM source_records
WHERE supplier_ruc = '20100041953'  -- RIMAC por ejemplo
ORDER BY fecha DESC;
-- 2. Subgrafo de una entidad pública (3 niveles)
SELECT * FROM get_subgraph('20131257750', 3);  -- ESSALUD
-- 3. Empresas fantasmas (creadas < 12 meses antes de ganar)
SELECT e.canonical_id, e.display_name, e.metadata->>'fecha_inicio_act' as inicio
FROM source_entities e
WHERE e.entity_type = 'company'
AND e.metadata->>'fecha_inicio_act' IS NOT NULL
AND e.metadata->>'fecha_inicio_act' > '2023-01-01';
-- 4. Companies que comparten mismo domicilio (MISMO_DOMICILIO)
SELECT e1.display_name, e2.display_name, e1.metadata->>'domicilio_fiscal'
FROM source_entities e1
JOIN source_entities e2 ON e1.metadata->>'domicilio_fiscal' = e2.metadata->>'domicilio_fiscal'
WHERE e1.id < e2.id AND e1.entity_type = 'company' AND e2.entity_type = 'company';
-- 5. Concentración de mercado por entidad
SELECT entity_name, supplier_name, SUM(monto) as total
FROM source_records
GROUP BY entity_ruc, supplier_ruc
ORDER BY total DESC
LIMIT 20;
8. Próximos Pasos para el Equipo de Grafos
1. 
Descargar data: gcloud storage cp -r gs://agente-perry-data-prod/scraped ./data/
2. 
Leer INDEX.md completo: cat data/INDEX.md
3. 
Mirar el graph.json: head -100 data/scraped/ocds/graph.json
4. 
Ver consultas de ejemplo: cat apps/scrapers/src/agenteperry/graph/models.py
5. 
Correr el pipeline de sync: uv run agenteperry graph map-records --input data/scraped/ocds/records.jsonl