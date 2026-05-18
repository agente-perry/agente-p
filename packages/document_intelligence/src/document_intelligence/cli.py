"""Document Intelligence CLI.

Available commands:

    python -m document_intelligence inspect-pdf <path>
    python -m document_intelligence chunk-pdf <path> [--max-chars N --overlap N --limit N]
    python -m document_intelligence build-index <path> [--top-k N --query TEXT --persist]
    python -m document_intelligence build-pack <dir> [--out DIR] [--ocr off|auto] [--max-docs N] [--pretty]
    python -m document_intelligence analyze-pack <dir> -q QUESTION [--mode mock|local-embed|llm] [--pretty] [--output-json FILE]
    python -m document_intelligence doctrine-info [--manifest <path>]
    python -m document_intelligence analyze <path> --question TEXT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from document_intelligence import __version__
from document_intelligence.agents.orchestrator import AgentOrchestrator, OrchestratorConfig
from document_intelligence.chunking import chunk_document
from document_intelligence.doctrine import DoctrineLoadError, load_doctrine
from document_intelligence.document_pack import build_pack as _build_pack_fn
from document_intelligence.document_pack.orchestrator import (
    PackOrchestrator,
    PackOrchestratorConfig,
)
from document_intelligence.embeddings import get_embedder
from document_intelligence.parsing import PDFParseError, parse_pdf
from document_intelligence.retrieval import TDRIndex
from document_intelligence.safety.legal_filter import BannedTermFoundError


def _echo_json(payload: object) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="document-intelligence")
def main() -> None:
    """Document Intelligence Core — provisional smoke CLI (T17 supersedes this)."""


@main.command("inspect-pdf")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--ocr",
    type=click.Choice(["off", "auto", "force"], case_sensitive=False),
    default="off",
    show_default=True,
    help="OCR mode: off (skip), auto (only low-text pages), force (every page).",
)
def inspect_pdf(pdf_path: Path, ocr: str) -> None:
    """Parse a PDF and emit per-page + parse-summary metadata."""
    from document_intelligence.parsing import get_default_ocr_adapter
    from document_intelligence.parsing.pdf_parser import parse_pdf_with_summary

    adapter = get_default_ocr_adapter() if ocr != "off" else None
    try:
        ref, pages, summary = parse_pdf_with_summary(
            pdf_path, ocr_mode=cast(Any, ocr), ocr_adapter=adapter
        )
    except PDFParseError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    payload = {
        "document_id": ref.document_id,
        "source_file": ref.source_file,
        "file_size": ref.file_size,
        "pages_total": len(pages),
        "page_count": len(pages),
        **summary.to_dict(),
        "pages": [
            {
                "page_number": p.page_number,
                "char_count": p.char_count,
                "needs_ocr": p.needs_ocr,
                "ocr_applied": p.ocr_applied,
                "ocr_error": p.ocr_error,
            }
            for p in pages
        ],
    }
    _echo_json(payload)


@main.command("chunk-pdf")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--max-chars", type=int, default=1200, show_default=True)
@click.option("--overlap", type=int, default=160, show_default=True)
@click.option("--limit", type=int, default=5, show_default=True, help="How many chunks to preview.")
def chunk_pdf(pdf_path: Path, max_chars: int, overlap: int, limit: int) -> None:
    """Parse, then split into chunks and preview the first N."""
    try:
        ref, pages = parse_pdf(pdf_path)
    except PDFParseError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    chunks = chunk_document(ref, pages, max_chars=max_chars, overlap_chars=overlap)
    payload = {
        "document_id": ref.document_id,
        "chunk_count": len(chunks),
        "preview": [
            {
                "chunk_id": c.chunk_id,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "char_start": c.char_start,
                "char_end": c.char_end,
                "section_hint": c.section_hint,
                "text_preview": c.text[:200] + ("..." if len(c.text) > 200 else ""),
            }
            for c in chunks[: max(limit, 0)]
        ],
    }
    _echo_json(payload)


@main.command("build-index")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--top-k", type=int, default=5, show_default=True)
@click.option("--query", type=str, default=None, help="Optional probe query; runs after build.")
@click.option("--persist", is_flag=True, default=False, help="Save the index to the local cache.")
def build_index(pdf_path: Path, top_k: int, query: str | None, persist: bool) -> None:
    """Build a hybrid (FAISS HNSW + BM25 + RRF) index and optionally probe + persist."""
    try:
        ref, pages = parse_pdf(pdf_path)
    except PDFParseError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    chunks = chunk_document(ref, pages)
    embedder = get_embedder("mock")
    index = TDRIndex.build(document_id=ref.document_id, chunks=chunks, embedder=embedder)

    payload: dict[str, object] = {
        "document_id": ref.document_id,
        "embedder": embedder.model_id,
        "chunks_indexed": index.size,
        "embedding_dim": embedder.dim,
    }
    if persist:
        path = index.save()
        payload["persisted_to"] = str(path)
    if query:
        hits = index.query(query, top_k=top_k)
        payload["query"] = query
        payload["hits"] = [
            {
                "chunk_id": h.chunk_id,
                "page_start": h.page_start,
                "page_end": h.page_end,
                "score": round(h.score, 4),
                "vector_score": round(h.vector_score, 4),
                "bm25_score": round(h.bm25_score, 4),
                "cluster_hint": h.cluster_hint,
                "text_excerpt": h.text_excerpt,
            }
            for h in hits
        ]
    _echo_json(payload)


@main.command("build-pack")
@click.argument("pdf_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--out",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory for artefacts. Defaults to pdf_dir/_index.",
)
@click.option(
    "--ocr",
    type=click.Choice(["off", "auto"], case_sensitive=False),
    default="off",
    show_default=True,
    help="OCR mode for scanned pages (off = skip; auto = only low-text pages).",
)
@click.option("--max-docs", type=int, default=None, show_default=True, help="Max PDFs to process.")
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON artefacts.")
def build_pack(pdf_dir: Path, output_dir: Path | None, ocr: str, max_docs: int | None, pretty: bool) -> None:
    """Scan a directory of PDFs, build a ProcessDocumentPack and write all artefacts."""
    out = output_dir or (pdf_dir / "_index")
    try:
        pack = _build_pack_fn(
            pdf_dir,
            out,
            ocr_mode=cast(Any, ocr),
            max_docs=max_docs,
            pretty=pretty,
        )
    except Exception as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    click.echo(f"Pack '{pack.pack_id}' written to {out}")


@main.command("analyze-pack")
@click.argument("pdf_dir", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--question",
    "-q",
    type=str,
    required=True,
    help="Question guiding the analysis.",
)
@click.option(
    "--out",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Output directory for artefacts. Defaults to pdf_dir/_index.",
)
@click.option(
    "--mode",
    type=click.Choice(["mock", "local-embed", "llm"], case_sensitive=False),
    default="mock",
    show_default=True,
    help="Embedder mode for the agent pipeline.",
)
@click.option(
    "--ocr",
    type=click.Choice(["off", "auto"], case_sensitive=False),
    default="off",
    show_default=True,
    help="OCR mode for scanned pages.",
)
@click.option("--max-docs", type=int, default=None, show_default=True, help="Max PDFs to analyze.")
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON output.")
@click.option("--output-json", "output_json", type=click.Path(dir_okay=False, path_type=Path), default=None, help="Write full result as JSON.")
def analyze_pack(
    pdf_dir: Path,
    question: str,
    output_dir: Path | None,
    mode: str,
    ocr: str,
    max_docs: int | None,
    pretty: bool,
    output_json: Path | None,
) -> None:
    """Analyze all usable documents in a folder using the full agent pipeline.

    Runs AgentOrchestrator on each document with usable text and returns
    per-document results enriched with pack-level metadata (pack_id, mode,
    document_type, missing_for_graphrag).

    Examples::

        python -m document_intelligence analyze-pack data/PDF-Base \\
            --question "Detecta senales de baja trazabilidad"

        python -m document_intelligence analyze-pack data/PDF-Base \\
            --question "Evalua consistencia en requisitos" \\
            --mode local-embed \\
            --pretty \\
            --out data/PDF-Base/_index
    """
    try:
        orch_config = OrchestratorConfig(mode=cast(Any, mode), ocr_mode=cast(Any, ocr))
        pack_orch = PackOrchestrator(
            config=PackOrchestratorConfig(
                orchestrator_config=orch_config,
                ocr_mode=cast(Any, ocr),
                max_docs=max_docs,
                pretty=pretty,
            )
        )
        result = pack_orch.analyze(pdf_dir, question, output_dir=output_dir)
    except Exception as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    payload = result.to_dict()
    indent = 2 if pretty else None
    json_text = json.dumps(payload, ensure_ascii=False, indent=indent)

    if output_json:
        output_json.write_text(json_text, encoding="utf-8")
        click.echo(f"Results written to {output_json}")
    else:
        click.echo(json_text)


@main.command("doctrine-info")
@click.option(
    "--manifest",
    "manifest_path",
    type=click.Path(exists=False, dir_okay=False, path_type=Path),
    default=None,
    help="Path to a doctrine artifact manifest. Falls back to the stub when omitted or missing.",
)
@click.option("--probe", type=str, default=None, help="Optional probe query against the doctrine.")
def doctrine_info(manifest_path: Path | None, probe: str | None) -> None:
    """Load the doctrinal corpus (artifact or stub) and emit summary metadata."""
    try:
        index = load_doctrine(manifest_path=manifest_path)
    except DoctrineLoadError as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)
    payload: dict[str, object] = {
        "source": "artifact" if manifest_path and manifest_path.exists() else "stub",
        "entries": index.size,
        "embedder": index.embedder_model,
    }
    if probe:
        hits = index.query(probe, top_k=3)
        payload["probe"] = probe
        payload["hits"] = [
            {
                "chunk_id": h.chunk_id,
                "source": h.source,
                "flag_code": h.flag_code,
                "score": round(h.score, 4),
                "quote": h.quote[:200] + ("..." if len(h.quote) > 200 else ""),
            }
            for h in hits
        ]
    _echo_json(payload)


@main.command("analyze")
@click.argument("pdf_path", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--question", type=str, required=True, help="Question to guide the analysis.")
@click.option(
    "--mode",
    type=click.Choice(["mock", "local-embed", "llm"], case_sensitive=False),
    default="mock",
    show_default=True,
    help="Execution mode: mock deterministic, local-embed, or llm.",
)
@click.option("--output", type=click.Path(dir_okay=False, path_type=Path), default=None)
@click.option("--pretty", is_flag=True, default=False, help="Pretty-print JSON to stdout.")
@click.option("--max-retries", type=int, default=1, show_default=True)
@click.option(
    "--ocr",
    type=click.Choice(["off", "auto", "force"], case_sensitive=False),
    default="off",
    show_default=True,
    help="OCR mode for scanned PDFs.",
)
@click.option(
    "--debug-retrieval",
    is_flag=True,
    default=False,
    help="Embed planner/retriever/critic diagnostics into the output JSON.",
)
def analyze(
    pdf_path: Path,
    question: str,
    mode: str,
    output: Path | None,
    pretty: bool,
    max_retries: int,
    ocr: str,
    debug_retrieval: bool,
) -> None:
    """Run the full analysis pipeline on a PDF and emit a legal-safe JSON report."""
    config = OrchestratorConfig(
        mode=cast(Any, mode),
        max_retries=max_retries,
        ocr_mode=cast(Any, ocr),
    )
    orchestrator = AgentOrchestrator(config=config)
    try:
        result = orchestrator.analyze_pdf(str(pdf_path), question)
    except (PDFParseError, BannedTermFoundError) as exc:
        click.echo(f"error: {exc}", err=True)
        sys.exit(2)

    payload = result.model_dump(mode="json")
    if orchestrator.last_state and orchestrator.last_state.parse_summary is not None:
        payload["parse_summary"] = orchestrator.last_state.parse_summary.to_dict()

    if debug_retrieval and orchestrator.last_state is not None:
        payload["debug_retrieval"] = _build_debug_retrieval(orchestrator.last_state, question)

    indent = 2 if pretty else None
    json_text = json.dumps(payload, ensure_ascii=False, indent=indent)

    if output:
        output.write_text(json_text, encoding="utf-8")
        click.echo(f"Saved analysis to {output}")
    else:
        click.echo(json_text)


def _build_debug_retrieval(state: Any, question: str) -> dict[str, Any]:
    """Compose a JSON-serialisable diagnostic blob for ``--debug-retrieval``."""
    plan = state.plan
    queries = (
        [
            {
                "flag_code": q.flag_code,
                "query_text": q.query_text,
                "target_clusters": list(q.target_clusters),
                "doctrine_anchor_id": q.doctrine_anchor_id,
            }
            for q in plan.queries
        ]
        if plan is not None
        else []
    )
    hits: list[dict[str, Any]] = []
    for result in state.retrieval_results:
        for hit in result.hits:
            hits.append(
                {
                    "query": result.query_text,
                    "flag_code": result.flag_code,
                    "chunk_id": hit.chunk_id,
                    "page_start": hit.page_start,
                    "page_end": hit.page_end,
                    "score": round(hit.score, 4),
                    "vector_score": round(hit.vector_score, 4),
                    "bm25_score": round(hit.bm25_score, 4),
                    "cluster_hint": hit.cluster_hint,
                    "excerpt": hit.text_excerpt[:300],
                }
            )
    candidate_codes: list[str] = [c.flag_code for c in state.candidates]
    audit = plan.audit if plan is not None else None
    return {
        "question": question,
        "planner": {
            "doctrine_consulted_first": audit.doctrine_consulted_first if audit else None,
            "doctrine_hits_count": audit.doctrine_hits_count if audit else 0,
            "candidate_flags": list(audit.candidate_flags) if audit else [],
            "expansion_sources": list(audit.expansion_sources) if audit else [],
            "intent_matches": list(audit.intent_matches) if audit else [],
        },
        "clusters_selected": list(plan.clusters_to_query) if plan else [],
        "queries_generated": queries,
        "retrieval_hits": hits,
        "candidate_patterns_seen": candidate_codes,
        "flags_candidate_count": len(state.candidates),
        "flags_accepted_count": (
            len(state.critique.accepted) if state.critique is not None else 0
        ),
        "flags_rejected_count": (
            len(state.critique.rejected) if state.critique is not None else 0
        ),
        "flags_rejected_reasons": (
            list(state.critique.reject_reasons) if state.critique is not None else []
        ),
        "retry_count": state.retry_count,
    }


if __name__ == "__main__":
    main()
