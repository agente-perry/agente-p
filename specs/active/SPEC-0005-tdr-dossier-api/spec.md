# SPEC-0005: TDR Dossier API

## Objetivo

Exponer un endpoint minimo para que el frontend muestre el analisis de un TDR.

## Endpoint

`GET /api/tdr/{id}`

## Respuesta esperada

```json
{
  "title": "...",
  "entity_name": "...",
  "risk_score": 75,
  "risk_level": "high",
  "flags": [
    {
      "flag_code": "OBSOLETE_PHYSICAL_FORMAT",
      "evidence_quote": "...",
      "page_number": 8,
      "explanation": "..."
    }
  ],
  "questions": ["..."],
  "dossier_path": "/data/results/ocds-dgv273-988512/dossier.md",
  "graph_findings": {
    "supplier_ruc": "20605681281",
    "buyer_ruc": "20131370645",
    "community_size": 3,
    "community_companies": [{"ruc": "20605681281", "name": "CONSORCIO SALUD NORTE"}],
    "shared_persons": ["PERSON-001"],
    "signals": [{"type": "HISTORIAL_SENALES", "description": "3 senales previas", "source": "neo4j"}],
    "risk_delta": 15,
    "flag_count": 3,
    "carousel_detected": true,
    "carousel_details": "3 empresas con mismo representante legal",
    "conflict_of_interest": false,
    "conflict_details": null,
    "error": null
  },
  "graph_enrichment_status": "enriched"
}
```

## Campos nuevos (SPEC-0012 integration)

- `dossier_path` (string|null): Path al archivo dossier.md generado por el CDC pipeline.
- `graph_findings` (object|null): Resultados del enrichment de Neo4j (señales de comunidad, carrusel, conflicto de interés). Generado por `enrich_dossier_with_graph()`.
- `graph_enrichment_status` (enum): `pending` | `enriched` | `error` | `skipped`.

## DB Schema

- `tdr_documents.dossier_path` (text): Path absoluto al dossier.md.
- `tdr_documents.graph_enrichment_status` (text): Estado de enrichment.
- `tdr_documents.graph_findings` (jsonb): JSON con señales, delta, comunidad.
- Migration: `packages/db/migrations/0004_tdr_graph_enrichment.sql`

## Fuera de alcance

- UI final.
- Publicacion automatica.
