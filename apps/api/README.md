# API (FastAPI)

Backend orchestrator connecting three layers:

- **Object storage** — public dossier artifacts.
- **Neo4j** — entity graph.
- **Document Intelligence** — calibrated analysis engine
  (`packages/document_intelligence`) plus on-demand audit graph.

## Endpoints

```
GET  /health                          status + readiness flags
GET  /demo/cases                      catalogue + live counts
GET  /dossiers                        list dossier ids
GET  /dossiers/{ocid}                 full dossier payload
GET  /dossiers/{ocid}/flags           flags only
GET  /dossiers/{ocid}/markdown        rendered markdown
GET  /graph/counts                    graph node/edge totals
GET  /graph/company/{ruc}             company node + metrics
GET  /graph/flags?limit=20            top flag codes
POST /audit/{ocid}                    run audit graph on a stored PDF
```

When `NEO4J_URI` is empty the `/graph/*` routes return 503.
When the analysis stack is not installed, `/audit/*` returns 501.

## Local setup

```bash
cd apps/api
uv venv --python 3.11
uv pip install -e ".[dev]"

# Enable /audit by installing the analysis stack:
uv pip install -e ../../packages/document_intelligence
uv pip install -e ../scrapers

cp .env.example .env  # set credentials
```

## Run

```bash
.venv/bin/uvicorn agenteperry_api.main:app --reload --port 8080
```

Swagger UI: <http://localhost:8080/docs>

## Tests

```bash
.venv/bin/pytest tests/ -q
.venv/bin/ruff check src tests
```

Tests use `unittest.mock` so they do not hit cloud services.

## Deploy

- Container build via the provided `Dockerfile`.
- Configure `NEO4J_URI`, object storage bucket and credentials via environment variables.

## Why FastAPI

- Shares Pydantic models with `document_intelligence`.
- Direct Python imports for the audit orchestrator.
- Automatic OpenAPI + Swagger UI.
