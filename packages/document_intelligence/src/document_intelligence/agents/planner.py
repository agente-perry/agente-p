"""PlannerAgent — doctrine-first retrieval planning.

Order is load-bearing and must be preserved:

    1. consult the DoctrineIndex with the user question
    2. extract candidate flag codes from doctrine hits
    3. for each candidate flag, look up the clusters of interest from
       ``flags/cluster_flag_map.yaml`` and the query templates from
       ``flags/planner_queries.yaml``
    4. only THEN emit a ``RetrievalPlan`` that the RetrieverAgent will run
       against the TDRIndex

The PlannerAudit field records that doctrine was consulted first so callers
(and tests) can verify the invariant without parsing logs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from document_intelligence.agents._canonical import (
    load_cluster_flag_map,
    load_planner_queries,
    match_intents,
)
from document_intelligence.doctrine import DoctrineHit, DoctrineIndex
from document_intelligence.schemas.cluster import DocumentCluster
from document_intelligence.schemas.plan import (
    FlagQuery,
    PlannerAudit,
    RetrievalPlan,
    TDRMap,
)

_LOG = logging.getLogger("document_intelligence.planner")
_DEFAULT_DOCTRINE_TOP_K = 10


@dataclass(frozen=True)
class PlannerConfig:
    doctrine_top_k: int = _DEFAULT_DOCTRINE_TOP_K
    max_queries_per_flag: int = 4
    enable_intent_expansion: bool = True
    fallback_to_all_flags_when_empty: bool = True


class PlannerAgent:
    """Produce a ``RetrievalPlan`` from a user question and the indices."""

    def __init__(
        self,
        *,
        doctrine_index: DoctrineIndex,
        config: PlannerConfig | None = None,
    ) -> None:
        self._doctrine = doctrine_index
        self._config = config or PlannerConfig()

    def plan(
        self,
        *,
        document_id: str,
        question: str,
        tdr_map: TDRMap,
        clusters: list[DocumentCluster],
    ) -> RetrievalPlan:
        # Step 1: consult doctrine BEFORE touching the TDR.
        doctrine_hits = self._doctrine.query(question, top_k=self._config.doctrine_top_k)
        _LOG.info(
            "planner.doctrine_consulted_first",
            extra={"document_id": document_id, "doctrine_hits": len(doctrine_hits)},
        )

        candidate_flags = list(_ordered_candidate_flags(doctrine_hits))
        expansion_sources: list[str] = []
        intent_match_names: list[str] = []
        if candidate_flags:
            expansion_sources.append("doctrine")

        # Step 2: intent-driven expansion. A general question like
        # "Detecta señales..." would otherwise miss flag codes the doctrine
        # stub does not surface. The intent map widens recall deterministically.
        if self._config.enable_intent_expansion:
            for intent in match_intents(question):
                intent_match_names.append(intent.name)
                source = f"intent::{intent.name}"
                if source not in expansion_sources:
                    expansion_sources.append(source)
                for code in intent.expands_to:
                    if code not in candidate_flags:
                        candidate_flags.append(code)

        cluster_flag_map = load_cluster_flag_map()
        planner_queries = load_planner_queries()
        available_clusters = {c.label for c in clusters}

        # Step 3: fallback when nothing surfaced. Better to scan all known
        # flag codes than to emit an empty plan and report "no signals" by
        # accident. Caller can disable via config when stricter recall is wanted.
        if (
            not candidate_flags
            and self._config.fallback_to_all_flags_when_empty
            and planner_queries
        ):
            candidate_flags = list(planner_queries.keys())
            expansion_sources.append("fallback::all_flags")

        queries: list[FlagQuery] = []
        clusters_to_query: list[str] = []
        for flag_code in candidate_flags:
            target_labels = cluster_flag_map.get(flag_code, ())
            templates = planner_queries.get(flag_code, ())[: self._config.max_queries_per_flag]
            if not templates:
                continue
            filtered_clusters = [c for c in target_labels if c in available_clusters]
            anchor_id = next(
                (h.chunk_id for h in doctrine_hits if h.flag_code == flag_code),
                None,
            )
            for template in templates:
                queries.append(
                    FlagQuery(
                        flag_code=flag_code,
                        query_text=template,
                        target_clusters=list(filtered_clusters),
                        doctrine_anchor_id=anchor_id,
                    )
                )
            for label in filtered_clusters:
                if label not in clusters_to_query:
                    clusters_to_query.append(label)

        # Light enrichment from the TDR map: if the map detected entregables/criterios
        # but no doctrine flag mentioned them, surface them anyway as exploratory clusters.
        for section in tdr_map.sections:
            if section.name in available_clusters and section.name not in clusters_to_query:
                clusters_to_query.append(section.name)

        audit = PlannerAudit(
            doctrine_consulted_first=True,
            doctrine_hits_count=len(doctrine_hits),
            candidate_flags=list(candidate_flags),
            notes=(
                "Doctrine queried before TDR. Candidate flags drawn from doctrine "
                "hits then enriched via intent expansion; clusters filtered against "
                "ClusterBuilderAgent output."
            ),
            expansion_sources=expansion_sources,
            intent_matches=intent_match_names,
        )
        return RetrievalPlan(
            document_id=document_id,
            question=question,
            clusters_to_query=clusters_to_query,
            queries=queries,
            audit=audit,
        )


def _ordered_candidate_flags(hits: list[DoctrineHit]) -> tuple[str, ...]:
    seen: list[str] = []
    for hit in hits:
        if hit.flag_code and hit.flag_code not in seen:
            seen.append(hit.flag_code)
    return tuple(seen)
