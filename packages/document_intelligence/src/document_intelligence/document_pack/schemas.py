"""Document Pack schemas — ProcessDocumentPack, inventory items, graph."""
# pyright: reportUnknownVariableType=false

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(StrEnum):
    TDR = "tdr"
    BASES = "bases"
    BASES_INTEGRADAS = "bases_integradas"
    ABSOLUCION_CONSULTAS = "absolucion_consultas"
    ADJUDICACION = "adjudicacion"
    BUENA_PRO = "buena_pro"
    CONTRATO = "contrato"
    ANEXO = "anexo"
    UNKNOWN = "unknown"


class ParseStatus(StrEnum):
    TEXT_OK = "text_ok"
    NEEDS_OCR = "needs_ocr"
    PARSE_ERROR = "parse_error"


class PackMode(StrEnum):
    PREVENTIVE = "preventive"
    INVESTIGATIVE = "investigative"
    UNKNOWN = "unknown"


class MissingGraphRAGKey(StrEnum):
    PROVIDER_RUC = "provider_ruc"
    OCID = "ocid"
    ENTITY_NAME = "entity_name"
    AWARD_DOCUMENT = "award_document"


class AwardEvidence(BaseModel):
    """Award (buena pro / adjudicación) evidence extracted from a pack.

    Mandatory fields per SCRAPING_DELIVERY_CONTRACT.md when the procurement
    has already been adjudicated. Without ``supplier_ruc`` GraphRAG cannot
    be activated even in investigative mode.
    """

    model_config = ConfigDict(extra="forbid")

    supplier_name: str = Field(min_length=1)
    supplier_ruc: str | None = Field(
        default=None,
        description="Peruvian RUC (11 digits). Validated by the pack validator.",
    )
    award_amount: float | None = Field(default=None, ge=0.0)
    award_currency: str = Field(default="PEN", min_length=3, max_length=3)
    award_date: str | None = Field(
        default=None,
        description="ISO-8601 date (YYYY-MM-DD).",
    )
    award_document_id: str | None = Field(
        default=None,
        description="document_id of the source PDF inside the pack. "
        "Must match an entry in documents[].",
    )
    award_source_quote: str = Field(
        min_length=1,
        description="Verbatim quote from the award document supporting these fields.",
    )
    award_source_page: int = Field(ge=1)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class InventoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(description="Stable hash-based id from file path + size.")
    file_name: str = Field(description="Original file name.")
    file_path: str = Field(description="Absolute path to the PDF file.")
    sha256: str = Field(description="SHA-256 content hash of the file.")
    size_bytes: int = Field(ge=0, description="File size in bytes.")
    pages_total: int = Field(ge=0, description="Total number of pages.")
    pages_with_text: int = Field(ge=0, description="Pages that have extractable text.")
    pages_needing_ocr: int = Field(ge=0, description="Pages that likely need OCR.")
    parse_status: ParseStatus = Field(
        description="Overall parse status for the document."
    )
    usable_for_analysis: bool = Field(
        description="True when document has usable text for downstream analysis."
    )

    def to_inventory_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ClassifiedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    process_id: str | None = Field(
        default=None,
        description="Parent ProcessDocumentPack.process_id. Set by pack loader.",
    )
    document_type: DocumentType = Field(
        description="Heuristic document type."
    )
    file_name: str
    file_path: str
    sha256: str
    size_bytes: int
    pages_total: int
    pages_with_text: int
    pages_needing_ocr: int
    text_coverage_ratio: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="pages_with_text / pages_total. Auto-computed when missing.",
    )
    parse_status: ParseStatus
    ocr_class: str | None = Field(
        default=None,
        description="OCR coverage class: 'native_text', 'partial_scan', 'full_scan'.",
    )
    ocr_status: str | None = Field(
        default=None,
        description="OCR run outcome: 'not_needed', 'pending', 'applied', 'failed'.",
    )
    source_url: str | None = Field(
        default=None,
        description="Original page from which the document was scraped (SEACE listing, etc.).",
    )
    file_url: str | None = Field(
        default=None,
        description="Direct download URL for the PDF.",
    )
    usable_for_analysis: bool
    classification_signals: dict[str, Any] = Field(
        default_factory=dict,
        description="Internal scoring signals used for classification."
    )

    def to_manifest_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class ProcessDocumentPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(description="Unique pack identifier, e.g. 'pdfbase_pack_001'.")
    root_path: str = Field(description="Root directory that was scanned.")
    sector: str = Field(default="unknown", description="Inferred sector or 'unknown'.")
    process_id: str = Field(
        default="unknown",
        description="Inferred procurement process identifier or 'unknown'.",
    )
    # PR #13 — full process metadata for SCRAPING_DELIVERY_CONTRACT.md.
    ocid: str | None = Field(
        default=None,
        description="OCDS process id (ocds-...). Required for GraphRAG primary key.",
    )
    entity_name: str | None = Field(
        default=None,
        description="Contracting entity human-readable name.",
    )
    entity_ruc: str | None = Field(
        default=None,
        description="Contracting entity RUC (11 digits, validated by pack validator).",
    )
    procedure_code: str | None = Field(
        default=None,
        description="Internal procedure code (e.g. AS-SM-55-2023-ESSALUD-GCL-1).",
    )
    procedure_type: str | None = Field(
        default=None,
        description="Procedure type: 'LP' (Licitación Pública), 'CP' (Concurso "
        "Público), 'AS' (Adjudicación Simplificada), 'SIE' (Subasta Inversa "
        "Electrónica), 'CD' (Contratación Directa).",
    )
    object_description: str | None = Field(
        default=None,
        description="Brief description of the contracting object.",
    )
    status: str | None = Field(
        default=None,
        description="Process status: 'convocatoria', 'absolucion', 'integradas', "
        "'buena_pro', 'contrato_suscrito', 'ejecucion', 'culminado'.",
    )
    source_url: str | None = Field(
        default=None,
        description="SEACE/OCDS process page URL.",
    )
    documents: list[ClassifiedDocument] = Field(default_factory=list)
    award: AwardEvidence | None = Field(
        default=None,
        description="Award evidence when status >= buena_pro.",
    )
    mode: PackMode = Field(
        default=PackMode.UNKNOWN,
        description="'preventive' = TDR/bases only. 'investigative' = bases + winner. "
        "'unknown' = cannot determine.",
    )
    has_tdr_or_bases: bool = Field(
        default=False,
        description="True when at least one TDR or bases document is present.",
    )
    has_award_document: bool = Field(
        default=False,
        description="True when at least one award document is present.",
    )
    missing_for_graphrag: list[MissingGraphRAGKey] = Field(default_factory=list)
    total_documents: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    documents_with_text: int = Field(ge=0)
    documents_needing_ocr: int = Field(ge=0)

    def to_pack_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PackGraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str = Field(description="Unique node identifier.")
    node_type: str = Field(
        description="One of: process_pack, document, page, chunk, semantic_cluster, missing_key."
    )
    label: str = Field(description="Human-readable short label.")
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PackGraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str = Field(description="Unique edge identifier.")
    source_id: str = Field(description="Source node identifier.")
    target_id: str = Field(description="Target node identifier.")
    relationship: str = Field(
        description="One of: PACK_CONTAINS_DOCUMENT, DOCUMENT_HAS_PAGE, "
        "DOCUMENT_HAS_CHUNK, DOCUMENT_HAS_CLUSTER, CLUSTER_CONTAINS_CHUNK, "
        "DOCUMENT_NEEDS_OCR, PACK_MISSING_KEY."
    )
    properties: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PackGraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pack_id: str
    nodes: list[PackGraphNode] = Field(default_factory=list)
    edges: list[PackGraphEdge] = Field(default_factory=list)

    def to_graph_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")