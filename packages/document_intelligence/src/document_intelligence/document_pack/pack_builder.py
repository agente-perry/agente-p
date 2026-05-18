"""Build a :class:`~document_intelligence.document_pack.schemas.ProcessDocumentPack`.

Orchestrates:
  1. ``build_inventory``  — scan PDFs
  2. ``classify_document`` — heuristic type assignment
  3. ``parse_pdf`` + ``chunk_document`` + ``build_clusters`` — chunk & cluster
  4. Mode inference (preventive / investigative / unknown)
  5. Missing-GraphRAG-key detection
  6. Write all artefacts to ``output_dir``
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from document_intelligence.agents import build_clusters
from document_intelligence.chunking import chunk_document
from document_intelligence.document_pack.classifier import classify_document
from document_intelligence.document_pack.inventory import build_inventory
from document_intelligence.document_pack.schemas import (
    ClassifiedDocument,
    DocumentType,
    InventoryItem,
    MissingGraphRAGKey,
    PackMode,
    ProcessDocumentPack,
)
from document_intelligence.parsing import (
    OCRMode,
    PDFParseError,
    parse_pdf,
)
from document_intelligence.schemas import DocumentChunk, DocumentCluster

from .pack_graph import build_graph

logger = logging.getLogger(__name__)

_ALL_ARTIFACTS = [
    "pdf_inventory.json",
    "document_manifest.json",
    "process_document_pack.json",
    "document_pack_graph.json",
    "clusters.json",
    "chunks.jsonl",
    "parse_report.json",
    "pack_summary.md",
]


def _derive_pack_id(root_path: Path, counter: int = 1) -> str:
    stem = root_path.name.strip().lower().replace(" ", "_").replace("-", "_")
    stem = "".join(c if c.isalnum() or c == "_" else "" for c in stem)
    if not stem:
        stem = "pdfbase"
    return f"{stem}_pack_{counter:03d}"


def _infer_mode(pack: ProcessDocumentPack) -> PackMode:
    if not pack.has_tdr_or_bases:
        return PackMode.UNKNOWN
    if pack.has_award_document:
        return PackMode.INVESTIGATIVE
    return PackMode.PREVENTIVE


def _detect_missing_keys(pack: ProcessDocumentPack) -> list[MissingGraphRAGKey]:
    missing: list[MissingGraphRAGKey] = []
    if not pack.has_award_document:
        missing.append(MissingGraphRAGKey.AWARD_DOCUMENT)
    return missing


def _build_classified(
    item: InventoryItem,
    document_type: DocumentType,
    signals: dict[str, Any],
) -> ClassifiedDocument:
    return ClassifiedDocument(
        document_id=item.document_id,
        document_type=document_type,
        file_name=item.file_name,
        file_path=item.file_path,
        sha256=item.sha256,
        size_bytes=item.size_bytes,
        pages_total=item.pages_total,
        pages_with_text=item.pages_with_text,
        pages_needing_ocr=item.pages_needing_ocr,
        parse_status=item.parse_status,
        usable_for_analysis=item.usable_for_analysis,
        classification_signals=signals,
    )


def _chunk_and_cluster(
    item: InventoryItem,
) -> tuple[list[DocumentChunk], list[DocumentCluster]]:
    if not item.usable_for_analysis:
        return [], []
    try:
        ref, pages = parse_pdf(Path(item.file_path))
        chunks = chunk_document(ref, pages)
        if not chunks:
            return [], []
        labelled, clusters = build_clusters(chunks)
        return labelled, clusters
    except PDFParseError:
        logger.warning("Could not chunk %s — skipping", item.file_name)
        return [], []


def build_pack(
    root_path: Path,
    output_dir: Path,
    *,
    ocr_mode: OCRMode = "off",
    max_docs: int | None = None,
    pack_id: str | None = None,
    pretty: bool = False,
) -> ProcessDocumentPack:
    """Build a ProcessDocumentPack and write all artefacts to ``output_dir``.

    Parameters
    ----------
    root_path:
        Directory containing PDF files to ingest.
    output_dir:
        Directory where all artefacts will be written.
        Created if it does not exist.
    ocr_mode:
        Passed through to :func:`document_intelligence.parsing.parse_pdf`.
        Defaults to ``"off"`` (no OCR attempted).
    max_docs:
        Optional cap on the number of PDFs processed.
    pack_id:
        Override the auto-generated pack ID.
    pretty:
        Format JSON artefacts with indentation when ``True``.

    Returns
    -------
    ProcessDocumentPack
        The fully-constructed pack.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_items = build_inventory(root_path, ocr_mode=ocr_mode, max_docs=max_docs)
    inventory_items: list[InventoryItem] = []
    classified_docs: list[ClassifiedDocument] = []
    all_chunks: list[DocumentChunk] = []
    all_clusters: list[DocumentCluster] = []
    parse_errors = 0
    docs_with_text = 0
    docs_needing_ocr = 0

    for item in raw_items:
        dtype, signals = classify_document(Path(item.file_path))
        cd = _build_classified(item, dtype, signals)
        classified_docs.append(cd)
        inventory_items.append(item)
        if item.parse_status.value == "parse_error":
            parse_errors += 1
        if item.pages_with_text > 0:
            docs_with_text += 1
        if item.pages_needing_ocr > 0:
            docs_needing_ocr += 1

        chunks, clusters = _chunk_and_cluster(item)
        all_chunks.extend(chunks)
        all_clusters.extend(clusters)

    has_tdr_or_bases = any(
        dt.document_type
        in {
            DocumentType.TDR,
            DocumentType.BASES,
            DocumentType.BASES_INTEGRADAS,
        }
        for dt in classified_docs
    )
    has_award = any(
        dt.document_type
        in {
            DocumentType.ADJUDICACION,
            DocumentType.BUENA_PRO,
            DocumentType.CONTRATO,
        }
        for dt in classified_docs
    )

    if pack_id is None:
        pack_id = _derive_pack_id(root_path)

    pack = ProcessDocumentPack(
        pack_id=pack_id,
        root_path=str(root_path.resolve()),
        documents=classified_docs,
        has_tdr_or_bases=has_tdr_or_bases,
        has_award_document=has_award,
        total_documents=len(classified_docs),
        total_pages=sum(d.pages_total for d in classified_docs),
        documents_with_text=docs_with_text,
        documents_needing_ocr=docs_needing_ocr,
    )
    pack.mode = _infer_mode(pack)
    pack.missing_for_graphrag = _detect_missing_keys(pack)

    indent = 2 if pretty else None

    graph = build_graph(pack, all_chunks, all_clusters)
    _write_json(output_dir / "document_pack_graph.json", graph, indent)

    _write_json(output_dir / "pdf_inventory.json", inventory_items, indent)
    _write_json(output_dir / "document_manifest.json", classified_docs, indent)
    _write_json(output_dir / "process_document_pack.json", pack, indent)
    _write_clusters(output_dir / "clusters.json", all_clusters, indent)
    _write_chunks(output_dir / "chunks.jsonl", all_chunks)
    _write_parse_report(
        output_dir / "parse_report.json",
        inventory_items,
        parse_errors,
        docs_with_text,
        docs_needing_ocr,
        indent,
    )
    _write_pack_summary(output_dir / "pack_summary.md", pack, all_chunks, all_clusters)

    return pack


def _serialize_item(obj: object) -> dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")  # type: ignore[return-value, attr-defined]
    if hasattr(obj, "to_dict"):
        return obj.to_dict()  # type: ignore[return-value, attr-defined]
    if hasattr(obj, "to_inventory_dict"):
        return obj.to_inventory_dict()  # type: ignore[return-value, attr-defined]
    if hasattr(obj, "to_manifest_dict"):
        return obj.to_manifest_dict()  # type: ignore[return-value, attr-defined]
    return obj  # type: ignore[return-value]


def _write_json(path: Path, data: object, indent: int | None) -> None:
    if isinstance(data, list):
        serializable: Any = [_serialize_item(item) for item in data]
    else:
        serializable = _serialize_item(data)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(serializable, fh, ensure_ascii=False, indent=indent)

    logger.info("Wrote %s", path.name)


def _write_clusters(path: Path, clusters: list[DocumentCluster], indent: int | None) -> None:
    serializable = [_serialize_item(c) for c in clusters]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(serializable, fh, ensure_ascii=False, indent=indent)
    logger.info("Wrote %s (%d clusters)", path.name, len(clusters))


def _write_chunks(path: Path, chunks: list[DocumentChunk]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for chunk in chunks:
            fh.write(json.dumps(_serialize_item(chunk), ensure_ascii=False) + "\n")
    logger.info("Wrote %s (%d chunks)", path.name, len(chunks))


def _write_parse_report(
    path: Path,
    items: list[InventoryItem],
    errors: int,
    with_text: int,
    needing_ocr: int,
    indent: int | None,
) -> None:
    report = {
        "total_pdfs": len(items),
        "parse_errors": errors,
        "documents_with_text": with_text,
        "documents_needing_ocr": needing_ocr,
        "inventory": [item.to_inventory_dict() for item in items],
    }
    with path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=indent)
    logger.info("Wrote %s", path.name)


def _write_pack_summary(
    path: Path,
    pack: ProcessDocumentPack,
    chunks: list[DocumentChunk],
    clusters: list[DocumentCluster],
) -> None:
    lines = [
        f"# Document Pack Summary — {pack.pack_id}",
        "",
        f"**Root:** `{pack.root_path}`",
        f"**Mode:** `{pack.mode.value}`",
        f"**Documents:** {pack.total_documents} total · {pack.documents_with_text} with text · {pack.documents_needing_ocr} need OCR",
        f"**Pages:** {pack.total_pages}",
        "",
        "## Documents",
    ]
    for doc in pack.documents:
        lines.append(
            f"- `{doc.file_name}` → *{doc.document_type.value}* "
            f"(pages: {doc.pages_total}, usable: {doc.usable_for_analysis})"
        )
    lines += [
        "",
        "## Missing for GraphRAG",
    ]
    if not pack.missing_for_graphrag:
        lines.append("- *none*")
    else:
        for k in pack.missing_for_graphrag:
            lines.append(f"- {k.value}")
    lines += [
        "",
        f"**Clusters:** {len(clusters)}",
        f"**Chunks:** {len(chunks)}",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote %s", path.name)