"""Evidence schemas — TDR citation and doctrine anchor."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """A citation drawn directly from the target document (TDR)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    page_number: int = Field(ge=1)
    quote: str = Field(min_length=1, description="Verbatim excerpt from the source document.")
    cluster: str | None = Field(default=None, description="Cluster label of the originating chunk.")


class DoctrineAnchor(BaseModel):
    """A citation drawn from the doctrinal corpus (OCP, OECD, etc.)."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, description="Human-readable source name and edition.")
    section: str | None = Field(default=None)
    page: int | None = Field(default=None, ge=1)
    quote: str = Field(min_length=1)
    flag_code: str | None = Field(
        default=None,
        description="Doctrinal flag code this anchor formally justifies, when applicable.",
    )


class EvidencePack(BaseModel):
    """A bundled (TDR + doctrine) citation pair for a single flag."""

    model_config = ConfigDict(extra="forbid")

    tdr_evidence: EvidenceItem
    doctrine_anchor: DoctrineAnchor
