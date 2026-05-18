"""AgentOrchestrator — coordinates the full PDF → analysis pipeline end-to-end.

Flow
====

parse_pdf
→ chunk_document
→ DocumentMapperAgent
→ ClusterBuilderAgent
→ TDRIndex.build_or_load
→ load_doctrine (or reuse cached)
→ PlannerAgent.plan
→ RetrieverAgent.run
→ RiskAnalysisAgent.analyze
→ EvidenceCriticAgent.critique(..., tdr_chunks)
→ retry max 1 if needs_replan (double retriever top_k)
→ CivicSynthesizerAgent.synthesize
→ LegalSafetyFilter.check_analysis
→ AnalysisResult

The orchestrator is intentionally sequential (no LangGraph dependency).
It maintains a lightweight typed state (``OrchestratorState``) so each
step’s output is inspectable during debugging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from document_intelligence.agents.civic_synthesizer import CivicSynthesizerAgent
from document_intelligence.agents.cluster_builder import ClusterBuilderAgent
from document_intelligence.agents.document_mapper import DocumentMapperAgent
from document_intelligence.agents.evidence_critic import (
    CriticConfig,
    CriticCritique,
    EvidenceCriticAgent,
)
from document_intelligence.agents.planner import PlannerAgent
from document_intelligence.agents.retriever_agent import RetrieverAgent, RetrieverConfig
from document_intelligence.agents.risk_analysis import RiskAnalysisAgent
from document_intelligence.agents.score import ScoringContext, apply_score
from document_intelligence.chunking import chunk_document
from document_intelligence.doctrine import load_doctrine
from document_intelligence.doctrine.index import DoctrineIndex
from document_intelligence.embeddings import get_embedder
from document_intelligence.embeddings.base import BaseEmbedder
from document_intelligence.parsing import (
    BaseOCRAdapter,
    OCRMode,
    ParseSummary,
    get_default_ocr_adapter,
)
from document_intelligence.parsing.pdf_parser import parse_pdf_with_summary
from document_intelligence.retrieval import TDRIndex
from document_intelligence.safety.legal_filter import FilterMode, LegalSafetyFilter
from document_intelligence.schemas.analysis import AnalysisResult, FlagCandidate
from document_intelligence.schemas.chunk import DocumentChunk
from document_intelligence.schemas.document import DocumentPage, DocumentRef
from document_intelligence.schemas.plan import RetrievalPlan, RetrievalResult

_DEFAULT_CACHE = Path.home() / ".cache" / "document_intelligence"
_PDF_CACHE = _DEFAULT_CACHE / "tdr_index"

_EmbedderMode = Literal["mock", "local-embed", "llm"]


@dataclass
class OrchestratorConfig:
    """Configuration knobs for the orchestrator."""

    mode: _EmbedderMode = "mock"
    embedder_dim: int = 384
    max_chars_per_chunk: int = 1200
    overlap_chars: int = 160
    retriever_top_k: int = 5
    planner_doctrine_top_k: int = 10
    max_retries: int = 1
    require_dual_evidence: bool = True
    safety_mode: FilterMode = "reject"
    ocr_mode: OCRMode = "off"
    low_text_threshold: int = 50
    min_confidence_for_critic: float = 0.20


@dataclass
class OrchestratorState:
    """Mutable state bag carried through the pipeline for observability."""

    document_id: str = ""
    pdf_path: str = ""
    question: str = ""
    parse_summary: ParseSummary | None = None
    pages: list[DocumentPage] = field(default_factory=lambda: [])
    chunks: list[DocumentChunk] = field(default_factory=lambda: [])
    tdr_map: Any = None
    clusters: Any = None
    plan: RetrievalPlan | None = None
    retrieval_results: list[RetrievalResult] = field(default_factory=lambda: [])
    candidates: list[FlagCandidate] = field(default_factory=lambda: [])
    critique: CriticCritique | None = None
    accepted_flags: Any = None
    retry_count: int = 0
    logs: list[dict[str, Any]] = field(default_factory=lambda: [])

    def log(self, stage: str, **kwargs: Any) -> None:
        entry: dict[str, Any] = {"stage": stage}
        entry.update(kwargs)
        self.logs.append(entry)


class AgentOrchestrator:
    """End-to-end document intelligence orchestrator.

    No API keys required in ``mode="mock"`` (default).
    """

    def __init__(
        self,
        config: OrchestratorConfig | None = None,
        *,
        ocr_adapter: BaseOCRAdapter | None = None,
        scoring_context: ScoringContext | None = None,
    ) -> None:
        self._config = config or OrchestratorConfig()
        self._embedder: BaseEmbedder | None = None
        self._safety = LegalSafetyFilter(mode=self._config.safety_mode)
        self._doctrine_index: DoctrineIndex | None = None
        self._ocr_adapter = ocr_adapter
        self._last_state: OrchestratorState | None = None
        self._scoring_context: ScoringContext = scoring_context or ScoringContext()

    def _get_embedder(self) -> BaseEmbedder:
        if self._embedder is None:
            self._embedder = get_embedder(self._config.mode, dim=self._config.embedder_dim)
        return self._embedder

    def _get_doctrine(self) -> DoctrineIndex:
        if self._doctrine_index is None:
            self._doctrine_index = load_doctrine(
                embedder=self._get_embedder(),
            )
        return self._doctrine_index

    def analyze_pdf(
        self,
        pdf_path: str,
        question: str,
    ) -> AnalysisResult:
        """Run the full pipeline and return an ``AnalysisResult``."""
        state = OrchestratorState(pdf_path=str(pdf_path), question=question)

        # ── 1. Parse ──────────────────────────────────────────────────────
        ref, pages = self._parse(state)
        state.document_id = ref.document_id
        state.pages = pages

        # ── 2. Chunk ──────────────────────────────────────────────────────
        state.chunks = self._chunk(ref, pages)
        chunk_texts = {c.chunk_id: c.text for c in state.chunks}

        # ── 3. Map & Cluster ─────────────────────────────────────────────
        mapper = DocumentMapperAgent()
        state.tdr_map = mapper(ref.document_id, pages)
        cluster_builder = ClusterBuilderAgent()
        labelled, clusters = cluster_builder(state.chunks)
        state.chunks = labelled
        state.clusters = clusters

        # ── 4. Index (build or load) ─────────────────────────────────────
        tdr_index = self._build_or_load_index(ref.document_id, labelled)

        # ── 5. Doctrine ──────────────────────────────────────────────────
        doctrine = self._get_doctrine()

        # ── 6. Plan ──────────────────────────────────────────────────────
        planner = PlannerAgent(
            doctrine_index=doctrine,
            config=None,
        )
        state.plan = planner.plan(
            document_id=ref.document_id,
            question=question,
            tdr_map=state.tdr_map,
            clusters=clusters,
        )
        state.log("plan", queries=len(state.plan.queries))

        # ── 7. Retrieve ──────────────────────────────────────────────────
        state.retrieval_results = self._retrieve(tdr_index, state.plan)
        state.log("retrieve", results=len(state.retrieval_results))

        # ── 8. Risk analysis ─────────────────────────────────────────────
        risk_agent = RiskAnalysisAgent(
            doctrine_index=doctrine,
        )
        state.candidates = risk_agent.analyze(state.retrieval_results)
        state.log("risk", candidates=len(state.candidates))

        # ── 9. Evidence critic ───────────────────────────────────────────
        critic = EvidenceCriticAgent(
            config=CriticConfig(
                require_dual_evidence=self._config.require_dual_evidence,
                min_confidence=self._config.min_confidence_for_critic,
            ),
        )
        state.critique = critic.critique(
            state.candidates,
            tdr_chunks=chunk_texts,
        )
        state.log(
            "critic",
            accepted=len(state.critique.accepted),
            rejected=len(state.critique.rejected),
            needs_replan=state.critique.needs_replan,
        )

        # ── 10. Retry loop (max 1) ───────────────────────────────────────
        if state.critique.needs_replan and state.retry_count < self._config.max_retries:
            state.retry_count += 1
            state.log("retry", attempt=state.retry_count)
            # Re-run pipeline with doubled retrieval budget.
            state.retrieval_results = self._retrieve(
                tdr_index, state.plan, top_k_override=self._config.retriever_top_k * 2
            )
            state.candidates = risk_agent.analyze(state.retrieval_results)
            state.critique = critic.critique(
                state.candidates,
                tdr_chunks=chunk_texts,
            )
            state.log(
                "critic_post_retry",
                accepted=len(state.critique.accepted),
                rejected=len(state.critique.rejected),
                needs_replan=state.critique.needs_replan,
            )

        state.accepted_flags = state.critique.accepted if state.critique else []

        # ── 11. Synthesize ───────────────────────────────────────────────
        synthesizer = CivicSynthesizerAgent()
        clusters_inspected = (
            state.plan.clusters_to_query
            if state.plan and state.plan.clusters_to_query
            else []
        )
        result = synthesizer.synthesize(
            document=Path(state.pdf_path).name,
            question=question,
            clusters_inspected=clusters_inspected,
            flags=state.accepted_flags,
        )
        state.log("synthesize", flags=len(result.flags), confidence=result.confidence)

        # ── 12. Safety filter ────────────────────────────────────────────
        result = self._apply_safety(result)
        state.log("safety", passed=True)

        # ── 13. Aggregate score (debug-only, never triggers GraphRAG) ──
        result = apply_score(result, context=self._scoring_context)
        state.log(
            "score",
            score=result.score,
            graph_rag_activation=result.graph_rag.activation,
            blockers=list(result.graph_rag.blockers),
        )
        self._last_state = state

        return result

    # ── Internal helpers ────────────────────────────────────────────────

    def _parse(self, state: OrchestratorState) -> tuple[DocumentRef, list[DocumentPage]]:
        adapter = self._ocr_adapter
        if adapter is None and self._config.ocr_mode != "off":
            adapter = get_default_ocr_adapter()
        ref, pages, summary = parse_pdf_with_summary(
            Path(state.pdf_path),
            ocr_mode=self._config.ocr_mode,
            ocr_adapter=adapter,
            low_text_threshold=self._config.low_text_threshold,
        )
        state.parse_summary = summary
        state.log("parse", pages=len(pages), **summary.to_dict())
        return ref, pages

    def _chunk(
        self,
        ref: DocumentRef,
        pages: list[DocumentPage],
    ) -> list[DocumentChunk]:
        return chunk_document(
            ref,
            pages,
            max_chars=self._config.max_chars_per_chunk,
            overlap_chars=self._config.overlap_chars,
        )

    def _build_or_load_index(
        self,
        document_id: str,
        chunks: list[DocumentChunk],
    ) -> TDRIndex:
        try:
            index = TDRIndex.load(
                document_id=document_id,
                embedder=self._get_embedder(),
                base_dir=_PDF_CACHE,
            )
            return index
        except (FileNotFoundError, ValueError):
            index = TDRIndex.build(
                document_id=document_id,
                chunks=chunks,
                embedder=self._get_embedder(),
            )
            index.save(base_dir=_PDF_CACHE)
            return index

    def _retrieve(
        self,
        tdr_index: TDRIndex,
        plan: RetrievalPlan,
        top_k_override: int | None = None,
    ) -> list[RetrievalResult]:
        top_k = top_k_override if top_k_override is not None else self._config.retriever_top_k
        retriever = RetrieverAgent(
            tdr_index=tdr_index,
            config=RetrieverConfig(top_k_per_query=top_k),
        )
        return retriever.run(plan)

    def _apply_safety(self, result: AnalysisResult) -> AnalysisResult:
        return self._safety.check_analysis(result)

    def export_logs(self, state: OrchestratorState) -> list[dict[str, Any]]:
        """Return structured JSON logs of the last run."""
        return state.logs

    @property
    def last_state(self) -> OrchestratorState | None:
        """Expose the last orchestrator state for CLI/reporting helpers."""
        return self._last_state
