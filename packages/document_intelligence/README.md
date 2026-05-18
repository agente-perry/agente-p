# document_intelligence

Local-first agentic document intelligence core for TDR / public-procurement analysis.

Status: PR #1 of SPEC-0007 — scaffolding + data layer only. Agents land in PRs #2–#4.

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
  embeddings/     Embedder protocol + deterministic FakeEmbedder
  retrieval/      In-memory cosine index (FAISS lands in PR #2)
  cli.py          Click CLI entry-point
```

## Tests

```bash
pytest packages/document_intelligence/tests/ -q
```

## Spec

See `specs/active/SPEC-0007-document-intelligence-core/` for design, tasks and architecture.
