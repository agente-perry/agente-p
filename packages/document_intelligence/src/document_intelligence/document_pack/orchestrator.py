"""PackOrchestrator — run the full agent pipeline on a ProcessDocumentPack.

This orchestrator is used when you have a folder of PDFs (a ProcessDocumentPack)
rather than a single PDF. It runs the AgentOrchestrator on each document that
has usable text, aggregates the results, and returns per-document AnalysisResults
enriched with pack-level metadata (pack_id, mode, document_type).

For investigative packs (bases + winner), all documents are analyzed and the
results reflect the full process context. For preventive packs (bases only,
no winner), the analysis is tagged accordingly.

This orchestrator does NOT activate GraphRAG. It is the source of structured
data that the future PlannerAgent will consult to decide whether GraphRAG
activation is warranted.
"""

# pyright: reportArgumentType=false

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from document_intelligence.agents.orchestrator import AgentOrchestrator, OrchestratorConfig
from document_intelligence.document_pack.mode_strategy import (
    PackAnalysisStrategy,
    resolve_strategy,
)
from document_intelligence.document_pack.pack_builder import build_pack as _build_pack
from document_intelligence.document_pack.schemas import (
    ClassifiedDocument,
    MissingGraphRAGKey,
    PackMode,
    ProcessDocumentPack,
)
from document_intelligence.schemas.analysis import AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class PackAnalysisResult:
    """Result of running the pipeline on an entire document pack."""

    pack_id: str
    pack_mode: PackMode
    strategy_applied: PackAnalysisStrategy
    root_path: str
    total_documents: int
    documents_analyzed: int
    document_results: list[AnalysisResult]
    missing_for_graphrag: list[MissingGraphRAGKey]
    summary_by_type: dict[str, list[AnalysisResult]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1",
            "pack_id": self.pack_id,
            "pack_mode": self.pack_mode.value,
            "strategy_applied": {
                "mode": self.strategy_applied.mode.value,
                **self.strategy_applied.to_config_dict(),
            },
            "root_path": self.root_path,
            "total_documents": self.total_documents,
            "documents_analyzed": self.documents_analyzed,
            "missing_for_graphrag": [k.value for k in self.missing_for_graphrag],
            "summary_by_type": {
                dtype: [r.model_dump(mode="json") for r in results]
                for dtype, results in self.summary_by_type.items()
            },
            "all_results": [r.model_dump(mode="json") for r in self.document_results],
        }


@dataclass
class PackOrchestratorConfig:
    """Configuration for PackOrchestrator."""

    orchestrator_config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    ocr_mode: str = "off"
    max_docs: int | None = None
    pack_id: str | None = None
    pretty: bool = False


class PackOrchestrator:
    """Orchestrate analysis over an entire ProcessDocumentPack.

    Usage::

        orch = PackOrchestrator(config=PackOrchestratorConfig())
        result = orch.analyze("/path/to/PDF-Base", "Detecta senales de baja trazabilidad")
    """

    def __init__(self, config: PackOrchestratorConfig | None = None) -> None:
        self._config = config or PackOrchestratorConfig()

    def analyze(
        self,
        pdf_dir: str | Path,
        question: str,
        output_dir: Path | None = None,
    ) -> PackAnalysisResult:
        """Analyze all usable documents in a folder and return aggregated results.

        If a ``_index/process_document_pack.json`` already exists it will be
        loaded directly instead of rebuilding the pack.

        Parameters
        ----------
        pdf_dir:
            Directory containing PDF files.
        question:
            The question/objective guiding the analysis.
        output_dir:
            Directory where pack artefacts will be written.
            Defaults to ``pdf_dir/_index``.

        Returns
        -------
        PackAnalysisResult
            Aggregated results with per-document AnalysisResults.
        """
        pdf_path = Path(pdf_dir)
        index_dir = output_dir or (pdf_path / "_index")
        pack = self._resolve_pack(pdf_path, index_dir)

        strategy = resolve_strategy(pack.mode)

        logger.info(
            "Starting pack analysis",
            extra={
                "pack_id": pack.pack_id,
                "mode": pack.mode.value,
                "strategy": strategy.risk_weight_profile,
                "total_docs": pack.total_documents,
                "docs_with_text": pack.documents_with_text,
                "docs_needing_ocr": pack.documents_needing_ocr,
            },
        )

        document_results: list[AnalysisResult] = []
        summary_by_type: dict[str, list[AnalysisResult]] = {}
        skipped = 0
        errors = 0

        for doc in pack.documents:
            if not doc.usable_for_analysis:
                logger.info(
                    "Skipping document (not usable)",
                    extra={"pack_id": pack.pack_id, "file": doc.file_name},
                )
                skipped += 1
                continue

            try:
                result = self._analyze_single(doc, question, pack.pack_id, strategy)
                document_results.append(result)
                dtype = doc.document_type.value
                summary_by_type.setdefault(dtype, []).append(result)
                logger.info(
                    "Analyzed document — %d flags",
                    len(result.flags),
                    extra={
                        "pack_id": pack.pack_id,
                        "file": doc.file_name,
                        "document_type": doc.document_type.value,
                        "flag_count": len(result.flags),
                        "confidence": result.confidence,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to analyze document",
                    extra={"pack_id": pack.pack_id, "file": doc.file_name, "error": str(exc)},
                )
                errors += 1
                continue

        analyzed = len(document_results)

        logger.info(
            "Pack analysis complete",
            extra={
                "pack_id": pack.pack_id,
                "total": pack.total_documents,
                "analyzed": analyzed,
                "skipped": skipped,
                "errors": errors,
            },
        )

        return PackAnalysisResult(
            pack_id=pack.pack_id,
            pack_mode=pack.mode,
            strategy_applied=strategy,
            root_path=pack.root_path,
            total_documents=pack.total_documents,
            documents_analyzed=analyzed,
            document_results=document_results,
            missing_for_graphrag=pack.missing_for_graphrag,
            summary_by_type=summary_by_type,
        )

    def _resolve_pack(self, pdf_dir: Path, index_dir: Path) -> ProcessDocumentPack:
        pack_file = index_dir / "process_document_pack.json"
        if pack_file.exists():
            import json

            data = json.loads(pack_file.read_text(encoding="utf-8"))
            return ProcessDocumentPack.model_validate(data)

        logger.info("No existing pack found at %s — building new pack", pack_file)
        return _build_pack(
            pdf_dir,
            index_dir,
            ocr_mode=self._config.ocr_mode,
            max_docs=self._config.max_docs,
            pack_id=self._config.pack_id,
            pretty=self._config.pretty,
        )

    def _analyze_single(
        self,
        doc: ClassifiedDocument,
        question: str,
        pack_id: str,
        strategy: PackAnalysisStrategy,
    ) -> AnalysisResult:
        config = _strategy_to_orchestrator_config(strategy, self._config.orchestrator_config)
        orch = AgentOrchestrator(config=config)
        result = orch.analyze_pdf(doc.file_path, question)
        result.pack_id = pack_id
        result.document_type = doc.document_type.value
        return result


def _strategy_to_orchestrator_config(
    strategy: PackAnalysisStrategy,
    base_config: OrchestratorConfig,
) -> OrchestratorConfig:
    """Derive an OrchestratorConfig from a PackAnalysisStrategy."""
    return OrchestratorConfig(
        mode=base_config.mode,
        embedder_dim=base_config.embedder_dim,
        max_chars_per_chunk=base_config.max_chars_per_chunk,
        overlap_chars=base_config.overlap_chars,
        retriever_top_k=strategy.retriever_top_k,
        planner_doctrine_top_k=strategy.planner_doctrine_top_k,
        max_retries=strategy.max_retries,
        require_dual_evidence=strategy.require_dual_evidence,
        safety_mode=base_config.safety_mode,
        ocr_mode=base_config.ocr_mode,
        low_text_threshold=base_config.low_text_threshold,
        min_confidence_for_critic=strategy.evidence_threshold,
    )