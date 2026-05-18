"""Build a local document-graph from a :class:`ProcessDocumentPack`.

The graph captures containment and needs-OCR relationships in the document set.
It does **not** perform GraphRAG — it is the prerequisite structural index
that a future PlannerAgent would use to decide when and how to activate
external GraphRAG services.

Node types
-----------
``process_pack`` — the top-level pack node
``document``     — a single PDF in the pack
``page``         — a parsed page (only when the page provides a meaningful signal)
``chunk``        — a semantic chunk from a document with usable text
``semantic_cluster`` — a thematic cluster grouping related chunks
``missing_key``  — a required key for GraphRAG that is not present in the pack

Edge types
----------
``PACK_CONTAINS_DOCUMENT``
``DOCUMENT_HAS_PAGE``
``DOCUMENT_HAS_CHUNK``
``DOCUMENT_HAS_CLUSTER``
``CLUSTER_CONTAINS_CHUNK``
``DOCUMENT_NEEDS_OCR``
``PACK_MISSING_KEY``
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from document_intelligence.document_pack.schemas import (
    PackGraph,
    PackGraphEdge,
    PackGraphNode,
    ProcessDocumentPack,
)

if TYPE_CHECKING:
    from document_intelligence.schemas import DocumentChunk, DocumentCluster

logger = logging.getLogger(__name__)

_REL_DOCUMENT_HAS_PAGE_THRESHOLD = 5


def _node_id(pack_id: str, node_type: str, suffix: str) -> str:
    return f"{pack_id}::{node_type}::{suffix}"


def _edge_id(source: str, relationship: str, target: str) -> str:
    return f"{source}--{relationship}--{target}"


def build_graph(
    pack: ProcessDocumentPack,
    chunks: list[DocumentChunk] | None = None,
    clusters: list[DocumentCluster] | None = None,
) -> PackGraph:
    """Build a :class:`PackGraph` from a fully-built :class:`ProcessDocumentPack`.

    Parameters
    ----------
    pack:
        The ProcessDocumentPack to graph. Should already have chunks and clusters
        attached; pass them via ``chunks`` / ``clusters`` args for graph inclusion.
    chunks:
        Optional list of document chunks. When provided, ``DOCUMENT_HAS_CHUNK``
        edges are created.
    clusters:
        Optional list of semantic clusters. When provided, ``DOCUMENT_HAS_CLUSTER``
        and ``CLUSTER_CONTAINS_CHUNK`` edges are created.

    Returns
    -------
    PackGraph
    """
    nodes: list[PackGraphNode] = []
    edges: list[PackGraphEdge] = []

    pack_nid = _node_id(pack.pack_id, "process_pack", "root")
    nodes.append(
        PackGraphNode(
            node_id=pack_nid,
            node_type="process_pack",
            label=pack.pack_id,
            properties={
                "mode": pack.mode.value,
                "root_path": pack.root_path,
                "total_documents": pack.total_documents,
                "total_pages": pack.total_pages,
                "has_tdr_or_bases": pack.has_tdr_or_bases,
                "has_award_document": pack.has_award_document,
            },
        )
    )

    chunk_map: dict[str, list[str]] = {}
    cluster_map: dict[str, list[str]] = {}

    for doc in pack.documents:
        doc_nid = _node_id(pack.pack_id, "document", doc.document_id)
        nodes.append(
            PackGraphNode(
                node_id=doc_nid,
                node_type="document",
                label=doc.file_name,
                properties={
                    "document_id": doc.document_id,
                    "document_type": doc.document_type.value,
                    "pages_total": doc.pages_total,
                    "pages_with_text": doc.pages_with_text,
                    "pages_needing_ocr": doc.pages_needing_ocr,
                    "usable_for_analysis": doc.usable_for_analysis,
                    "parse_status": doc.parse_status.value,
                    "sha256": doc.sha256,
                    "size_bytes": doc.size_bytes,
                },
            )
        )
        edges.append(
            PackGraphEdge(
                edge_id=_edge_id(pack_nid, "PACK_CONTAINS_DOCUMENT", doc_nid),
                source_id=pack_nid,
                target_id=doc_nid,
                relationship="PACK_CONTAINS_DOCUMENT",
            )
        )

        if doc.pages_needing_ocr > 0:
            edges.append(
                PackGraphEdge(
                    edge_id=_edge_id(doc_nid, "DOCUMENT_NEEDS_OCR", "ocr_"),
                    source_id=doc_nid,
                    target_id="ocr_",
                    relationship="DOCUMENT_NEEDS_OCR",
                    properties={"pages_requiring_ocr": doc.pages_needing_ocr},
                )
            )

        if chunks is not None:
            doc_chunks = [c for c in chunks if c.document_id == doc.document_id]
            for chk in doc_chunks:
                chunk_map.setdefault(doc.document_id, []).append(chk.chunk_id)
                chk_nid = _node_id(pack.pack_id, "chunk", chk.chunk_id)
                nodes.append(
                    PackGraphNode(
                        node_id=chk_nid,
                        node_type="chunk",
                        label=chk.section_hint or chk.chunk_id[-8:],
                        properties={
                            "chunk_id": chk.chunk_id,
                            "page_start": chk.page_start,
                            "page_end": chk.page_end,
                            "cluster_label": chk.metadata.get("cluster_label"),
                            "char_count": chk.char_end - chk.char_start,
                        },
                    )
                )
                edges.append(
                    PackGraphEdge(
                        edge_id=_edge_id(doc_nid, "DOCUMENT_HAS_CHUNK", chk_nid),
                        source_id=doc_nid,
                        target_id=chk_nid,
                        relationship="DOCUMENT_HAS_CHUNK",
                    )
                )

        if clusters is not None:
            for cl in clusters:
                doc_in_cluster = any(
                    chk.startswith(doc.document_id) for chk in cl.chunk_ids
                )
                if not doc_in_cluster:
                    continue
                cluster_map.setdefault(doc.document_id, []).append(cl.cluster_id)
                cl_nid = _node_id(pack.pack_id, "semantic_cluster", cl.cluster_id)
                nodes.append(
                    PackGraphNode(
                        node_id=cl_nid,
                        node_type="semantic_cluster",
                        label=cl.label,
                        properties={
                            "cluster_id": cl.cluster_id,
                            "label": cl.label,
                            "chunk_count": len(cl.chunk_ids),
                            "top_terms": cl.top_terms,
                        },
                    )
                )
                edges.append(
                    PackGraphEdge(
                        edge_id=_edge_id(doc_nid, "DOCUMENT_HAS_CLUSTER", cl_nid),
                        source_id=doc_nid,
                        target_id=cl_nid,
                        relationship="DOCUMENT_HAS_CLUSTER",
                    )
                )
                for chk_id in cl.chunk_ids:
                    chk_nid = _node_id(pack.pack_id, "chunk", chk_id)
                    edges.append(
                        PackGraphEdge(
                            edge_id=_edge_id(cl_nid, "CLUSTER_CONTAINS_CHUNK", chk_nid),
                            source_id=cl_nid,
                            target_id=chk_nid,
                            relationship="CLUSTER_CONTAINS_CHUNK",
                        )
                    )

    for key in pack.missing_for_graphrag:
        key_nid = _node_id(pack.pack_id, "missing_key", key.value)
        nodes.append(
            PackGraphNode(
                node_id=key_nid,
                node_type="missing_key",
                label=f"missing: {key.value}",
                properties={"key": key.value},
            )
        )
        edges.append(
            PackGraphEdge(
                edge_id=_edge_id(pack_nid, "PACK_MISSING_KEY", key_nid),
                source_id=pack_nid,
                target_id=key_nid,
                relationship="PACK_MISSING_KEY",
                properties={"missing_key": key.value},
            )
        )

    logger.info(
        "Built graph for pack '%s': %d nodes, %d edges",
        pack.pack_id,
        len(nodes),
        len(edges),
    )
    return PackGraph(pack_id=pack.pack_id, nodes=nodes, edges=edges)