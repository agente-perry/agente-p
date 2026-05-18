# Scraping Delivery Contract — `ProcessDocumentPack`

This document is the canonical contract between the **scraping team** (SEACE,
OCDS, OECE, future sources) and the **Document Intelligence engine**
(`packages/document_intelligence`). Anything the scraping team delivers must
conform to this schema; anything the engine consumes assumes it does.

If a field cannot be filled today, deliver it as `null`. Do not omit fields
documented as optional — keep the schema stable so the loader is forwards-
compatible.

## Delivery format

- One pack per JSONL line, or one pack per `.json` file.
- Encoding: UTF-8.
- File location: `data/scraped/seace_salud/manifests/<batch>.jsonl`
  (or equivalent per sector).
- Example: `data/scraped/seace_salud/manifests/process_document_packs.example.jsonl`.

## Schema — `ProcessDocumentPack`

```json
{
  "pack_id": "essalud_pack_001",
  "root_path": "data/golden_set/pdfs",
  "sector": "salud",

  "process_id": "AS-SM-55-2023-ESSALUD-GCL-1",
  "ocid": "ocds-dgv273-seacev3-988512",
  "entity_name": "Seguro Social de Salud - EsSalud",
  "entity_ruc": "20131257750",
  "procedure_code": "AS-SM-55-2023-ESSALUD-GCL-1",
  "procedure_type": "AS",
  "object_description": "CONTRATACION DEL SERVICIO DE SEGURIDAD Y VIGILANCIA ...",
  "status": "absolucion",
  "source_url": "https://prodapp2.seace.gob.pe/...",

  "documents": [ { /* ClassifiedDocument */ } ],
  "award": null,

  "mode": "preventive",
  "has_tdr_or_bases": true,
  "has_award_document": false,
  "missing_for_graphrag": ["provider_ruc", "award_document"],

  "total_documents": 1,
  "total_pages": 212,
  "documents_with_text": 1,
  "documents_needing_ocr": 0
}
```

### Required top-level fields

| Field | Type | Notes |
|-------|------|-------|
| `pack_id` | string | Unique. Convention: `<entity_slug>_pack_<NNN>` |
| `process_id` | string | **Not** `"unknown"` — validator rejects placeholder |
| `root_path` | string | Directory the pack was scanned from |
| `documents` | array | At least one with `document_type ∈ {tdr, bases, bases_integradas}` |
| `mode` | enum | `preventive` / `investigative` / `unknown` |
| `total_documents` | int | Length of `documents[]` |
| `total_pages` | int | Sum of `documents[].pages_total` |
| `documents_with_text` | int | Count of docs with `pages_with_text > 0` |
| `documents_needing_ocr` | int | Count of docs with `pages_needing_ocr > 0` |

### Strongly-recommended for GraphRAG primary keys

These are not required by the schema but block GraphRAG activation when missing:

| Field | Why |
|-------|-----|
| `ocid` | OCDS process identifier — primary key for OCDS cross-reference |
| `entity_ruc` | 11-digit Peruvian RUC. Validated (must start with `10/15/17/20`) |
| `procedure_code` | Internal procedure code, used for cross-document matching |

### Procedure type vocabulary (`procedure_type`)

| Code | Meaning |
|------|---------|
| `LP` | Licitación Pública |
| `CP` | Concurso Público |
| `AS` | Adjudicación Simplificada |
| `SIE` | Subasta Inversa Electrónica |
| `CD` | Contratación Directa |

### Status vocabulary (`status`)

| Value | Stage |
|-------|-------|
| `convocatoria` | Bases published, no questions yet |
| `absolucion` | Pliego de absolución published |
| `integradas` | Bases integradas published |
| `buena_pro` | Award announced |
| `contrato_suscrito` | Contract signed |
| `ejecucion` | Implementation phase |
| `culminado` | Process closed |

When `status >= "buena_pro"`, the `award` block becomes mandatory.

## Schema — `ClassifiedDocument` (`documents[i]`)

```json
{
  "document_id": "tdr_salud_pliego_001",
  "process_id": "AS-SM-55-2023-ESSALUD-GCL-1",
  "document_type": "absolucion_consultas",
  "file_name": "tdr_salud_pliego_001.pdf",
  "file_path": "data/golden_set/pdfs/tdr_salud_pliego_001.pdf",
  "sha256": "0000...0001",
  "size_bytes": 5419376,
  "pages_total": 212,
  "pages_with_text": 212,
  "pages_needing_ocr": 0,
  "text_coverage_ratio": 1.0,
  "parse_status": "text_ok",
  "ocr_class": "native_text",
  "ocr_status": "not_needed",
  "source_url": null,
  "file_url": null,
  "usable_for_analysis": true,
  "classification_signals": {}
}
```

### Required per-document fields

| Field | Type | Notes |
|-------|------|-------|
| `document_id` | string | Unique within the pack |
| `document_type` | enum | `tdr / bases / bases_integradas / absolucion_consultas / adjudicacion / buena_pro / contrato / anexo / unknown` |
| `file_path` | string | Non-empty. Resolved relative to repo root or absolute |
| `sha256` | string | Non-empty content hash |
| `pages_total` | int | >= 0 |
| `pages_with_text` | int | >= 0, <= pages_total |
| `pages_needing_ocr` | int | >= 0, <= pages_total |
| `text_coverage_ratio` | float | [0.0, 1.0]. If 0.0, `ocr_status` must be `pending/failed/applied` |
| `parse_status` | enum | `text_ok / needs_ocr / parse_error` |
| `usable_for_analysis` | bool | True only if text coverage >= 0.7 |

### Optional per-document fields (recommended)

| Field | Type | Use |
|-------|------|-----|
| `ocr_class` | string | `native_text / partial_scan / full_scan` |
| `ocr_status` | string | `not_needed / pending / applied / failed` |
| `source_url` | string | SEACE listing page the doc was scraped from |
| `file_url` | string | Direct download URL |
| `classification_signals` | object | Internal scoring used by the classifier |

## Schema — `AwardEvidence` (`pack.award`)

Required when `status >= "buena_pro"`:

```json
{
  "supplier_name": "VIPROSEG S.A.C.",
  "supplier_ruc": "20605681281",
  "award_amount": 195383235.96,
  "award_currency": "PEN",
  "award_date": "2024-03-15",
  "award_document_id": "buena_pro_001",
  "award_source_quote": "Se adjudica la buena pro a VIPROSEG S.A.C. por S/ 195'383,235.96",
  "award_source_page": 12,
  "confidence": 0.95
}
```

### Required

| Field | Notes |
|-------|-------|
| `supplier_name` | Non-empty |
| `award_source_quote` | Verbatim quote from the buena_pro document |
| `award_source_page` | >= 1 |

### Optional but strongly recommended

| Field | Why |
|-------|-----|
| `supplier_ruc` | 11-digit RUC, validated. Required for GraphRAG investigative mode |
| `award_document_id` | Must match a `document_id` in `documents[]` |
| `award_amount` + `award_currency` | Triggers high-value flag rules |
| `award_date` | ISO-8601 (YYYY-MM-DD) |
| `confidence` | Extraction confidence [0.0, 1.0] |

## Validator invariants enforced by the engine

Run by `document_intelligence.document_pack.validate_pack(pack)`:

1. `process_id` non-empty and not `"unknown"`.
2. At least one document with type ∈ `{tdr, bases, bases_integradas}`.
3. Every document `file_path` non-empty (`check_file_existence=True` also
   asserts the file exists on disk).
4. Every document `sha256` non-empty.
5. `text_coverage_ratio` in [0, 1]; zero coverage requires `ocr_status` ∈
   `{pending, failed, applied}`.
6. When `award` present:
   - non-empty `award_source_quote` (also enforced by Pydantic `min_length=1`)
   - `award_source_page >= 1`
   - `supplier_ruc`, if set, passes RUC-11 sanity check (starts with `10/15/17/20`)
   - `award_document_id`, if set, exists in `documents[]`
7. `entity_ruc`, if set, passes RUC-11 sanity check.
8. `mode=investigative` requires `award` OR `has_award_document=True`.
9. `mode=preventive` forbids an `award` block.

## How packs feed the AuditorGraph

```python
from document_intelligence.document_pack import (
    load_valid_packs_from_jsonl,
    PackMode,
)
from document_intelligence.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
)
from document_intelligence.agents.score import ScoringContext

packs, rejected = load_valid_packs_from_jsonl(
    "data/scraped/seace_salud/manifests/process_document_packs.example.jsonl"
)

for pack in packs:
    # Pick the primary document (TDR/bases) as analysis target.
    main_doc = next(d for d in pack.documents if d.document_type in {"tdr", "bases", "bases_integradas"})

    ctx = ScoringContext(
        supplier_ruc=pack.award.supplier_ruc if pack.award else None,
        entity_ruc=pack.entity_ruc,
        ocid=pack.ocid,
    )

    orch = AgentOrchestrator(
        OrchestratorConfig(mode="mock", ocr_mode="off"),
        scoring_context=ctx,
    )
    result = orch.analyze_pdf(main_doc.file_path, "Detecta señales...")
    print(pack.pack_id, result.score, result.graph_rag.activation)
```

### GraphRAG gate — what blocks activation

| Pack state | Result |
|-----------|--------|
| `mode=preventive`, no award | `no_primary_key` (no supplier_ruc) → gate closed |
| `mode=investigative`, score < 75 | gate closed regardless |
| `mode=investigative`, score >= 75, supplier_ruc + ocid present | gate **could** open (PR #14+) |
| Invalid pack (validator errors) | engine never sees it — rejected at load time |

PR #13 does NOT activate GraphRAG. It only ensures the pack has the data
that PR #14 would need.

## Required fields by phase

| Field | Convocatoria | Absolución | Integradas | Buena pro | Contrato |
|-------|:-----------:|:----------:|:----------:|:---------:|:--------:|
| `process_id` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ocid` | ⚠️ recommended | ⚠️ | ⚠️ | ✅ | ✅ |
| `entity_name` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `entity_ruc` | ⚠️ | ⚠️ | ⚠️ | ✅ | ✅ |
| TDR/bases document | ✅ | ✅ | ✅ | ✅ | ✅ |
| `award` | ❌ | ❌ | ❌ | ✅ | ✅ |
| `award.supplier_ruc` | n/a | n/a | n/a | ⚠️ | ✅ |

## Versioning

This contract is versioned implicitly via the schemas in
`packages/document_intelligence/src/document_intelligence/document_pack/schemas.py`.
Breaking changes require:

1. Bump `ProcessDocumentPack.schema_version` (if added) or `pack.metadata.schema_version`.
2. Update this doc.
3. Update fixture `process_document_packs.example.jsonl`.
4. Coordinated scraper update before the engine refuses the old format.

## What this contract is NOT about

- ❌ It does not specify how the scraping team obtains the PDFs.
- ❌ It does not commit the engine to any specific GraphRAG activation policy.
- ❌ It does not require Spanish-language doctrine (the engine uses
  language-agnostic regex on the TDR + cross-language doctrine retrieval).
- ❌ It does not include UI / dashboard / viral-content fields. Those live
  in downstream consumers, not in the pack.

## Out of scope (for this PR)

- SUNAT / Contraloría / JNE / El Peruano enrichment.
- Neo4j graph traversal.
- AI-elements / dashboard surfaces.
- Schema versioning machinery.

Those land in PR #14+ once at least three packs from real SEACE scraping
have been delivered against this contract and validated by the engine.
