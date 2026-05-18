"""Scan a directory of PDFs and build an inventory with parse metadata.

Produces a list of :class:`~document_intelligence.document_pack.schemas.InventoryItem`
for every ``*.pdf`` found (case-insensitive), computing SHA-256, page counts and
a usable-for-analysis flag without running OCR by default.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from document_intelligence.document_pack.schemas import InventoryItem, ParseStatus
from document_intelligence.parsing import (
    OCRMode,
    PDFParseError,
    parse_pdf_with_summary,
)

logger = logging.getLogger(__name__)

_INVALID_SUFFIXES = {".identifier", ".zone", ".tmp", ".bak"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_valid_pdf(path: Path) -> bool:
    name = path.name.lower()
    if any(name.endswith(s) for s in _INVALID_SUFFIXES):
        return False
    if path.suffix.lower() != ".pdf":
        return False
    return True


def _derive_parse_status(
    pages_with_text: int, pages_needing_ocr: int, error: bool
) -> ParseStatus:
    if error:
        return ParseStatus.PARSE_ERROR
    if pages_with_text > 0:
        return ParseStatus.TEXT_OK
    if pages_needing_ocr > 0:
        return ParseStatus.NEEDS_OCR
    return ParseStatus.TEXT_OK


def build_inventory(
    root_path: Path,
    *,
    ocr_mode: OCRMode = "off",
    max_docs: int | None = None,
) -> list[InventoryItem]:
    """Scan ``root_path`` for PDFs and return inventory items.

    Parameters
    ----------
    root_path:
        Directory containing PDF files.
    ocr_mode:
        OCR mode passed to the parser. Defaults to ``"off"`` — scanned pages
        are recorded as ``needs_ocr`` without attempting recognition.
    max_docs:
        Optional cap on the number of PDFs to process. When supplied only
        the first ``max_docs`` PDFs (sorted by name) are processed.

    Returns
    -------
    list[InventoryItem]
        One entry per discovered PDF, in sorted filename order.
    """
    if not root_path.is_dir():
        raise ValueError(f"Expected a directory, got: {root_path}")

    pdf_files = sorted(p for p in root_path.iterdir() if _is_valid_pdf(p))
    if max_docs is not None:
        pdf_files = pdf_files[:max_docs]

    items: list[InventoryItem] = []
    for pdf_path in pdf_files:
        try:
            sha256 = _sha256(pdf_path)
            stat = pdf_path.stat()
            _, _, summary = parse_pdf_with_summary(
                pdf_path,
                ocr_mode=ocr_mode,
                low_text_threshold=20,
            )
            pages_with_text = summary.pages_with_text
            pages_needing_ocr = summary.pages_needing_ocr
            parse_error = False
        except PDFParseError:
            logger.warning("Failed to parse %s — skipping", pdf_path)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("Unexpected error on %s: %s — skipping", pdf_path, exc)
            continue

        parse_status = _derive_parse_status(pages_with_text, pages_needing_ocr, parse_error)
        usable = pages_with_text > 0 and not parse_error

        doc_id = f"doc_{sha256[:16]}"

        items.append(
            InventoryItem(
                document_id=doc_id,
                file_name=pdf_path.name,
                file_path=str(pdf_path.resolve()),
                sha256=sha256,
                size_bytes=stat.st_size,
                pages_total=summary.pages_total if not parse_error else 0,
                pages_with_text=pages_with_text,
                pages_needing_ocr=pages_needing_ocr,
                parse_status=parse_status,
                usable_for_analysis=usable,
            )
        )

    return items