"""FastAPI entry point.

Run locally:

    uvicorn agenteperry_api.main:app --reload --port 8080
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agenteperry_api import __version__
from agenteperry_api.config import get_settings
from agenteperry_api.routers import audit, demo, dossiers, graph, health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.api_title,
        version=__version__,
        description=(
            "Backend layer between the GCP data lake (gs://agente-perry-data-prod/), "
            "the Neo4j AuraDB graph and the document_intelligence agent stack. "
            "Read-only by default; the /audit endpoints trigger an on-demand "
            "LangGraph AuditorGraph run when the document_intelligence + agenteperry "
            "packages are present in the venv."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(demo.router)
    app.include_router(dossiers.router)
    app.include_router(graph.router)
    app.include_router(audit.router)
    return app


app = create_app()


def main() -> int:
    import uvicorn

    settings = get_settings()  # noqa: F841 — eager-load to fail fast on bad env
    uvicorn.run("agenteperry_api.main:app", host="0.0.0.0", port=8080, reload=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
