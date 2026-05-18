# SPEC-0007: Document Intelligence Core

## Objetivo

Crear un núcleo agentico local-first que analice TDRs/bases/contratos de contratación pública y emita señales de riesgo (red flags) con **doble sustento**: cita textual del TDR + cita textual de la doctrina (OCP Red Flags Guide, OECD Governing with AI).

El sistema **no acusa corrupción**. Detecta señales basadas en evidencia, fundamentadas en metodologías públicas internacionales.

## Inversión conceptual respecto a la actividad inicial

La actividad inicial proponía embeber el TDR y agrupar sus chunks para detectar flags por heurística textual. Con la información actualizada se invierte la arquitectura:

| Capa | Qué es | Quién la procesa |
|------|--------|------------------|
| **Doctrina** | PDFs grandes (~500pp c/u): OCP Red Flags for Integrity Guide + OECD Governing with AI. Definiciones de indicadores, fórmulas OCDS, patrones internacionales. | Embebido fuera de este spec (colaborador externo entrega vectores + chunks). Nosotros consumimos. |
| **TDR target** | Bases / Términos de Referencia / contratos peruanos. ~50–300pp. | Nosotros parseamos, segmentamos, mapeamos, analizamos. |
| **Agente** | Cadena de agentes que lee selectivamente el TDR, consulta la doctrina, detecta señales, valida evidencia, sintetiza respuesta legal-safe. | Este spec. |

La doctrina **sustenta** las flags; el TDR las **evidencia**. Sin ambas citas, una flag no es emitida.

## Principio rector

> Si no hay cita textual del TDR **y** cita textual o referencia explícita de la doctrina, no hay flag.

## Patrón RAG: Agentic 2-Layer + Map-Reduce + Cluster Routing

Razones para no usar RAG plano (top-k embedding):

1. Los TDRs son largos y heterogéneos; chunks individuales pierden contexto seccional.
2. Las red flags son **patrones estructurales** (sección "Experiencia" sobreespecificada, "Forma de pago" sin entregable digital), no coincidencias léxicas.
3. La doctrina describe **categorías** de riesgo; necesitamos primero saber qué buscar antes de buscarlo.

Estrategia adoptada:

```
1. INGEST TDR
   parser → text por página → chunker con overlap → embeddings (adapter) → index local

2. MAP (DocumentMapperAgent)
   detecta secciones del TDR (objeto, requisitos, experiencia, entregables, plazos, criterios, etc.)
   produce mapa estructural con rangos de página

3. CLUSTER (ClusterBuilderAgent)
   agrupa chunks por sección semántica
   etiqueta cada cluster con tema canónico

4. DOCTRINE LOOKUP (PlannerAgent)
   consulta el índice de doctrina con prompt fijo:
   "¿Qué red flags aplican a una contratación con estos clusters detectados?"
   recupera definiciones de indicadores relevantes + sus señales textuales esperadas
   produce un plan: { flag_code → clusters a inspeccionar, queries específicas }

5. RETRIEVE TDR (RetrieverAgent)
   por cada query del plan, busca en clusters seleccionados (no en todo el TDR)
   devuelve chunks con score, página, contexto

6. RISK ANALYSIS (RiskAnalysisAgent)
   por cada chunk + flag candidato, evalúa si la evidencia soporta la señal
   produce flags con: evidence_quote (TDR), page_number, doctrine_anchor (cita doctrina)

7. CRITIC (EvidenceCriticAgent)
   descarta flags sin doble sustento
   re-pregunta si la evidencia es ambigua (loop limitado a 1 retry)

8. SYNTHESIZE (CivicSynthesizerAgent)
   produce JSON legal-safe + resumen + preguntas para la autoridad
   bloquea léxico prohibido (corrupto, robo, fraude, etc.)
```

### Por qué este patrón vs alternativas

| Alternativa | Por qué no |
|------------|-----------|
| RAG plano top-k sobre todo el TDR | Devuelve chunks descontextualizados; pierde estructura. |
| HyDE / Self-Query | Útil pero insuficiente solo; lo usaremos dentro del PlannerAgent. |
| ColBERT / late interaction | Mejor recall pero mayor costo. No justificado para fase 1. |
| GraphRAG completo | Sobredimensionado; no tenemos KG todavía. |
| Map-Reduce puro (Anthropic-style) | Sin doctrina-first, generaría flags inventadas. |

Adoptamos un híbrido: **DocMap + ClusterRoute + DoctrineFirst Planner + ConstrainedRetrieve + EvidenceCritic loop**. Cercano a *Agentic RAG* (Self-RAG + CRAG) pero con la novedad de que la doctrina dicta qué buscar antes de tocar el target.

### Índices

| Índice | Contenido | Estructura | Provisión |
|--------|-----------|------------|-----------|
| `doctrine_index` | Chunks de los 2 PDFs doctrinales | HNSW (faiss) en memoria, persistido a disco | Importado desde artefacto externo (ver § 8) |
| `tdr_index` (por documento) | Chunks del TDR bajo análisis | HNSW en memoria, vida = sesión de análisis | Construido on-the-fly por nuestro pipeline |

Para fase 1 ambos usan **FAISS local** (HNSW con `M=32, efConstruction=200, efSearch=64`). Adapter abstraía pgvector para fase 2.

No usamos IVF porque el volumen actual (decenas de miles de chunks) cabe en HNSW puro con mejor recall. IVF se justifica desde ~1M vectores.

## Esquema de input/output

### Input externo (doctrina, provisto por colaborador)

```text
data/doctrine/
  manifest.json              # versión, fecha, fuentes, modelo embedding
  chunks.jsonl               # { chunk_id, source, page_start, page_end, text, section_path }
  vectors.npy                # matriz [N x D] alineada con chunks.jsonl
```

Si el artefacto no existe, el sistema corre con un **stub doctrinal hardcoded** (un subset reducido de definiciones OCP traducido a JSON) para no bloquear desarrollo.

### Output del orchestrator

```json
{
  "document": "base_001.pdf",
  "question": "...",
  "tdr_map": {
    "sections": [{ "name": "Experiencia del postor", "page_start": 45, "page_end": 52 }]
  },
  "clusters_inspected": ["Entregables", "Criterios de evaluación"],
  "flags": [
    {
      "flag_code": "OBSOLETE_PHYSICAL_FORMAT",
      "flag_name": "Entregable exclusivamente físico",
      "severity": "medium",
      "tdr_evidence": {
        "page_number": 91,
        "quote": "El informe final deberá presentarse impreso en formato A3..."
      },
      "doctrine_anchor": {
        "source": "OCP Red Flags Guide 2024",
        "section": "Implementation phase / Output traceability",
        "page": 47,
        "quote": "Lack of digital, structured deliverables is a signal of weak traceability..."
      },
      "explanation": "El requisito prioriza soporte físico y reduce trazabilidad digital.",
      "confidence": 0.78
    }
  ],
  "summary": "...",
  "questions_for_authority": ["..."],
  "missing_data": ["..."],
  "confidence": "medium",
  "disclaimer": "Este análisis no constituye acusación. Identifica señales con evidencia textual que requieren revisión humana."
}
```

## Catálogo inicial de red flags

Tomadas de OCP Red Flags for Integrity Guide (fase planeamiento + adjudicación + implementación). Cada una con `doctrine_anchor` obligatorio.

| Código | Nombre | Fase OCDS | Doctrina source |
|--------|--------|-----------|-----------------|
| `LOW_TRACEABILITY_OUTPUT` | Entregables sin dataset estructurado | Implementation | OCP |
| `OBSOLETE_PHYSICAL_FORMAT` | Entregables exclusivamente físicos | Implementation | OCP |
| `EXCESSIVE_DOCUMENT_REQUIREMENT` | Documentación administrativa excesiva | Tender | OCP |
| `SPECIFIC_EQUIPMENT_REQUIREMENT` | Especificación de marca/modelo único | Tender | OCP |
| `EXCESSIVE_CERTIFICATION_REQUIREMENT` | Certificaciones desproporcionadas | Tender | OCP |
| `SUBJECTIVE_EVALUATION_CRITERIA` | Criterios subjetivos no medibles | Award | OCP |
| `UNREALISTIC_DEADLINE` | Plazo de presentación atípicamente corto | Tender | OCP |
| `OVER_SPECIFIED_EXPERIENCE` | Experiencia previa hecha a medida | Tender | OCP |
| `AI_NO_AUDIT_TRAIL` | Uso de IA sin trazabilidad ni gobernanza | Implementation | OECD |

La lista crece con la doctrina. El catálogo vive en `packages/document_intelligence/src/document_intelligence/flags/catalog.yaml` y se valida contra el manifiesto doctrinal al cargar.

## Modos de ejecución

| Modo | API key requerida | Embeddings | Síntesis |
|------|------------------|-----------|----------|
| `mock` (default si no hay key) | No | FakeEmbedder determinístico | Plantillas estáticas |
| `local-embed` | No | sentence-transformers / E5 | Plantillas |
| `llm` | Sí (OPENAI_API_KEY o OPENROUTER_API_KEY) | Real | LLM con prompts estrictos |

El CLI imprime el modo activo al iniciar. Los tests corren en `mock`.

## CLI

```bash
# 1. cargar doctrina (importa artefacto del colaborador)
python -m document_intelligence.cli load-doctrine data/doctrine/manifest.json

# 2. inspeccionar un PDF antes de analizarlo
python -m document_intelligence.cli inspect-pdf data/tdrs/base_001.pdf

# 3. construir índice TDR persistente
python -m document_intelligence.cli build-index data/tdrs/base_001.pdf

# 4. análisis dirigido por pregunta
python -m document_intelligence.cli analyze data/tdrs/base_001.pdf \
  --question "Detecta señales de baja trazabilidad y requisitos restrictivos" \
  --output reports/base_001.json

# 5. comparación entre 2 TDRs (fase posterior)
python -m document_intelligence.cli compare data/tdrs/base_001.pdf data/tdrs/base_002.pdf
```

## Restricciones legal-safe

- Léxico prohibido en cualquier output: `corrupto`, `corrupción comprobada`, `robo`, `fraude`, `delito`, `culpable`, `delincuente`, `mafioso`, `ilegal`.
- Léxico requerido: `señal de riesgo`, `merece revisión`, `requiere explicación`, `patrón atípico`, `cita textual`, `página`.
- Cada flag emitido pasa por `LegalSafetyFilter` (regex + lista negra). Si falla, se reescribe o se rechaza.
- Disclaimer obligatorio en todo output JSON.

## Out of scope (no implementar ahora)

- Embedding de los 2 PDFs doctrinales (lo hace colaborador externo).
- Supabase, pgvector productivo.
- Frontend / UI.
- Scrapers SEACE/ONPE/JNE.
- OCR (PDFs con imágenes se marcan `needs_ocr: true` y se omiten).
- Comparación entre TDRs (fase posterior, ver tasks).
- Dossier persistente, alertas SMS.
- KG / Graphiti / Neo4j.

## Relación con specs existentes

- **SPEC-0002 (tdr-pdf-parser)** y **SPEC-0003 (tdr-chunk-embeddings)** ya implementaron parsing y chunking básicos en `apps/scrapers/src/agenteperry/tdr/`. El nuevo paquete **no los reescribe**; los importa o reimplementa solo si su contrato no encaja con la arquitectura agentica. Auditar en task 0.
- **SPEC-0004 (tdr-rule-based-flags)** ya tiene flags por regex. Este spec los supera con flags doctrina-fundamentadas; los flags antiguos se mantienen como `legacy_rule_flags` opcionales.
- **SPEC-0005 (tdr-dossier-api)** consume `AnalysisResult`. Mantener compatibilidad de esquema o documentar migración.

## Criterios de aceptación

1. `python -m document_intelligence.cli analyze <fixture.pdf> --question "..."` corre sin API key y emite JSON válido.
2. Cada flag emitido contiene `tdr_evidence.quote`, `tdr_evidence.page_number`, `doctrine_anchor.source`, `doctrine_anchor.quote`.
3. El LegalSafetyFilter rechaza outputs con léxico prohibido (test obligatorio).
4. El EvidenceCriticAgent descarta al menos 1 flag candidato en el test fixture (prueba de que no es pass-through).
5. El PlannerAgent consulta doctrina antes de tocar el TDR (verificable en logs).
6. `docs/AGENT_DOCUMENT_CORE.md` contiene diagrama Mermaid del pipeline + tabla de agentes + ejemplo end-to-end.
7. Tests: `pytest packages/document_intelligence/tests/ -q` pasa en modo mock.
8. Ruff + pyright limpios.

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Doctrina aún no provista por colaborador | Stub doctrinal hardcoded (subset OCP en YAML) permite desarrollo end-to-end |
| LLM alucina citas | EvidenceCriticAgent verifica que `quote` exista literalmente en el chunk recuperado |
| PDFs con tablas/imágenes | Marcar `needs_ocr` y no inventar texto |
| Léxico acusatorio se filtra | LegalSafetyFilter + tests específicos + revisión humana antes de cada release |
| Recall bajo en retrieve | Híbrido vectorial + BM25 (rank_bm25) como fallback en RetrieverAgent |
