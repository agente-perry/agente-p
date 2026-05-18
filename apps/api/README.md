# AgentePerry API (FastAPI)

Backend que conecta tres capas:

- **GCS** — `gs://agente-perry-data-prod/` (data lake del compa).
- **Neo4j AuraDB** — grafo poblado por `ingest/main.py` del repo `agente-p`.
- **Document Intelligence** — motor calibrado (`packages/document_intelligence`) +
  `AuditorGraph` (`apps/scrapers/.../tdr/auditor.py`) para corridas on-demand.

## Endpoints

```
GET  /health                          → status + readiness flags
GET  /demo/cases                      → catalogue hardcoded + live counts
GET  /dossiers                        → lista OCIDs con dossier en GCS
GET  /dossiers/{ocid}                 → dossier.json completo
GET  /dossiers/{ocid}/flags           → flags.json
GET  /dossiers/{ocid}/markdown        → dossier.md + gs:// uri
GET  /graph/counts                    → totales por nodo/edge en Neo4j
GET  /graph/company/{ruc}             → Company + métricas
GET  /graph/flags?limit=20            → top flag_codes
POST /audit/{ocid}                    → corre AuditorGraph sobre PDF de GCS
```

Cuando `NEO4J_URI` está vacío → `/graph/*` retorna 503 (resto sigue OK).
Cuando el stack `document_intelligence + langgraph + agenteperry` no está
en el venv → `/audit/*` retorna 501 (resto sigue OK).

## Setup local

```bash
cd apps/api
uv venv --python 3.11
uv pip install -e ".[dev]"

# Para habilitar /audit, instalar también document_intelligence + agenteperry:
uv pip install -e ../../packages/document_intelligence
uv pip install -e ../scrapers

cp .env.example .env  # editar con credenciales reales
gcloud auth application-default login
gcloud config set project agente-perry
```

## Correr

```bash
.venv/bin/uvicorn agenteperry_api.main:app --reload --port 8080
```

Swagger UI: <http://localhost:8080/docs>.

## Tests

```bash
.venv/bin/pytest tests/ -q
.venv/bin/ruff check src tests
```

Los tests usan `unittest.mock` para no tocar GCS/Neo4j reales.

## Integración con el frontend

El frontend Next.js (`https://github.com/agente-perry/agente-perry`) lee Neo4j
**directo** vía `neo4j-driver`. Esta API añade endpoints que el frontend
puede consumir para:

- `/dossiers/{ocid}` y `/dossiers/{ocid}/markdown` — renderizar dossier ciudadano.
- `/demo/cases` — landing con risk + score real desde GCS.
- `/audit/{ocid}` — botón "Re-auditar con motor calibrado".

Agregar `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080` en `.env.local`
del frontend. Las rutas existentes `/api/grafo`, `/api/alertas`, etc. siguen
hablando a Neo4j directo (compañero); las nuevas usan esta API.

## Deploy

- **Cloud Run** (recomendado): `gcloud run deploy agenteperry-api --source . --region us-central1 --allow-unauthenticated`.
- **Docker**: `docker build -t agenteperry-api . && docker run -p 8080:8080 --env-file .env agenteperry-api`.

Credenciales GCS: usar Workload Identity en Cloud Run (no clave JSON).
Credenciales Neo4j: variable de entorno encriptada.

## Por qué FastAPI y no Express/Hono

- Comparte modelos Pydantic con `document_intelligence` y `document_pack`.
- Tipos JSON sincronizados con el motor sin duplicación.
- `/audit/{ocid}` necesita import directo del orchestrator Python.
- Swagger UI gratis.
- Stack único (Python) reduce surface de errores en hackathon.
