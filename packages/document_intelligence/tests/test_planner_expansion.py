"""PlannerAgent expansion behaviour (PR #8).

Verifies that a general user question is expanded via intent_map even when the
doctrine stub returns no flag-coded hits, and that the audit trail records the
expansion sources for traceability.
"""

from __future__ import annotations

from document_intelligence.agents import ClusterBuilderAgent, DocumentMapperAgent, PlannerAgent
from document_intelligence.agents.planner import PlannerConfig
from document_intelligence.chunking import chunk_document
from document_intelligence.doctrine import DoctrineIndex, load_doctrine
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.schemas.document import DocumentPage, DocumentRef


def _pipeline_setup(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> tuple[str, object, list[object]]:
    ref, pages = sample_pages
    chunks = chunk_document(ref, pages, max_chars=300, overlap_chars=40)
    tdr_map = DocumentMapperAgent()(ref.document_id, pages)
    _labelled, clusters = ClusterBuilderAgent()(chunks)
    return ref.document_id, tdr_map, clusters


def test_planner_expands_via_risk_scan_intent(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    doc_id, tdr_map, clusters = _pipeline_setup(sample_pages)
    doctrine = load_doctrine(embedder=FakeEmbedder(dim=128))
    planner = PlannerAgent(doctrine_index=doctrine)
    plan = planner.plan(
        document_id=doc_id,
        question="Detecta señales de baja trazabilidad y requisitos restrictivos",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    assert "intent::risk_scan" in plan.audit.expansion_sources
    assert "risk_scan" in plan.audit.intent_matches
    # Several distinct flag codes must end up in queries because risk_scan
    # widens the candidate set beyond what the doctrine stub returns.
    flag_codes = {q.flag_code for q in plan.queries}
    assert len(flag_codes) >= 4


def test_planner_falls_back_to_all_flags_when_nothing_matches(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    doc_id, tdr_map, clusters = _pipeline_setup(sample_pages)
    empty_doctrine = DoctrineIndex.from_chunks([], embedder=FakeEmbedder(dim=128))
    planner = PlannerAgent(doctrine_index=empty_doctrine)
    plan = planner.plan(
        document_id=doc_id,
        question="Cual es la capital del Peru?",  # no intent triggers
        tdr_map=tdr_map,
        clusters=clusters,
    )
    assert "fallback::all_flags" in plan.audit.expansion_sources
    flag_codes = {q.flag_code for q in plan.queries}
    # Every known flag with templates should be present.
    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in flag_codes
    assert "SUBJECTIVE_EVALUATION_CRITERIA" in flag_codes


def test_planner_fallback_can_be_disabled(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    doc_id, tdr_map, clusters = _pipeline_setup(sample_pages)
    empty_doctrine = DoctrineIndex.from_chunks([], embedder=FakeEmbedder(dim=128))
    planner = PlannerAgent(
        doctrine_index=empty_doctrine,
        config=PlannerConfig(
            enable_intent_expansion=False,
            fallback_to_all_flags_when_empty=False,
        ),
    )
    plan = planner.plan(
        document_id=doc_id,
        question="Detecta señales de baja trazabilidad",  # intent would trigger but disabled
        tdr_map=tdr_map,
        clusters=clusters,
    )
    assert plan.queries == []
    assert plan.audit.expansion_sources == []


def test_planner_queries_align_with_known_patterns(
    sample_pages: tuple[DocumentRef, list[DocumentPage]],
) -> None:
    """Every emitted query must reference a known flag with retrieval templates."""
    from document_intelligence.agents._canonical import load_planner_queries

    doc_id, tdr_map, clusters = _pipeline_setup(sample_pages)
    planner = PlannerAgent(doctrine_index=load_doctrine(embedder=FakeEmbedder(dim=128)))
    plan = planner.plan(
        document_id=doc_id,
        question="Detecta señales de baja trazabilidad y requisitos restrictivos",
        tdr_map=tdr_map,
        clusters=clusters,
    )
    templates = load_planner_queries()
    for query in plan.queries:
        assert query.flag_code in templates, f"flag {query.flag_code} has no templates"
        assert query.query_text in templates[query.flag_code]
