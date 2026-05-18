"""Tests for document_pack/pack_graph.py."""

from __future__ import annotations

from document_intelligence.document_pack.pack_graph import build_graph
from document_intelligence.document_pack.schemas import (
    ClassifiedDocument,
    DocumentType,
    InventoryItem,
    MissingGraphRAGKey,
    PackMode,
    ParseStatus,
    ProcessDocumentPack,
)


def _make_minimal_pack(
    doc_types: list[DocumentType],
    missing_keys: list[MissingGraphRAGKey] | None = None,
) -> ProcessDocumentPack:
    docs = []
    for i, dtype in enumerate(doc_types):
        item = InventoryItem(
            document_id=f"doc_{i:03d}",
            file_name=f"doc_{i}.pdf",
            file_path=f"/tmp/doc_{i}.pdf",
            sha256="a" * 64,
            size_bytes=1024,
            pages_total=10,
            pages_with_text=5,
            pages_needing_ocr=5,
            parse_status=ParseStatus.TEXT_OK,
            usable_for_analysis=True,
        )
        cd = ClassifiedDocument(
            document_id=item.document_id,
            document_type=dtype,
            file_name=item.file_name,
            file_path=item.file_path,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
            pages_total=item.pages_total,
            pages_with_text=item.pages_with_text,
            pages_needing_ocr=item.pages_needing_ocr,
            parse_status=item.parse_status,
            usable_for_analysis=item.usable_for_analysis,
        )
        docs.append(cd)

    pack = ProcessDocumentPack(
        pack_id="test_pack_001",
        root_path="/tmp",
        documents=docs,
        has_tdr_or_bases=any(
            d in {DocumentType.TDR, DocumentType.BASES, DocumentType.BASES_INTEGRADAS}
            for d in doc_types
        ),
        has_award_document=any(
            d in {DocumentType.ADJUDICACION, DocumentType.BUENA_PRO, DocumentType.CONTRATO}
            for d in doc_types
        ),
        total_documents=len(docs),
        total_pages=sum(d.pages_total for d in docs),
        documents_with_text=len(docs),
        documents_needing_ocr=len(docs),
        mode=PackMode.UNKNOWN,
        missing_for_graphrag=missing_keys or [],
    )
    return pack


class TestGraphNodes:
    def test_graph_has_process_pack_node(self) -> None:
        pack = _make_minimal_pack([])
        graph = build_graph(pack)
        node_types = {n.node_type for n in graph.nodes}
        assert "process_pack" in node_types

    def test_graph_has_document_nodes(self) -> None:
        pack = _make_minimal_pack([DocumentType.TDR, DocumentType.BASES])
        graph = build_graph(pack)
        node_types = {n.node_type for n in graph.nodes}
        assert "document" in node_types
        doc_nodes = [n for n in graph.nodes if n.node_type == "document"]
        assert len(doc_nodes) == 2

    def test_missing_key_node_when_missing(self) -> None:
        pack = _make_minimal_pack(
            [DocumentType.TDR],
            missing_keys=[MissingGraphRAGKey.AWARD_DOCUMENT],
        )
        graph = build_graph(pack)
        node_types = {n.node_type for n in graph.nodes}
        assert "missing_key" in node_types

    def test_process_pack_node_label_is_pack_id(self) -> None:
        pack = _make_minimal_pack([])
        graph = build_graph(pack)
        pack_node = next(n for n in graph.nodes if n.node_type == "process_pack")
        assert pack_node.label == "test_pack_001"


class TestGraphEdges:
    def test_pack_contains_document_edge(self) -> None:
        pack = _make_minimal_pack([DocumentType.TDR])
        graph = build_graph(pack)
        rels = {e.relationship for e in graph.edges}
        assert "PACK_CONTAINS_DOCUMENT" in rels

    def test_document_needs_ocr_edge_when_pages_need_ocr(self) -> None:
        pack = _make_minimal_pack([DocumentType.TDR])
        graph = build_graph(pack)
        ocr_edges = [e for e in graph.edges if e.relationship == "DOCUMENT_NEEDS_OCR"]
        assert len(ocr_edges) == 1

    def test_no_document_needs_ocr_edge_when_no_pages_need_ocr(self) -> None:
        item = InventoryItem(
            document_id="doc_clean",
            file_name="clean.pdf",
            file_path="/tmp/clean.pdf",
            sha256="b" * 64,
            size_bytes=1024,
            pages_total=5,
            pages_with_text=5,
            pages_needing_ocr=0,
            parse_status=ParseStatus.TEXT_OK,
            usable_for_analysis=True,
        )
        cd = ClassifiedDocument(
            document_id=item.document_id,
            document_type=DocumentType.TDR,
            file_name=item.file_name,
            file_path=item.file_path,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
            pages_total=item.pages_total,
            pages_with_text=item.pages_with_text,
            pages_needing_ocr=item.pages_needing_ocr,
            parse_status=item.parse_status,
            usable_for_analysis=item.usable_for_analysis,
        )
        pack = ProcessDocumentPack(
            pack_id="test_pack_002",
            root_path="/tmp",
            documents=[cd],
            has_tdr_or_bases=True,
            has_award_document=False,
            total_documents=1,
            total_pages=5,
            documents_with_text=1,
            documents_needing_ocr=0,
            mode=PackMode.PREVENTIVE,
            missing_for_graphrag=[MissingGraphRAGKey.AWARD_DOCUMENT],
        )
        graph = build_graph(pack)
        ocr_edges = [e for e in graph.edges if e.relationship == "DOCUMENT_NEEDS_OCR"]
        assert len(ocr_edges) == 0

    def test_pack_missing_key_edge(self) -> None:
        pack = _make_minimal_pack(
            [DocumentType.TDR],
            missing_keys=[MissingGraphRAGKey.PROVIDER_RUC],
        )
        graph = build_graph(pack)
        missing_edges = [e for e in graph.edges if e.relationship == "PACK_MISSING_KEY"]
        assert len(missing_edges) == 1
        assert missing_edges[0].source_id.endswith("process_pack::root")
        assert "provider_ruc" in missing_edges[0].target_id

    def test_edge_ids_are_unique(self) -> None:
        pack = _make_minimal_pack([DocumentType.TDR, DocumentType.BASES])
        graph = build_graph(pack)
        edge_ids = [e.edge_id for e in graph.edges]
        assert len(edge_ids) == len(set(edge_ids))