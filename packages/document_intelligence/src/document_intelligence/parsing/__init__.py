"""PDF parsing and text cleaning."""

from __future__ import annotations

from document_intelligence.parsing.header_footer import (
    HeaderFooterReport,
    detect_repeated_lines,
    strip_repeated_lines,
)
from document_intelligence.parsing.ocr import (
    BaseOCRAdapter,
    NoopOCRAdapter,
    OCRMode,
    OCRResult,
    TesseractOCRAdapter,
    get_default_ocr_adapter,
)
from document_intelligence.parsing.pdf_parser import (
    ParseSummary,
    PDFParseError,
    parse_pdf,
    parse_pdf_with_summary,
)
from document_intelligence.parsing.text_cleaner import clean_page_text

__all__ = [
    "BaseOCRAdapter",
    "HeaderFooterReport",
    "NoopOCRAdapter",
    "OCRMode",
    "OCRResult",
    "PDFParseError",
    "ParseSummary",
    "TesseractOCRAdapter",
    "clean_page_text",
    "detect_repeated_lines",
    "get_default_ocr_adapter",
    "parse_pdf",
    "parse_pdf_with_summary",
    "strip_repeated_lines",
]
