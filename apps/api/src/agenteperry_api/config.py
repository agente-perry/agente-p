"""Pydantic-settings based configuration. Reads .env automatically."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- GCP ---
    gcp_project: str = Field(default="agente-perry")
    gcs_bucket: str = Field(default="agente-perry-data-prod")
    gcs_results_prefix: str = Field(default="scraped/results/")
    gcs_ocds_path: str = Field(default="scraped/ocds/records.jsonl")
    gcs_sunat_path: str = Field(
        default="scraped/collectors/sunat_padron/rucs.jsonl"
    )
    gcs_downloads_prefix: str = Field(default="downloads/")

    # --- Neo4j (compañero's AuraDB graph) ---
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None
    neo4j_database: str = "neo4j"

    # --- API ---
    api_title: str = "AgentePerry API"
    api_version: str = "0.1.0"
    api_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://agente-perry.vercel.app",
        ]
    )
    api_disable_auditor: bool = Field(
        default=False,
        description=(
            "When True, /audit endpoints return 501. Useful for read-only "
            "deployments that do not ship document_intelligence."
        ),
    )

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
