# PLAN — SPEC-0008 SUNAT Padrón Enrichment

## Arquitectura

```
sunat.gob.pe/descargaPRR/mrc137_padron_reducido.html
        │ HTML scrape (discover ZIP link)
        ▼
SUNAT_PADRON_URL
        │ wget/curl o collector.download()
        ▼
data/raw/sunat_padron/sunat_padron.zip   (cached, sha256 tracked)
        │ zipfile.extract → .txt
        ▼
sunat_padron.txt (ISO-8859-1, pipe '|', 14.5M rows)
        │ iter_sunat_rows() → generator de dicts
        ▼
sunat_row_to_result() → CollectionResult
        │
        ▼
records.jsonl  (source_records-compatible)
        │
        ▼
Batch UPSERT into source_records (Postgres)
  ON CONFLICT (external_id) DO UPDATE
        │
        ▼
enrich_companies_from_sunat()
  SELECT source_entities.company WHERE canonical_id = sunat.entity_ruc
  UPDATE metadata (non-destructive merge)
        │
        ▼
source_entities enriched with SUNAT metadata
        │
        ▼
audit.json
```

## Modelo de datos

### SUNAT source_records

| Campo | Fuente | Nota |
|-------|--------|------|
| `source_id` | FK `source_catalog` | `sunat_padron` |
| `external_id` | `ruc` | 11 dígitos |
| `record_type` | `"company"` | |
| `entity_ruc` | `ruc` | 11 dígitos |
| `entity_name` | `razon_social` | |
| `parsed_data` | JSONB | `{ruc, razon_social, estado, condicion, ubigeo, domicilio_fiscal}` |
| `region` | `ubigeo[:2]` | Departamento |
| `raw_data` | dict completo | Todas las columnas del TXT |
| `checksum` | SHA256 del ZIP | |
| `source_url` | `SUNAT_PADRON_URL` | |

### Enrichment de source_entities.company

Cuando `source_entities.canonical_id = source_records.entity_ruc` (de SUNAT):

```sql
UPDATE source_entities
SET metadata = metadata || {
  'ocds_name': existing_display_name,
  'sunat_razon_social': record.entity_name,
  'sunat_estado': parsed_data->>'estado',
  'sunat_condicion': parsed_data->>'condicion',
  'sunat_ubigeo': parsed_data->>'ubigeo',
  'sunat_domicilio_fiscal': parsed_data->>'domicilio_fiscal',
  'sunat_last_seen_at': now()
},
sources = ARRAY(SELECT DISTINCT unnest(sources || ARRAY['sunat_padron']))
WHERE entity_type = 'company' AND canonical_id = %s;
```

**Reglas:**
1. `display_name` NO se modifica. Se preserva el nombre que OCDS registró.
2. Si company no existía (nuevo RUC), se crea como entidad nueva con `display_name = sunat.razon_social`.
3. `sources` es merge sin duplicar.
4. Si parsed_data ya tenía `ocds_name`, no se sobreescribe.

## Implementación

### Pasos del pipeline

```bash
# 1. Collect
uv run agenteperry sources pipeline sunat_padron --limit 1000

# Internamente:
# Step 1: collect → results (list[CollectionResult])
# Step 2: records.jsonl → upsert_source_records()
# Step 3: map_records_to_graph() → graph.json (company entities)
# Step 4: upsert_entities() + upsert_relationships()
# Step 5: enrich_companies_from_sunat() (nuevo para SUNAT)
# Step 6: _build_sunat_audit() → audit.json
```

### Pseudocódigo `enrich_companies_from_sunat()`

```python
def enrich_companies_from_sunat(records_jsonl: Path, batch_size: int = 500) -> dict[str, int]:
    sunat_records = load_sunat_records(records_jsonl)  # solo source_code == sunat_padron
    rucs = [r["entity_ruc"] for r in sunat_records if r["entity_ruc"]]

    # Cargar companies existentes de OCDS
    existing = db.execute(
        "SELECT id, canonical_id, display_name, metadata, sources "
        "FROM source_entities WHERE entity_type = 'company' AND canonical_id = ANY(%s)",
        (rucs,)
    )
    existing_by_ruc = {r["canonical_id"]: r for r in existing}

    enriched = 0
    created = 0
    errors = []

    for record in sunat_records:
        ruc = record.get("entity_ruc")
        if not ruc:
            continue

        parsed = record.get("parsed_data", {})
        existing = existing_by_ruc.get(ruc)

        if existing:
            # UPDATE no destructivo
            metadata = dict(existing["metadata"])
            metadata["ocds_name"] = existing["display_name"]
            metadata["sunat_razon_social"] = record.get("entity_name")
            metadata["sunat_estado"] = parsed.get("estado")
            metadata["sunat_condicion"] = parsed.get("condicion")
            metadata["sunat_ubigeo"] = parsed.get("ubigeo")
            metadata["sunat_domicilio_fiscal"] = parsed.get("domicilio_fiscal")
            metadata["sunat_last_seen_at"] = now_iso()

            sources = sorted(set(existing["sources"] + ["sunat_padron"]))

            db.execute(
                "UPDATE source_entities SET metadata = %s, sources = %s WHERE id = %s",
                (json.dumps(metadata), sources, existing["id"])
            )
            enriched += 1
        else:
            # CREATE nueva entidad
            db.execute(
                "INSERT INTO source_entities (entity_type, canonical_id, display_name, metadata, sources) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (canonical_id) DO NOTHING",
                (
                    "company", ruc, record.get("entity_name"),
                    json.dumps({
                        "sunat_razon_social": record.get("entity_name"),
                        "sunat_estado": parsed.get("estado"),
                        "sunat_condicion": parsed.get("condicion"),
                        "sunat_ubigeo": parsed.get("ubigeo"),
                        "sunat_domicilio_fiscal": parsed.get("domicilio_fiscal"),
                        "sunat_last_seen_at": now_iso(),
                    }),
                    ["sunat_padron"],
                )
            )
            created += 1

    return {
        "companies_enriched": enriched,
        "companies_created": created,
        "errors": len(errors),
    }
```

## Performance

| Métrica | Target | Nota |
|---------|--------|------|
| Descarga 200MB | < 60s | Solo si se corre full |
| Parse 1000 filas | < 1s | Limit smoke test |
| Enrichment 1000 companies | < 2s | UPDATE batch |
| Full 14.5M | Evaluar | No es objetivo de este spec |

## Tests obligatorios

1. `test_sunat_padron_parser_ruc_validation()` — RUC de 11 dígitos vs inválido.
2. `test_sunat_padron_parser_encoding_n_tilde()` — `COMPAÑIA SEÑOR DEL VALLE`.
3. `test_sunat_enrichment_preserves_ocds_name()` — `display_name` OCDS no cambia.
4. `test_sunat_enrichment_merges_metadata()` — `sunat_estado` y `ocds_name` coexisten.
5. `test_sunat_audit_metrics()` — `audit.json` contiene `ocds_match_rate`.

## Rollback

```sql
-- Quitar metadata SUNAT de companies
UPDATE source_entities
SET metadata = metadata - 'sunat_razon_social'
                    - 'sunat_estado'
                    - 'sunat_condicion'
                    - 'sunat_ubigeo'
                    - 'sunat_domicilio_fiscal'
                    - 'sunat_last_seen_at',
    sources = array_remove(sources, 'sunat_padron')
WHERE entity_type = 'company';

-- Borrar source_records SUNAT
DELETE FROM source_records
WHERE source_id = (SELECT id FROM source_catalog WHERE source_code = 'sunat_padron');
```

## Branch

```
feat/SPEC-0008-sunat-padron-enrichment
```

## Commit sugerido

```
feat(scrapers): close SUNAT padron enrichment audit (SPEC-0008)
```
