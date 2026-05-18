"""Plan-time schemas: document map, retrieval plan, retrieval results."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DocumentSection(BaseModel):
    """A canonical section detected in a TDR."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, description="Canonical label, e.g. 'Entregables'.")
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    heading_raw: str | None = Field(
        default=None,
        description="Verbatim heading text that triggered the detection.",
    )


class TDRMap(BaseModel):
    """Structural map of a TDR produced by ``DocumentMapperAgent``."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    sections: list[DocumentSection] = Field(default_factory=lambda: [])
    unmatched_pages: list[int] = Field(
        default_factory=lambda: [],
        description="Pages that did not fall under any detected section.",
    )


class FlagQuery(BaseModel):
    """A single retrieval query produced by ``PlannerAgent``."""

    model_config = ConfigDict(extra="forbid")

    flag_code: str
    query_text: str
    target_clusters: list[str] = Field(
        default_factory=lambda: [],
        description="Cluster labels to filter against; empty means no filter.",
    )
    doctrine_anchor_id: str | None = Field(
        default=None,
        description="Doctrine chunk_id whose definition motivates this query.",
    )


class PlannerAudit(BaseModel):
    """Auditable trace proving the planner consulted doctrine before TDR retrieval."""

    model_config = ConfigDict(extra="forbid")

    doctrine_consulted_first: bool
    doctrine_hits_count: int
    candidate_flags: list[str] = Field(default_factory=lambda: [])
    notes: str = ""
    expansion_sources: list[str] = Field(
        default_factory=lambda: [],
        description="Names of intent rules and/or fallbacks that contributed candidate flags.",
    )
    intent_matches: list[str] = Field(
        default_factory=lambda: [],
        description="Intent definitions whose trigger phrases matched the question.",
    )


class RetrievalPlan(BaseModel):
    """Plan produced by ``PlannerAgent``: which clusters and queries to run."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    question: str
    clusters_to_query: list[str] = Field(default_factory=lambda: [])
    queries: list[FlagQuery] = Field(default_factory=lambda: [])
    audit: PlannerAudit


class RetrievalHitRecord(BaseModel):
    """Serializable form of a ``RetrievalHit`` for downstream agents."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    page_start: int
    page_end: int
    text_excerpt: str
    score: float
    vector_score: float
    bm25_score: float
    cluster_hint: str | None = None


class RetrievalResult(BaseModel):
    """Hits returned for a single ``FlagQuery``."""

    model_config = ConfigDict(extra="forbid")

    flag_code: str
    query_text: str
    target_clusters: list[str] = Field(default_factory=lambda: [])
    hits: list[RetrievalHitRecord] = Field(default_factory=lambda: [])
    doctrine_anchor_id: str | None = Field(
        default=None,
        description="Doctrine chunk_id that justified this query (from FlagQuery.doctrine_anchor_id).",
    )
