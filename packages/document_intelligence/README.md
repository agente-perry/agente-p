# document_intelligence

Agentic document intelligence core for TDR and public-procurement analysis.

## Install (dev)

```bash
cd packages/document_intelligence
pip install -e ".[dev]"
```

## CLI

```bash
python -m document_intelligence inspect-pdf path/to/base.pdf
python -m document_intelligence chunk-pdf path/to/base.pdf --max-chars 1200 --overlap 160
python -m document_intelligence build-index path/to/base.pdf --query "entregables fisicos"
```

All commands run without API keys.

## Layout

```
src/document_intelligence/
  schemas/        Pydantic v2 contracts shared across agents
  parsing/        PyMuPDF page extraction + text cleanup
  chunking/       Cross-page chunker with page provenance
  embeddings/     Embedder protocol + deterministic fake for tests
  retrieval/      Vector index for chunk retrieval
  agents/         Planner, evidence critic, risk scoring, orchestrator
  doctrine/       Doctrine index for legal precedents
  cli.py          Click CLI entry-point
```

## Tests

```bash
pytest packages/document_intelligence/tests/ -q
```
