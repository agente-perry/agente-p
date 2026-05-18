"""RetrieverAgent — execute a RetrievalPlan against the TDRIndex.

The agent does not transform or rerank hits; it merely runs each ``FlagQuery``
through ``TDRIndex.query`` with the plan's cluster filter applied, and wraps
the results in serializable ``RetrievalResult`` records.
"""

from __future__ import annotations

from dataclasses import dataclass

from document_intelligence.retrieval import RetrievalHit, TDRIndex
from document_intelligence.schemas.plan import (
    FlagQuery,
    RetrievalHitRecord,
    RetrievalPlan,
    RetrievalResult,
)


@dataclass(frozen=True)
class RetrieverConfig:
    top_k_per_query: int = 5


class RetrieverAgent:
    """Run a ``RetrievalPlan`` and return one ``RetrievalResult`` per query."""

    def __init__(self, *, tdr_index: TDRIndex, config: RetrieverConfig | None = None) -> None:
        self._tdr = tdr_index
        self._config = config or RetrieverConfig()

    def run(self, plan: RetrievalPlan) -> list[RetrievalResult]:
        results: list[RetrievalResult] = []
        for query in plan.queries:
            hits = self._tdr.query(
                query.query_text,
                top_k=self._config.top_k_per_query,
                cluster_filter=query.target_clusters or None,
            )
            results.append(_make_result(query, hits))
        return results


def _make_result(query: FlagQuery, hits: list[RetrievalHit]) -> RetrievalResult:
    return RetrievalResult(
        flag_code=query.flag_code,
        query_text=query.query_text,
        target_clusters=list(query.target_clusters),
        doctrine_anchor_id=query.doctrine_anchor_id,
        hits=[
            RetrievalHitRecord(
                chunk_id=hit.chunk_id,
                page_start=hit.page_start,
                page_end=hit.page_end,
                text_excerpt=hit.text_excerpt,
                score=hit.score,
                vector_score=hit.vector_score,
                bm25_score=hit.bm25_score,
                cluster_hint=hit.cluster_hint,
            )
            for hit in hits
        ],
    )
