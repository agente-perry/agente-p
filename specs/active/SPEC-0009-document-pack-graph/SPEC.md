# SPEC-0009: Document Pack Graph — PDF-Base Source for PlannerAgent

## Estado

- **Spec ID**: SPEC-0009
- **Autor**: AgentePerry Staff AI Engineering
- **Fecha**: 2025-05-17
- **Branch**: `feat/SPEC-0009-document-pack-graph`
- **Depende de**: SPEC-0000 (limpieza base), SPEC-0002 (pdf-parser), SPEC-0003 (chunk-embeddings)

---

## Resumen ejecutivo

Crear un módulo que inspeccione todos los PDFs de `data/PDF-Base`,
construya un inventario estructurado, clasifique cada documento por tipo
heurístico, genere chunks y clusters cuando hay texto, y cree un grafo
documental local (`document_pack_graph.json`) que alimente al PlannerAgent.

Este módulo es la **fuente documental interna** para el modo preventive /
 investigative. No abre GraphRAG externo, Neo4j ni Graphiti. Es la base
 sobre la cual el futuro PlannerAgent podrá decidir si activa GraphRAG
 según los criterios: señal documental + score + llave usable.

---

## Problema

Cuando se recibe una carpeta de PDFs de un proceso de contratación pública,
no existe una capa intermedia que:

1. Sepa cuántos PDFs hay y sus propiedades (SHA-256, páginas, texto, OCR).
2. Clasifique cada PDF sin LLM (TDR, bases integradas, buena pro...).
3. Infiera el modo del proceso (preventive = antes de adjudicación,
   investigative = después de ganador).
4. Detecte qué keys faltan para activar GraphRAG (RUC, OCID, entidad).
5. Produzca chunks y clusters temáticos para retrieval.

---

## Solución

Crear el módulo `packages/document_intelligence/src/document_intelligence/document_pack/`:

```
document_pack/
  __init__.py     — exports públicos
  schemas.py      — InventoryItem, ClassifiedDocument, ProcessDocumentPack,
                    PackGraph, PackGraphNode, PackGraphEdge
  inventory.py    — escanear carpeta, SHA-256, parsear metadata
  classifier.py   — clasificación heurística por nombre + keywords
  pack_builder.py — orquestar todo, escribir artefactos
  pack_graph.py   — construir grafo local (nodos + edges)
```

Y un CLI subcomando `build-pack`.

---

## Diseño detallado

### 1. `schemas.py`

```python
# Enums
DocumentType   = "tdr" | "bases" | "bases_integradas" | "absolucion_consultas"
               | "adjudicacion" | "buena_pro" | "contrato" | "anexo" | "unknown"
ParseStatus   = "text_ok" | "needs_ocr" | "parse_error"
PackMode      = "preventive" | "investigative" | "unknown"
MissingGraphRAGKey = "provider_ruc" | "ocid" | "entity_name" | "award_document"

# Models
InventoryItem
ClassifiedDocument   ( InventoryItem + document_type + classification_signals )
ProcessDocumentPack  ( pack_id, root_path, documents[], mode, has_tdr_or_bases,
                       has_award_document, missing_for_graphrag[] )
PackGraphNode        ( node_id, node_type, label, properties )
PackGraphEdge        ( edge_id, source_id, target_id, relationship, properties )
PackGraph            ( pack_id, nodes[], edges[] )
```

### 2. `inventory.py`

- Escanea `*.pdf` case-insensitive, excluye `*.pdf:Zone.Identifier`, `*.tmp`, `*.bak`.
- Calcula SHA-256 por streaming (65536-byte chunks).
- Parsing con `parse_pdf_with_summary(ocr_mode="off")` — no OCR por defecto.
- `parse_status`: `text_ok` / `needs_ocr` / `parse_error`.
- `usable_for_analysis = pages_with_text > 0 and parse_status != parse_error`.
- Soporta `--max-docs` para limitar procesamiento.

### 3. `classifier.py`

Clasificación en 3 fases (sin LLM):

1. **Filename matching** — patterns `bases_integradas`, `tdr`, `bases`,
   `buena_pro`, `contrato`, etc. en el nombre del archivo.
2. **Page-text probing** — lee primeras 3 páginas del PDF y busca keywords
   en el catálogo (`BASES INTEGRADAS`, `TÉRMINOS DE REFERENCIA`, etc.).
3. **Keyword scoring** — weighted scoring; `bases_integradas > bases > tdr`.

Conflictos resueltos por prioridad:
- `bases_integradas` > `bases` > `tdr`
- `buena_pro` > `adjudicacion`
- `contrato` solo
- `absolucion_consultas` puede coexistir con bases
- `unknown` como fallback

### 4. `pack_builder.py`

Orquestador que:
1. Llama `build_inventory`.
2. Para cada PDF: `classify_document`.
3. Si `usable_for_analysis`: `parse_pdf` → `chunk_document` → `build_clusters`.
4. Infiere `mode`:
   - `preventive`: hay TDR/bases y no hay award document.
   - `investigative`: hay TDR/bases + adjudicacion/buena_pro/contrato.
   - `unknown`: resto.
5. Detecta `missing_for_graphrag`.
6. Escribe los 8 artefactos a `--out`.

### 5. `pack_graph.py`

Grafo local con 6 tipos de nodo y 7 tipos de edge:

**Nodos**: `process_pack`, `document`, `page`, `chunk`,
`semantic_cluster`, `missing_key`.

**Edges**:
- `PACK_CONTAINS_DOCUMENT`
- `DOCUMENT_HAS_PAGE`
- `DOCUMENT_HAS_CHUNK`
- `DOCUMENT_HAS_CLUSTER`
- `CLUSTER_CONTAINS_CHUNK`
- `DOCUMENT_NEEDS_OCR`
- `PACK_MISSING_KEY`

### 6. Artefactos generados

| Archivo | Descripción |
|---------|-------------|
| `pdf_inventory.json` | Array de InventoryItem |
| `document_manifest.json` | Array de ClassifiedDocument |
| `process_document_pack.json` | ProcessDocumentPack |
| `document_pack_graph.json` | PackGraph (nodes + edges) |
| `clusters.json` | Array de DocumentCluster |
| `chunks.jsonl` | Un DocumentChunk por línea |
| `parse_report.json` | Diagnóstico agregado del parsing |
| `pack_summary.md` | Resumen legible en Markdown |

---

## CLI

```bash
python -m document_intelligence build-pack \
  /home/miguel/projects/hacklatam/data/PDF-Base \
  --out /home/miguel/projects/hacklatam/data/PDF-Base/_index \
  --ocr off

# Flags
--out      directorio de salida (default: pdf_dir/_index)
--ocr      off | auto (default: off)
--max-docs N   limitar PDFs procesados
--pretty      JSON indentado
```

---

## Tests

Crear 4 archivos de test:

1. `tests/test_document_pack_inventory.py`
   - detecta PDFs
   - SHA-256 no vacío
   - pages_total > 0
   - usable_for_analysis = True cuando hay texto
   - max_docs limita correctamente
   - ignora Zone.Identifier y .bak

2. `tests/test_document_pack_classifier.py`
   - `bases_integradas` reconocido por filename
   - `bases` reconocido por filename
   - `tdr` reconocido por nombre y keywords
   - `buena_pro` > `adjudicacion` en scoring
   - `unknown` cuando no hay señales

3. `tests/test_document_pack_graph.py`
   - nodos `process_pack` y `document` presentes
   - edge `PACK_CONTAINS_DOCUMENT` existe
   - edge `DOCUMENT_NEEDS_OCR` cuando pages_needing_ocr > 0
   - edge `PACK_MISSING_KEY` cuando faltan keys
   - nodos únicos (sin duplicados por node_id)

4. `tests/test_document_pack_builder.py`
   - modo `preventive` cuando hay bases sin ganador
   - modo `investigative` cuando hay bases + buena_pro
   - modo `unknown` cuando no hay bases
   - `missing_for_graphrag` incluye `award_document` cuando no hay adjudicacion
   - los 8 archivos son creados
   - `max_docs` es respetado

---

## Gate de calidad

```bash
cd packages/document_intelligence
uv run --extra dev pytest tests/test_document_pack_*.py -q
uv run --extra dev ruff check src/document_intelligence/document_pack tests/
uv run --extra dev pyright src/document_intelligence/document_pack
```

---

## Límites de esta implementación

### Sí hace

- Escaneo y parsing de PDFs locales.
- Clasificación heurística sin LLM.
- Chunks y clusters para documentos con texto.
- Grafo documental local (nodos + edges).
- Modo preventive vs. investigative.
- Detección de keys faltantes para GraphRAG.

### No hace (fuera de scope)

- GraphRAG externo (Neo4j, Graphiti).
- Conexiones a SUNAT, JNE, ONPE, CDC, SEACE.
- OCR real (solo marca `needs_ocr`).
- Modificaciones a RiskAnalysisAgent, EvidenceCriticAgent,
  LegalSafetyFilter, DoctrineIndex, scrapers, Supabase.
- UI de ningún tipo.
- Embeddings o llamadas a LLMs.

---

## Criterios para activar modo future GraphRAG

| Criterio | Fuente en el pack |
|----------|-------------------|
| Señal documental aceptada | `has_tdr_or_bases = True` + `has_award_document = True` |
| Evidencia textual | `chunks.jsonl` no vacío + clusters con labels |
| Score sobre umbral | PlannerAgent determina (futuro) |
| Llave usable | `missing_for_graphrag = []` (vacío) |

Cuando los 4 criterios se cumplan, el PlannerAgent podrá activar
GraphRAG externo con la confianza de que hay corpus suficiente
y keys para enriquecer el grafo con datos de entidades externas.