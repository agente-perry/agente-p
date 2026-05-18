# ARCHITECTURE — AgentePerry (canonical alignment)

Master architecture document for AgentePerry. Aligns every contributor —
human or agent — on the system's tesis, phased construction order, and the
explicit boundary between "what exists today" and "what must NOT be built
yet".

This is the source of truth. Other docs (`docs/AGENT_DOCUMENT_CORE.md`,
`AGENTS.md`, `specs/active/SPEC-0007-*`, `docs/PLAN.md`) link here for the
big picture.

---

## 1. Tesis técnica

> AgentePerry **no acusa corrupción**. Audita documentos de contratación
> pública peruana, detecta señales verificables contra doctrina pública
> (OSCE, OECE, OCP, OECD) y — solo si el score documental lo justifica —
> activa una investigación de red sobre empresas, funcionarios y
> antecedentes en fuentes públicas.

Tres principios no negociables:

1. **Evidencia primero**. Toda señal lleva cita textual + página + chunk +
   ancla doctrinal. Sin doble cita, no hay flag.
2. **Doctrina-first retrieval**. El planner consulta doctrina antes de
   tocar el TDR. `data/PDF-Base/` contiene PDFs públicos de criterio
   internacional versionados como corpus doctrinal; los outputs derivados
   no se commitean.
3. **Legal-safe by construction**. `LegalSafetyFilter` rechaza vocabulario
   acusatorio en cualquier campo del output antes de llegar al usuario.

---

## 2. Diagrama canónico

```mermaid
flowchart TD
    SEACE[SEACE Salud<br/>OCDS records.jsonl]
    SEACE --> CDC{CDC documental<br/>(roadmap)}
    CDC --> PACK

    subgraph PACK["Cluster documental del proceso (process_document_pack)"]
      TDR[/TDR / bases/]
      OTHER[/Otros documentos<br/>consultas, absoluciones/]
      WINNER[/Documento adjudicación<br/>buena pro / ganador<br/>(post-adjudicación)/]
    end

    PACK --> AUD[Auditor documental]

    subgraph AUD["Agente Auditor (PR #1..#9 → existente)"]
      PARSE[parse + OCR fallback]
      CHUNK[chunker cross-page]
      CLU[ClusterBuilder]
      DOC_IDX[(Doctrine Index<br/>OSCE/OECE/OCP/OECD)]
      PLAN[Planner doctrine-first<br/>+ intent expansion]
      RET[Retriever HNSW + BM25 + RRF]
      RISK[RiskAnalysis<br/>regex evidence-backed]
      CRIT[EvidenceCritic<br/>literal quote check]
      SYN[CivicSynthesizer]
      SAFE[LegalSafetyFilter]

      PARSE --> CHUNK --> CLU --> RET
      DOC_IDX --> PLAN --> RET
      RET --> RISK --> CRIT --> SYN --> SAFE
    end

    AUD --> SCORE{Score de riesgo<br/>+ confidence}

    SCORE -->|score < 50| OUT1[Análisis documental simple<br/>AnalysisResult legal-safe]
    SCORE -->|50 ≤ score ≤ 75| OUT2[Preguntas + revisión humana]
    SCORE -->|score > 75| GRAPH

    subgraph GRAPH["GraphRAG (roadmap Fase 4)"]
      SUNAT[SUNAT padron<br/>razón social / estado / reps]
      CONTRA[Contraloría<br/>informes / sanciones]
      JNE[JNE / ONPE<br/>política / campañas]
      PERUANO[El Peruano<br/>nombramientos / resoluciones]
      OCDS[SEACE / OCDS<br/>historial contractual]
      KG[(Knowledge graph<br/>empresa ↔ persona ↔ entidad)]

      SUNAT --> KG
      CONTRA --> KG
      JNE --> KG
      PERUANO --> KG
      OCDS --> KG
    end

    GRAPH --> DOSSIER[Dossier investigativo]

    subgraph DOSSIER["Dossier + Difusión (roadmap Fase 5)"]
      INFORME[Informe investigativo]
      V0[Reporte V0]
      PREG[Preguntas a la autoridad]
      CITIZEN[Resumen ciudadano]
      VIRAL[Agente contenido viral<br/>TikTok / X / WhatsApp]
    end

    OUT1 -.archivo paralelo.-> CITIZEN
    OUT2 -.archivo paralelo.-> PREG
```

---

## 3. Cluster documental por proceso

Definición canónica:

```text
process_document_pack =
    TDR / bases
  + otros documentos del expediente
      (consultas, absoluciones, integradas, pliego)
  + documento de adjudicación / ganador
      (acta buena pro, contrato firmado)  ← SOLO cuando existe
```

Schema sugerido:

```json
{
  "process_id": "ocds-dgv273-seacev3-...",
  "sector": "salud",
  "entity_ruc": "...",
  "phase": "tender | award | implementation",
  "documents": [
    {"type": "tdr",          "file": "...", "checksum": "..."},
    {"type": "bases",        "file": "...", "checksum": "..."},
    {"type": "absolucion",   "file": "...", "checksum": "..."},
    {"type": "adjudicacion", "file": "...", "checksum": "..."}
  ],
  "winner": {
    "supplier_ruc": "...",
    "supplier_name": "...",
    "monto": 0.0,
    "fecha_buena_pro": "YYYY-MM-DD"
  }
}
```

### Modo de operación según fase

| Modo | Trigger | Documentos disponibles | Salida |
|------|---------|------------------------|--------|
| **Preventivo** | TDR publicado, sin adjudicación | TDR + bases + consultas | Señales tempranas, preguntas para autoridad antes de la buena pro |
| **Investigativo** | Adjudicación publicada | Pack completo + ganador | Activa pre-condiciones de GraphRAG (RUC supplier conocido) |

El motor **no debe romper** si `winner` está vacío — debe operar en modo
preventivo. El score y la activación de GraphRAG cambian según el modo.

---

## 4. Las 5 fases del roadmap

### Fase 1 — Auditor documental (✅ ENTREGADO en working tree)

PDF aislado → `AnalysisResult` legal-safe.

> **Honestidad del estado**: las iteraciones descritas abajo viven en el
> working tree de la rama `feat/SPEC-0007-document-intelligence-core`.
> NO existen como commits separados etiquetados `PR #1`..`PR #9`. Las
> etiquetas son referencias internas al historial de trabajo documentado
> en `specs/active/SPEC-0007-*` y `docs/FLAG_CALIBRATION_NOTES.md`.

Componentes entregados (working tree):

- Parser PyMuPDF + header/footer dedup + OCR fallback (iter #6)
- Chunker cross-page con overlap (iter #1b)
- DocumentMapper + ClusterBuilder (iter #2)
- Doctrine stub (iter #1b) + Planner doctrine-first (iter #2)
- Intent expansion + debug retrieval (iter #8)
- Retriever HNSW + BM25 + RRF (iter #1b)
- RiskAnalysis con patterns calibrados (iter #7) + relaxación evidence-backed (iter #9) + severity tuning (iter #10)
- EvidenceCritic con literal-quote anti-hallucination (iter #3 + iter #8 fix) + reject_reasons telemetry (iter #10)
- CivicSynthesizer + LegalSafetyFilter (iter #3)
- AgentOrchestrator end-to-end (iter #4)
- Golden Set + batch runner (iter #5)

Métricas verificadas (al 2026-05-17):

- **208 tests passing** (`pytest tests/ -q`)
- **ruff clean** (`ruff check src tests`)
- **pyright 0 errors** dentro del paquete `document_intelligence`
- **5 flag records emitidos en 3 PDFs** del golden set:
  - 3 × `OVER_SPECIFIED_EXPERIENCE` (ambiente_positive p52, mineria p52, salud_pliego p206)
  - 2 × `EXCESSIVE_DOCUMENT_REQUIREMENT` (ambiente_positive p21, mineria p21)
  - 2 de los 5 son duplicados del mismo template SIE-ANA entre ambiente_positive y mineria; **señales distintas reales = 3**.

### Fase 2 — Cluster documental por proceso (PENDIENTE)

Convierte el motor de "PDF aislado" a "process pack".

Trabajo pendiente:

- Schema `process_document_pack` y loader.
- Orchestrator que recibe pack y produce `ProcessAnalysisResult`
  (agregado de N `AnalysisResult` cruzados).
- Reglas que solo aplican entre documentos del mismo proceso:
  - inconsistencias entre TDR y bases integradas
  - cambios entre original y absolución de consultas
  - desviaciones del contrato firmado vs TDR original

**Bloqueante mínimo para entrar a Fase 2**: tener ≥3 flags reales
verificadas manualmente en Fase 1.

### Fase 3 — Score de activación (PARCIAL)

Hoy: cada flag tiene `confidence` 0–1 y `severity` low/medium/high.
Falta: regla de score formal que decide cuándo escalar.

Regla propuesta (a fijar en PR posterior, NO ahora):

```
score = Σ por flag aceptada:
   + 30 si severity == high y confidence ≥ 0.65
   + 20 si severity == medium y confidence ≥ 0.55
   + 10 si severity == low
   + 20 si doctrine_anchor.source es OSCE/OECE/OCP
   + 10 si cita textual tiene número específico (años, monto, %)
   + 10 si proveedor identificado (modo investigativo)
   + 20 si supplier en sanciones vigentes
   + 10 si monto > percentil 95 del sector

clamp [0, 100]
```

Umbrales:

- `< 50`  → análisis documental simple, output AnalysisResult.
- `50–75` → preguntas para autoridad + revisión humana, sin GraphRAG.
- `> 75`  → activar GraphRAG **solo si existe primary key usable**.

### Fase 4 — GraphRAG (NO INICIAR ANTES DE TIEMPO)

Cruza supplier_ruc / entity_ruc con fuentes externas para construir
red de relaciones.

Fuentes:

- **SUNAT padron**: razón social, estado, condición (collector existe).
- **Contraloría**: informes, sanciones (collector NO existe).
- **JNE / ONPE**: política, campañas (collector NO existe).
- **El Peruano**: nombramientos, resoluciones (collector NO existe).
- **SEACE / OCDS**: historial contractual (data en jsonl, no en KG).

Tabla de salidas a construir:

| Tabla / endpoint | Propósito |
|------------------|-----------|
| `entities` | empresas + entidades públicas |
| `representatives` | relación persona ↔ empresa |
| `sanctions` | OECE inhabilitados vigentes |
| `contracts` | OCDS normalizado |
| `relationships` | aristas tipadas (GANA_CONTRATO, REPRESENTA_A, FUNCIONARIO_EN, etc.) |

**Decisión técnica pendiente**: PostgreSQL + recursive CTEs vs Neo4j /
Graphiti. Por defecto, PostgreSQL hasta que el volumen y las queries
justifiquen migración.

### Fase 5 — Dossier y difusión (NO INICIAR ANTES DE TIEMPO)

Outputs ciudadanos derivados del informe investigativo:

- Informe investigativo (técnico)
- Reporte V0 (resumen ejecutivo)
- Preguntas para la autoridad (formato pedido formal)
- Resumen ciudadano (lenguaje claro)
- Guion TikTok / hilo X / copy WhatsApp (Agente viral)

Cada output pasa por `LegalSafetyFilter` antes de salir. Sin esa garantía,
no se publica.

---

## 5. Diagrama del usuario → Implementación actual → Pendiente

| Bloque del diagrama | Estado actual | Pendiente |
|--------------------|--------------|-----------|
| Input CDC TDR solo Salud | Parcial — data en `data/scraped/filtered/salud_*.jsonl` (2566 records), sin CDC automático | CDC tiempo real (deferido a post-Fase 2) |
| Fuente SEACE | Parcial — OCDS scraping en `data/scraped/ocds/records.jsonl` (72,399 records) | Pipeline incremental + dedup productivo |
| TDR / otros docs / ganador | Parcial — motor analiza PDFs individuales | Schema `process_document_pack` (Fase 2) |
| Docs OSCE/OECE/OCP/OECD como criterio | Base real parcial — `data/PDF-Base/` incluye PDFs públicos OCP/OECD y el motor mantiene fallback stub | Expandir DoctrineIndex real, manifest enriquecido, chunks/vectores derivados fuera de git |
| Reglas detectar regularidad / clusters embeddings | ✅ Implementado — chunking, ClusterBuilder, retrieval híbrido, RRF | Calibración continua basada en golden set ampliado |
| Agente Auditor | ✅ V1 entregado — 9 agentes + 208 tests + 5 flags reales | Mejoras incrementales (severity tuning, more medium patterns) |
| Prob/Score | Parcial — `confidence` + `severity` por flag, sin score formal de proceso | Score agregado con umbrales (Fase 3) |
| GraphRAG | ❌ No iniciado | Diseño + schema + populación de tablas (Fase 4) |
| SUNAT | Parcial — collector + 25 records demo en `data/scraped/collectors/sunat_padron/` | Carga completa + integración a Investigation Agent |
| Contraloría / JNE / El Peruano | ❌ Collectors no existen | Construcción collectors + integración (Fase 4) |
| OECE sanciones | Collector existe (`apps/scrapers/.../sanciones.py`), output **vacío** | Ejecutar collector + popular tabla `sanctions` |
| Informe de investigación | Parcial — `AnalysisResult` legal-safe con summary + questions | Dossier investigativo extendido (Fase 5) |
| Agente viral TikTok | ❌ No iniciado | Generadores de copy (Fase 5) |

---

## 6. Regla de activación de GraphRAG

GraphRAG es **caro** (latencia + complejidad + riesgo de fabricar
relaciones). No se activa por defecto.

**Pre-condiciones obligatorias para activar GraphRAG**:

1. Existe al menos 1 `FlagRecord` aceptado por `EvidenceCriticAgent`.
2. La flag aceptada tiene `tdr_evidence.quote` no vacío y `doctrine_anchor`
   con source no vacío.
3. Score agregado del proceso supera el umbral (`> 75` en la fórmula
   propuesta en Fase 3, ajustable).
4. Existe al menos una primary key usable:
   - `supplier_ruc` (modo investigativo, post-adjudicación), o
   - `entity_ruc` (siempre disponible si OCDS está poblado), o
   - `ocid` (process identifier OCDS).
5. La data necesaria para el cruce existe en una fuente accesible y verificable
   (GCS, Neo4j, fuente pública o corpus doctrinal). No fabricar empresas,
   personas, sanciones ni relaciones.

Si cualquier pre-condición falla → **no activar**. El sistema entrega
`AnalysisResult` documental + nota explícita: "GraphRAG no activado:
{razón}".

Esta regla evita que la demo cuente historias con datos que no existen.

---

## 7. Modo preventivo vs Modo investigativo

| Aspecto | Modo preventivo | Modo investigativo |
|---------|-----------------|---------------------|
| Trigger temporal | TDR publicado, sin adjudicación | Adjudicación publicada |
| Pack disponible | TDR + bases + consultas | Pack completo + ganador |
| Findings posibles | Señales documentales (PR #1..#9) | Doc + supplier history + sanctions + reps |
| GraphRAG | NO (no hay supplier_ruc) | SÍ (si score > 75) |
| Output destinatario | Postores potenciales, sociedad civil, autoridad antes de la buena pro | Periodismo, fiscalía, investigación |
| Léxico permitido | "señal de riesgo", "merece revisión" | igual + "patrón atípico" |
| Léxico prohibido | Lista completa LegalSafety | Lista completa LegalSafety |

El orchestrator detecta el modo automáticamente según presencia de
`winner` en el pack. **Si winner está vacío → modo preventivo. Punto.**

---

## 8. Lo que NO se debe construir todavía

Lista explícita de **veto** mientras Fase 1 + Fase 2 no estén consolidadas:

- ❌ LangGraph / LangChain agent executors. El orchestrator manual con
  branching condicional es suficiente hasta Fase 4.
- ❌ Neo4j productivo. PostgreSQL + recursive CTEs cubren el grafo hasta
  millones de relaciones.
- ❌ Graphiti / KG temporal externo.
- ❌ MiniMax / GPT / OpenRouter como dependencia obligatoria. El motor
  debe correr con `--mode mock` sin API keys.
- ❌ UI / dashboard / Next.js demo. La CLI con `--debug-retrieval` es la
  demo técnica. UI viene en Fase 5.
- ❌ Generadores de contenido viral (TikTok, X, WhatsApp) antes de Fase 5.
- ❌ CDC en tiempo real. Batch scripts son suficientes hasta Fase 2.
- ❌ Webhooks / queues / cron jobs.
- ❌ Reglas o patterns sin evidence-backing en golden set.
- ❌ Findings fabricados (RUCs, personas, sanciones inventadas). Si la
  data no existe en el repo, el finding no se emite.

Si un PR rompe cualquier veto → rechazar y referir a este documento.

---

## 9. Estado de PRs vs fases

| PR | Fase | Estado | Output |
|----|------|--------|--------|
| PR #1 / #1b | 1 | ✅ | Scaffold + data layer + doctrine stub |
| PR #2 | 1 | ✅ | DocMapper + Cluster + Planner + Retriever |
| PR #3 | 1 | ✅ | Risk + Critic + Synthesizer + Safety |
| PR #4 | 1 | ✅ | AgentOrchestrator + CLI `analyze` + E2E tests |
| PR #5 | 1 | ✅ | Golden Set scaffolding + batch runner |
| PR #6 | 1 | ✅ | OCR hardening + Tesseract adapter |
| PR #7 | 1 | ✅ | Pattern hardening (0 FP regression) |
| PR #8 | 1 | ✅ | Query expansion + debug retrieval |
| PR #9 | 1 | ✅ | Pattern relaxation evidence-backed (5 flags reales) |
| PR #10 | 1 | ✅ | Severity tuning + scoring gate coverage (208 tests) |
| PR #11 | 1 → 2 | 🔜 | Golden set expansion: ≥1 PDF no-SIE template + human verification |
| PR #12 | 2 | 🔒 | Process document pack schema + multi-doc orchestrator |
| PR #13 | 3 | 🔒 | Score agregado formal + umbrales |
| PR #14 | 4 | 🔒 | SUNAT/OECE/OCDS productive load + Investigation Agent |
| PR #15 | 4 | 🔒 | GraphRAG primer (PostgreSQL recursive CTEs) |
| PR #16 | 5 | 🔒 | Dossier extendido + content agent |

🔒 = bloqueado hasta que la fase anterior tenga métricas verdes.

---

## 10. Frase central para todo contribuidor

> La visión completa es GraphRAG + dossier + viralización.
> La fase actual es **evidencia documental**.
> Sin evidencia documental verificable, no hay GraphRAG.
> Sin GraphRAG no hay dossier investigativo.
> Sin dossier no hay viralización.
>
> Construir hacia abajo de la pirámide rompe el sistema.

---

## 11. Ver también

- `docs/AGENT_DOCUMENT_CORE.md` — detalle operativo de Fase 1.
- `docs/FLAG_CALIBRATION_NOTES.md` — log de calibración de patterns.
- `docs/GOLDEN_SET_EVALUATION.md` — protocolo de evaluación.
- `specs/active/SPEC-0007-document-intelligence-core/` — spec viva de Fase 1.
- `data/golden_set/outputs/review_notes.md` — último review humano.
- `AGENTS.md` — instrucciones operativas por agente.
