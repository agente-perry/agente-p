"""ProcessDocumentPack validator — enforces SCRAPING_DELIVERY_CONTRACT.md.

A pack is **valid** when every invariant below holds. The validator returns
a list of error strings; callers can short-circuit on any non-empty list.
The validator never raises on input shape; only on actually-malformed packs.

Invariants:

1. ``process_id`` is non-empty and not the placeholder ``"unknown"``.
2. At least one document with type ∈ {tdr, bases, bases_integradas}.
3. Every document's ``file_path`` is non-empty (existence is checked
   separately by ``check_file_existence``).
4. Every document's ``sha256`` is non-empty.
5. Every document's ``text_coverage_ratio`` is in [0.0, 1.0]; if 0, the
   document must declare ``ocr_status="pending"`` or ``"failed"``.
6. When ``award`` is present:
   - ``award.award_source_quote`` is non-empty.
   - ``award.award_source_page >= 1``.
   - ``award.supplier_ruc``, if present, passes RUC-11 sanity check.
   - ``award.award_document_id``, if present, must match a document in
     ``documents[]``.
7. ``entity_ruc``, if present, passes RUC-11 sanity check.
8. ``mode`` is consistent with ``has_award_document`` and ``award``.
"""

from __future__ import annotations

from pathlib import Path

from document_intelligence.document_pack.schemas import (
    DocumentType,
    PackMode,
    ProcessDocumentPack,
)

_TDR_LIKE_TYPES: frozenset[DocumentType] = frozenset(
    {DocumentType.TDR, DocumentType.BASES, DocumentType.BASES_INTEGRADAS}
)


def _looks_like_peruvian_ruc(value: str) -> bool:
    """Sanity check for a Peruvian RUC: 11 digits, starts with 10/15/17/20."""
    if not value or len(value) != 11 or not value.isdigit():
        return False
    return value[:2] in {"10", "15", "17", "20"}


def validate_pack(
    pack: ProcessDocumentPack,
    *,
    check_file_existence: bool = False,
) -> list[str]:
    """Return a list of human-readable error strings; empty list = pack valid.

    Set ``check_file_existence=True`` to also verify that each declared
    ``file_path`` exists on disk. Defaults to False so the same validator
    can be used in tests where paths are intentionally synthetic.
    """
    errors: list[str] = []

    # 1. process_id
    pid = (pack.process_id or "").strip()
    if not pid or pid == "unknown":
        errors.append("process_id missing or set to 'unknown'")

    # 2. has at least one TDR/bases-class document
    tdr_like = [d for d in pack.documents if d.document_type in _TDR_LIKE_TYPES]
    if not tdr_like:
        errors.append(
            "pack must include at least one document of type "
            "tdr / bases / bases_integradas"
        )

    # 3–5. per-document checks
    doc_ids: set[str] = set()
    for doc in pack.documents:
        if not doc.file_path or not doc.file_path.strip():
            errors.append(f"document {doc.document_id}: file_path is empty")
        elif check_file_existence and not Path(doc.file_path).exists():
            errors.append(f"document {doc.document_id}: file not found at {doc.file_path}")
        if not doc.sha256 or not doc.sha256.strip():
            errors.append(f"document {doc.document_id}: sha256 is empty")
        if not (0.0 <= doc.text_coverage_ratio <= 1.0):
            errors.append(
                f"document {doc.document_id}: text_coverage_ratio "
                f"{doc.text_coverage_ratio} out of [0, 1]"
            )
        if doc.text_coverage_ratio == 0.0 and doc.ocr_status not in {"pending", "failed", "applied"}:
            errors.append(
                f"document {doc.document_id}: zero text coverage but "
                f"ocr_status={doc.ocr_status!r} (expected 'pending'/'failed'/'applied')"
            )
        doc_ids.add(doc.document_id)

    # 6. award block
    if pack.award is not None:
        award = pack.award
        if not award.award_source_quote.strip():
            errors.append("award.award_source_quote is empty")
        if award.award_source_page < 1:
            errors.append(f"award.award_source_page={award.award_source_page} < 1")
        if award.supplier_ruc and not _looks_like_peruvian_ruc(award.supplier_ruc):
            errors.append(f"award.supplier_ruc {award.supplier_ruc!r} fails RUC-11 sanity check")
        if award.award_document_id and award.award_document_id not in doc_ids:
            errors.append(
                f"award.award_document_id {award.award_document_id!r} "
                "does not match any document_id in documents[]"
            )

    # 7. entity_ruc sanity
    if pack.entity_ruc and not _looks_like_peruvian_ruc(pack.entity_ruc):
        errors.append(f"entity_ruc {pack.entity_ruc!r} fails RUC-11 sanity check")

    # 8. mode consistency
    if pack.mode == PackMode.INVESTIGATIVE and pack.award is None and not pack.has_award_document:
        errors.append(
            "mode=investigative but pack has no award block and "
            "has_award_document=False"
        )
    if pack.award is not None and pack.mode == PackMode.PREVENTIVE:
        errors.append(
            "pack has award block but mode=preventive (should be investigative)"
        )

    return errors


def assert_valid(pack: ProcessDocumentPack, *, check_file_existence: bool = False) -> None:
    """Raise ``ValueError`` aggregating every validation issue."""
    errs = validate_pack(pack, check_file_existence=check_file_existence)
    if errs:
        raise ValueError("ProcessDocumentPack validation failed:\n  - " + "\n  - ".join(errs))
