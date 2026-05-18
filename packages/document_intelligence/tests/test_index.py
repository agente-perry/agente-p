"""TDRIndex: hybrid retrieval, RRF fusion, cluster filter, persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from document_intelligence.chunking import chunk_document
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.retrieval import TDRIndex
from document_intelligence.schemas.chunk import DocumentChunk
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def _build_index(
    pages_fixture: tuple[DocumentRef, list[DocumentPage]],
) -> TDRIndex:
    ref, pages = pages_fixture
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    return TDRIndex.build(
        document_id=ref.document_id,
        chunks=chunks,
        embedder=FakeEmbedder(dim=128),
    )


def test_index_build_and_query(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    index = _build_index(sample_pages)
    assert index.size > 0
    hits = index.query("entregables formato fisico impreso A3", top_k=3)
    assert hits
    assert all(h.page_start >= 1 for h in hits)
    assert hits[0].score >= hits[-1].score


def test_index_empty_returns_no_hits() -> None:
    index = TDRIndex.build(
        document_id="empty",
        chunks=[],
        embedder=FakeEmbedder(dim=64),
    )
    assert index.query("anything", top_k=5) == []


def test_index_top_k_zero(sample_pages: tuple[DocumentRef, list[DocumentPage]]) -> None:
    index = _build_index(sample_pages)
    assert index.query("anything", top_k=0) == []


def test_index_hybrid_fuses_vector_and_bm25(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    index = _build_index(sample_pages)
    hits = index.query("juicio comite tecnico", top_k=3)
    # BM25 should surface the literal-term chunk; both rankers contribute.
    assert hits, "expected at least one hit for a high-lexical-overlap query"
    assert hits[0].bm25_score > 0.0


def test_index_cluster_filter_restricts_results(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    # Tag some chunks with a synthetic cluster label via metadata.
    relabelled: list[DocumentChunk] = []
    for chunk in chunks:
        if chunk.section_hint and "ENTREGABLES" in chunk.section_hint:
            relabelled.append(chunk.model_copy(update={"metadata": {"cluster_label": "Entregables"}}))
        else:
            relabelled.append(chunk)
    index = TDRIndex.build(
        document_id=ref.document_id,
        chunks=relabelled,
        embedder=FakeEmbedder(dim=128),
    )
    hits = index.query("formato A3 impreso", top_k=5, cluster_filter=["Entregables"])
    assert hits, "cluster-filtered query must return at least one hit when a match exists"
    assert all(h.cluster_hint == "Entregables" for h in hits)


def test_index_persist_and_load_roundtrip(
    sample_pages: tuple[DocumentRef, list[DocumentPage]], tmp_path: Path
) -> None:
    embedder = FakeEmbedder(dim=128)
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    original = TDRIndex.build(document_id=ref.document_id, chunks=chunks, embedder=embedder)
    saved = original.save(base_dir=tmp_path)
    assert (saved / "manifest.json").exists()
    assert (saved / "chunks.jsonl").exists()
    assert (saved / "vectors.faiss").exists()

    reloaded = TDRIndex.load(ref.document_id, embedder=embedder, base_dir=tmp_path)
    assert reloaded.size == original.size
    hits = reloaded.query("entregables formato fisico impreso A3", top_k=2)
    assert hits


def test_index_load_rejects_embedder_mismatch(
    sample_pages: tuple[DocumentRef, list[DocumentPage]], tmp_path: Path
) -> None:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    TDRIndex.build(
        document_id=ref.document_id, chunks=chunks, embedder=FakeEmbedder(dim=128)
    ).save(base_dir=tmp_path)
    with pytest.raises(ValueError):
        TDRIndex.load(ref.document_id, embedder=FakeEmbedder(dim=64), base_dir=tmp_path)
