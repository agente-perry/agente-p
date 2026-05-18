"""PlannerAgent: doctrine-first ordering and cluster routing."""

from __future__ import annotations

from typing import Any

import pytest

from document_intelligence.agents import (
    ClusterBuilderAgent,
    DocumentMapperAgent,
    PlannerAgent,
)
from document_intelligence.chunking import chunk_document
from document_intelligence.doctrine import load_doctrine
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def _setup(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> tuple[Any, Any, Any]:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    mapper = DocumentMapperAgent()
    tdr_map = mapper(ref.document_id, pages)
    _labelled, clusters = ClusterBuilderAgent()(chunks)
    return ref, tdr_map, clusters


def test_planner_consults_doctrine_before_returning(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    ref, tdr_map, clusters = _setup(sample_pages)
    doctrine = load_doctrine(embedder=FakeEmbedder(dim=128))
    planner = PlannerAgent(doctrine_index=doctrine)
    with caplog.at_level("INFO", logger="document_intelligence.planner"):
        plan = planner.plan(
            document_id=ref.document_id,
            question="Detecta senales de baja trazabilidad y entregables fisicos",
            tdr_map=tdr_map,
            clusters=clusters,
        )
    assert plan.audit.doctrine_consulted_first is True
    assert plan.audit.doctrine_hits_count > 0
    assert any("doctrine_consulted_first" in rec.message for rec in caplog.records)


def test_planner_emits_queries_for_doctrine_flag_candidates(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, tdr_map, clusters = _setup(sample_pages)
    doctrine = load_doctrine(embedder=FakeEmbedder(dim=128))
    planner = PlannerAgent(doctrine_index=doctrine)
    plan = planner.plan(
        document_id=ref.document_id,
        question="experiencia minima sobre especificada del postor",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    flag_codes = {q.flag_code for q in plan.queries}
    assert plan.queries, "planner must emit at least one query when doctrine returns hits"
    assert flag_codes.issubset(set(plan.audit.candidate_flags))


def test_planner_target_clusters_are_filtered_to_available(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    ref, tdr_map, clusters = _setup(sample_pages)
    available = {c.label for c in clusters}
    doctrine = load_doctrine(embedder=FakeEmbedder(dim=128))
    plan = PlannerAgent(doctrine_index=doctrine).plan(
        document_id=ref.document_id,
        question="evaluacion subjetiva criterios del comite",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    for query in plan.queries:
        for label in query.target_clusters:
            assert label in available


def test_planner_with_empty_doctrine_and_no_fallback_produces_empty_plan(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    """With intent expansion AND fallback disabled, empty doctrine → empty plan."""
    from document_intelligence.agents.planner import PlannerConfig
    from document_intelligence.doctrine import DoctrineIndex

    ref, tdr_map, clusters = _setup(sample_pages)
    empty = DoctrineIndex.from_chunks([], embedder=FakeEmbedder(dim=128))
    plan = PlannerAgent(
        doctrine_index=empty,
        config=PlannerConfig(
            enable_intent_expansion=False,
            fallback_to_all_flags_when_empty=False,
        ),
    ).plan(
        document_id=ref.document_id,
        question="cualquier cosa",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    assert plan.queries == []
    assert plan.audit.candidate_flags == []
    assert plan.audit.doctrine_consulted_first is True
