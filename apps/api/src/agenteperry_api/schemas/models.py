"""API request/response models. All read-only; no DB writes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    api_version: str
    gcs_bucket: str
    neo4j_enabled: bool
    auditor_available: bool


class DossierIndexItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocid: str
    has_dossier_json: bool
    has_dossier_md: bool
    has_flags_json: bool
    has_pages_json: bool
    has_chunks_json: bool


class CompanyGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ruc: str
    name: str | None = None
    estado: str | None = None
    condicion: str | None = None
    total_contracts: int = 0
    total_won_pen: float = 0.0
    risk_score_v2: float | None = None
    flags: list[str] = Field(default_factory=list)


class FlagAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_code: str
    company_count: int
    sample_companies: list[str] = Field(default_factory=list)


class GraphCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: dict[str, int] = Field(default_factory=dict)
    edges: dict[str, int] = Field(default_factory=dict)


class AuditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sector: str | None = None
    entity_name: str | None = None
    procedure_code: str | None = None
    monto: float | None = None
    # When provided, overrides the GCS blob path lookup.
    explicit_pdf_path: str | None = None


class AuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocid: str
    status: str
    risk_level: str | None = None
    score: int | None = None
    total_pages: int | None = None
    coverage_pct: float | None = None
    audit_trace: list[dict[str, Any]] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)


class DemoCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ocid: str
    title: str
    sector: str
    entity_name: str
    risk_level: str
    score: int
    flag_count: int
    headline_quote: str | None = None
    headline_page: int | None = None
    supplier_name: str | None = None
    supplier_ruc: str | None = None
