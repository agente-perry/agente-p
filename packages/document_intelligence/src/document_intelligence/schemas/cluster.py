"""Cluster schema — thematic grouping of chunks for cluster-routed retrieval."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DocumentCluster(BaseModel):
    """A thematic group of chunks belonging to one canonical section label."""

    model_config = ConfigDict(extra="forbid")

    cluster_id: str
    label: str = Field(description="Canonical label, e.g. 'Entregables', 'Criterios de evaluacion'.")
    summary: str = Field(default="", description="Optional short description of the cluster.")
    chunk_ids: list[str] = Field(default_factory=list)
    top_terms: list[str] = Field(default_factory=list)
