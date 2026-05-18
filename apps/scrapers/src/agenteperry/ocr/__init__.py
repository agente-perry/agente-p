"""OCR module for AgentePerry."""

from agenteperry.ocr.bridge import (
    AnalyzerPrepareResult,
    BridgeResult,
    LoaderPrepareResult,
    build_ocr_bridge_bundles,
    prepare_analyzer_bundles,
    prepare_loader_inputs,
)
from agenteperry.ocr.cli import ocr_group
from agenteperry.ocr.minimax_client import MinimaxOCRClient
from agenteperry.ocr.models import (
    OcrDocumentStatus,
    OcrManifest,
    OcrPageResult,
    OcrPageStatus,
    PdfClassification,
    PdfOcrClass,
)
from agenteperry.ocr.pdf_classifier import classify_pdf, classify_pdf_dir
from agenteperry.ocr.processor import OcrProcessor, process_many

__all__ = [
    "MinimaxOCRClient",
    "BridgeResult",
    "AnalyzerPrepareResult",
    "LoaderPrepareResult",
    "OcrDocumentStatus",
    "OcrManifest",
    "OcrPageResult",
    "OcrPageStatus",
    "OcrProcessor",
    "PdfClassification",
    "PdfOcrClass",
    "classify_pdf",
    "classify_pdf_dir",
    "build_ocr_bridge_bundles",
    "prepare_analyzer_bundles",
    "prepare_loader_inputs",
    "ocr_group",
    "process_many",
]
