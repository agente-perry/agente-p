"""ClusterBuilderAgent: writes ``metadata['cluster_label']`` before any index build."""

from __future__ import annotations

from document_intelligence.agents import ClusterBuilderAgent, build_clusters
from document_intelligence.chunking import chunk_document
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.retrieval import TDRIndex
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def test_cluster_builder_assigns_labels(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    labelled, clusters = build_clusters(chunks)
    assert len(labelled) == len(chunks)
    assert all("cluster_label" in c.metadata for c in labelled)
    labels = {c.label for c in clusters}
    assert "Entregables" in labels or "Experiencia del postor" in labels
    chunk_ids_in_clusters = {cid for cluster in clusters for cid in cluster.chunk_ids}
    assert chunk_ids_in_clusters == {c.chunk_id for c in labelled}


def test_cluster_builder_falls_back_to_otros() -> None:
    from document_intelligence.schemas.chunk import DocumentChunk

    chunk = DocumentChunk(
        chunk_id="d::00000",
        document_id="d",
        source_file="/x.pdf",
        chunk_index=0,
        page_start=1,
        page_end=1,
        text="texto sin ninguna palabra clave del catalogo aqui dentro",
        char_start=0,
        char_end=60,
        section_hint=None,
    )
    labelled, clusters = build_clusters([chunk])
    assert labelled[0].metadata["cluster_label"] == "Otros"
    assert clusters[0].label == "Otros"


def test_cluster_filter_feeds_tdr_index(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    """The labels written by the agent must drive TDRIndex.cluster_filter."""
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    labelled, _clusters = build_clusters(chunks)

    index = TDRIndex.build(
        document_id=ref.document_id,
        chunks=labelled,
        embedder=FakeEmbedder(dim=128),
    )
    # Pick the label that actually exists in this corpus.
    available = {c.metadata["cluster_label"] for c in labelled}
    target = next(
        (label for label in ("Entregables", "Experiencia del postor", "Criterios de evaluación") if label in available),
        next(iter(available)),
    )
    hits = index.query("informe formato A3 impreso", top_k=5, cluster_filter=[target])
    assert all(hit.cluster_hint == target for hit in hits)


def test_cluster_builder_callable(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    agent = ClusterBuilderAgent()
    labelled, clusters = agent(chunks)
    assert labelled
    assert clusters
