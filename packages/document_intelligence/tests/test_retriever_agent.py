"""RetrieverAgent: runs a RetrievalPlan against a TDRIndex."""

from __future__ import annotations

from document_intelligence.agents import (
    ClusterBuilderAgent,
    DocumentMapperAgent,
    PlannerAgent,
    RetrieverAgent,
)
from document_intelligence.agents.retriever_agent import RetrieverConfig
from document_intelligence.chunking import chunk_document
from document_intelligence.doctrine import load_doctrine
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.retrieval import TDRIndex
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def _pipeline(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> tuple[TDRIndex, RetrieverAgent, object]:
    ref, pages = sample_pages
    embedder = FakeEmbedder(dim=128)

    tdr_map = DocumentMapperAgent()(ref.document_id, pages)
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    labelled, clusters = ClusterBuilderAgent()(chunks)
    index = TDRIndex.build(document_id=ref.document_id, chunks=labelled, embedder=embedder)
    doctrine = load_doctrine(embedder=embedder)
    planner = PlannerAgent(doctrine_index=doctrine)
    plan = planner.plan(
        document_id=ref.document_id,
        question="entregables fisicos impresos sin dataset",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    retriever = RetrieverAgent(tdr_index=index, config=RetrieverConfig(top_k_per_query=3))
    return index, retriever, plan


def test_retriever_returns_one_result_per_query(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    _index, retriever, plan = _pipeline(sample_pages)
    results = retriever.run(plan)
    assert len(results) == len(plan.queries)
    for result, query in zip(results, plan.queries, strict=True):
        assert result.flag_code == query.flag_code
        assert result.query_text == query.query_text


def test_retriever_respects_cluster_filter(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    _index, retriever, plan = _pipeline(sample_pages)
    results = retriever.run(plan)
    for result in results:
        if not result.target_clusters:
            continue
        for hit in result.hits:
            assert hit.cluster_hint in result.target_clusters


def test_retriever_empty_plan_returns_empty_results(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    from document_intelligence.doctrine import DoctrineIndex
    from document_intelligence.schemas.plan import (
        PlannerAudit,
        RetrievalPlan,
    )

    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    labelled, _clusters = ClusterBuilderAgent()(chunks)
    index = TDRIndex.build(
        document_id=ref.document_id, chunks=labelled, embedder=FakeEmbedder(dim=128)
    )
    _ = DoctrineIndex.from_chunks([], embedder=FakeEmbedder(dim=128))
    empty_plan = RetrievalPlan(
        document_id=ref.document_id,
        question="nada",
        clusters_to_query=[],
        queries=[],
        audit=PlannerAudit(
            doctrine_consulted_first=True, doctrine_hits_count=0, candidate_flags=[]
        ),
    )
    retriever = RetrieverAgent(tdr_index=index)
    assert retriever.run(empty_plan) == []
