# @agenteperry/scrapers

Python package for TDR ingestion and risk-signal scanning. Handles:

1. Manual TDR metadata ingestion.
2. PDF parsing with PyMuPDF.
3. Text cleaning by page.
4. Chunking with page provenance.
5. Embedding payload preparation.
6. Rule-based flags with evidence quotes.
7. Local smoke-search.

## Setup

```bash
uv sync --extra dev
uv run agenteperry tdr index
```

## Commands

```bash
uv run agenteperry tdr index
uv run agenteperry tdr load-manual ../../data/manual_tdrs/metadata.csv
uv run agenteperry tdr parse ../../storage/raw/tdr/demo.pdf --out ../../storage/processed/tdr/demo.pages.json
uv run agenteperry tdr chunk ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.chunks.json
uv run agenteperry tdr embed-inputs ../../storage/processed/tdr/demo.chunks.json --out ../../storage/processed/tdr/demo.embedding-inputs.json
uv run agenteperry tdr flags ../../storage/processed/tdr/demo.pages.json --out ../../storage/processed/tdr/demo.flags.json
uv run agenteperry tdr smoke-search ../../storage/processed/tdr/demo.chunks.json "formato A3"
```

## Structure

```text
src/agenteperry/
  cli.py
  tdr/
    index.py        human-readable package/command/rule index
    models.py       Pydantic models
    ingestion.py    manual CSV manifest validation + checksums
    parsing.py      PDF text extraction with PyMuPDF
    chunking.py     chunks with page provenance and overlap
    embeddings.py   provider-ready embedding payloads
    flags.py        deterministic TDR signals with evidence
    search.py       local smoke-search
```

## Tests

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests
uv run --extra dev pyright
```

## Data Rules

Real data never goes into Git. Use ignored local folders:

```text
../../data/manual_tdrs/
../../storage/raw/tdr/
../../storage/processed/tdr/
../../downloads/
```
