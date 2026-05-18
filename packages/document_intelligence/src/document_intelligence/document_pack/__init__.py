"""Document Pack — scan, classify and graph a folder of PDFs into a ProcessDocumentPack."""

from __future__ import annotations

from document_intelligence.document_pack.classifier import classify_document
from document_intelligence.document_pack.inventory import build_inventory
from document_intelligence.document_pack.loader import (
    iter_packs_from_jsonl,
    load_pack_from_json,
    load_valid_packs_from_jsonl,
)
from document_intelligence.document_pack.mode_strategy import (
    PackAnalysisStrategy,
    resolve_strategy,
)
from document_intelligence.document_pack.orchestrator import (
    PackAnalysisResult,
    PackOrchestrator,
    PackOrchestratorConfig,
)
from document_intelligence.document_pack.pack_builder import build_pack
from document_intelligence.document_pack.pack_graph import build_graph
from document_intelligence.document_pack.schemas import (
    AwardEvidence,
    ClassifiedDocument,
    DocumentType,
    InventoryItem,
    MissingGraphRAGKey,
    PackGraph,
    PackGraphEdge,
    PackGraphNode,
    PackMode,
    ParseStatus,
    ProcessDocumentPack,
)
from document_intelligence.document_pack.validator import assert_valid, validate_pack

__all__ = [
    "assert_valid",
    "AwardEvidence",
    "build_graph",
    "build_inventory",
    "build_pack",
    "classify_document",
    "ClassifiedDocument",
    "DocumentType",
    "InventoryItem",
    "iter_packs_from_jsonl",
    "load_pack_from_json",
    "load_valid_packs_from_jsonl",
    "MissingGraphRAGKey",
    "PackAnalysisResult",
    "PackAnalysisStrategy",
    "PackGraph",
    "PackGraphEdge",
    "PackGraphNode",
    "PackMode",
    "PackOrchestrator",
    "PackOrchestratorConfig",
    "ParseStatus",
    "ProcessDocumentPack",
    "resolve_strategy",
    "validate_pack",
]