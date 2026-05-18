# Scraping — TDR Ingestion

## MVP Source Strategy

Start with a manual CSV manifest and PDFs saved outside Git. This avoids wasting hackathon time on brittle portals before the core scanner works.

Required CSV columns for `SPEC-0001`:

```csv
external_id,title,entity_name,procedure_code,source_url,file_url,sector,region,district,publication_date,estimated_value
```

## Local Data Layout

```text
data/manual_tdrs/metadata.csv
storage/raw/tdr/<external_id>/<checksum>.pdf
storage/processed/tdr/<external_id>.pages.json
storage/processed/tdr/<external_id>.chunks.json
storage/processed/tdr/<external_id>.flags.json
```

These paths are ignored by Git. Real PDFs and downloaded data must not be committed.

## Commands

```bash
cd apps/scrapers
uv run agenteperry tdr index
uv run agenteperry tdr load-manual ../../data/manual_tdrs/metadata.csv
uv run agenteperry tdr parse ../../storage/raw/tdr/demo.pdf --out ../../storage/processed/tdr/demo.pages.json
uv run agenteperry tdr chunk ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.chunks.json
uv run agenteperry tdr flags ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.flags.json
```

## Deferred Sources

SEACE/OECE crawler, ONPE, JNE, SUNARP, SUNAT and CGR are deferred. Add them only after the TDR pipeline has real parsed documents and evidence-backed flags.
