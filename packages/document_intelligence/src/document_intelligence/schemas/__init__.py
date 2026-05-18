"""Pydantic schemas — single source of truth for agent contracts."""

from __future__ import annotations

from document_intelligence.schemas.analysis import (
    AnalysisResult,
    CriticCritique,
    FlagCandidate,
    FlagRecord,
)
from document_intelligence.schemas.chunk import DocumentChunk
from document_intelligence.schemas.cluster import DocumentCluster
from document_intelligence.schemas.document import DocumentPage, DocumentRef
from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem, EvidencePack
from document_intelligence.schemas.plan import (
    DocumentSection,
    FlagQuery,
    PlannerAudit,
    RetrievalHitRecord,
    RetrievalPlan,
    RetrievalResult,
    TDRMap,
)

__all__ = [
    "AnalysisResult",
    "CriticCritique",
    "DoctrineAnchor",
    "DocumentChunk",
    "DocumentCluster",
    "DocumentPage",
    "DocumentRef",
    "DocumentSection",
    "EvidenceItem",
    "EvidencePack",
    "FlagCandidate",
    "FlagQuery",
    "FlagRecord",
    "PlannerAudit",
    "RetrievalHitRecord",
    "RetrievalPlan",
    "RetrievalResult",
    "TDRMap",
]
