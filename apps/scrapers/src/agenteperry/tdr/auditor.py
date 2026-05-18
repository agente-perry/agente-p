# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingTypeArgument=false, reportTypedDictNotRequiredAccess=false
"""LangGraph orchestration for AgentePerry TDR Scanner.

State
-----
The graph uses a single ``AuditorState`` TypedDict that accumulates
results through each node. No external state is mutated between nodes.

Checkpointing
-------------
A ``checkpointer`` is required at compile time. For development use
``MemorySaver``; for production use ``PostgresSaver``.

Audit Trace
-----------
Every node writes a dict to ``state["audit_trace"]`` with keys:
  node, status, duration_ms, input_keys, output_keys, error.

Thread Safety
-------------
Each invocation requires a unique ``thread_id`` in the config:
  config = {"configurable": {"thread_id": "<uuid>"}}

pyright: reportMissingTypeStubs=false
pyright: reportUnknownMemberType=false
pyright: reportUnknownParameterType=false
pyright: reportMissingTypeArgument=false
pyright: reportTypedDictNotRequiredAccess=false
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

# Calibrated engine — the LangGraph wrapper delegates flag detection to the
# document_intelligence package (PR#7 + PR#9 + PR#10 patterns, doctrine
# anchors, literal-quote anti-hallucination, LegalSafetyFilter). The legacy
# rule engine `agenteperry.tdr.flags` is intentionally NOT used here because
# it reactivates false positives that the calibrated engine already removed.
from document_intelligence.agents.orchestrator import (
    AgentOrchestrator,
    OrchestratorConfig,
)
from document_intelligence.schemas.analysis import FlagRecord
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agenteperry.tdr.chunking import chunk_pages
from agenteperry.tdr.dossier import generate_dossier
from agenteperry.tdr.downloader import inspect_pdf_text_layer
from agenteperry.tdr.models import TdrChunk, TdrFlag, TdrPage, TdrSeverity
from agenteperry.tdr.parsing import extract_pdf_pages


class AuditorState(TypedDict, total=False):
    """Accumulating state for the TDR Auditor graph.

    Fields are populated progressively as the graph runs.
    """

    document_id: str
    pdf_path: str | None
    tdr_id: str | None
    sector: str | None
    ocid: str | None
    entity_name: str | None
    procedure_code: str | None
    monto: float | None
    question: str | None
    # Enrichment identifiers — required for Neo4j graph enrichment
    supplier_ruc: str | None
    buyer_ruc: str | None
    pages: list[TdrPage]
    total_pages: int
    coverage_pct: float
    chunks: list[TdrChunk]
    flags: list[TdrFlag]
    score: int
    risk_level: str
    dossier: dict[str, Any]
    graph_findings: dict[str, Any] | None  # populated by node_enrich_graph
    audit_trace: list[dict[str, Any]]
    status: str
    error: str | None


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def should_continue_from_check(state: AuditorState) -> str:
    """Route after check_pdf: continue to parse_pdf or stop on error."""
    if state.get("status") == "error":
        return END
    return "parse_pdf"


def should_continue_from_parse(state: AuditorState) -> str:
    """Route after parse_pdf: continue to chunk_text or stop on error."""
    if state.get("status") == "error":
        return END
    return "chunk_text"


def should_continue_from_chunk(state: AuditorState) -> str:
    """Route after chunk_text: continue to detect_flags or stop on error."""
    if state.get("status") == "error":
        return END
    return "detect_flags"


def should_continue_from_flags(state: AuditorState) -> str:
    """Route after detect_flags: continue to generate_dossier or stop on error."""
    if state.get("status") == "error":
        return END
    return "generate_dossier"


def should_continue_from_dossier(state: AuditorState) -> str:
    """Route after generate_dossier: enrich with graph if supplier_ruc known."""
    if state.get("status") == "error":
        return END
    if state.get("supplier_ruc"):
        return "enrich_graph"
    return END


def node_check_pdf(state: AuditorState) -> AuditorState:
    """Verify the PDF has a usable text layer before processing."""
    import time

    t0 = time.monotonic()
    state.setdefault("audit_trace", [])
    state.setdefault("status", "checking_pdf")

    pdf_path = state.get("pdf_path")
    if not pdf_path:
        state["status"] = "error"
        state["error"] = "pdf_path not set"
        return state

    path = Path(pdf_path)
    if not path.exists():
        state["status"] = "error"
        state["error"] = f"PDF not found: {pdf_path}"
        return state

    usability = inspect_pdf_text_layer(path)
    if not usability.get("is_usable"):
        state["status"] = "error"
        state["error"] = (
            f"PDF has no usable text layer: "
            f"status={usability.get('tdr_status')} "
            f"coverage={usability.get('coverage_pct')}%"
        )
        state["audit_trace"].append(
            _trace("check_pdf", "error", t0, error=state["error"])
        )
        return state

    state["total_pages"] = usability.get("total_pages", 0)
    state["coverage_pct"] = usability.get("coverage_pct", 0.0)
    state["status"] = "pdf_checked"
    state["audit_trace"].append(_trace("check_pdf", "ok", t0))
    return state


def node_parse_pdf(state: AuditorState) -> AuditorState:
    """Extract text page-by-page using PyMuPDF."""
    import time

    t0 = time.monotonic()
    state.setdefault("status", "parsing")
    state.setdefault("audit_trace", [])

    pdf_path = state.get("pdf_path")
    if not pdf_path:
        state["status"] = "error"
        state["error"] = "pdf_path not set"
        return state

    path = Path(pdf_path)
    try:
        pages = extract_pdf_pages(path, tdr_id=state.get("tdr_id") or state.get("ocid"))
    except FileNotFoundError:
        state["status"] = "error"
        state["error"] = f"PDF not found: {pdf_path}"
        state["audit_trace"].append(
            _trace("parse_pdf", "error", t0, error=f"PDF not found: {pdf_path}")
        )
        return state

    state["pages"] = pages
    state["status"] = "parsed"
    state["audit_trace"].append(
        _trace("parse_pdf", "ok", t0, extra={"pages": len(pages)})
    )
    return state


def node_chunk_text(state: AuditorState) -> AuditorState:
    """Split pages into overlapping chunks with page provenance."""
    import time

    t0 = time.monotonic()
    state.setdefault("status", "chunking")
    state.setdefault("audit_trace", [])

    pages = state.get("pages", [])
    if not pages:
        state["status"] = "error"
        state["error"] = "No pages to chunk"
        return state

    chunks = chunk_pages(pages)
    state["chunks"] = chunks
    state["status"] = "chunked"
    state["audit_trace"].append(
        _trace("chunk_text", "ok", t0, extra={"chunks": len(chunks)})
    )
    return state


def node_detect_flags(state: AuditorState) -> AuditorState:
    """Delegate flag detection to ``document_intelligence`` (calibrated engine).

    Runs the full calibrated pipeline (parse → chunk → cluster → planner with
    intent expansion → retriever → risk_analysis → evidence_critic →
    civic_synthesizer → legal_safety_filter → score). Each ``FlagRecord``
    returned carries doctrine_anchor, literal-quote-verified evidence, and a
    severity already tuned by PR #10.
    """
    import time

    t0 = time.monotonic()
    state.setdefault("status", "detecting_flags")
    state.setdefault("audit_trace", [])

    pdf_path = state.get("pdf_path")
    if not pdf_path:
        state["status"] = "error"
        state["error"] = "pdf_path not set"
        return state

    pages = state.get("pages", [])
    if not pages:
        state["status"] = "error"
        state["error"] = "No pages for flag detection"
        return state

    try:
        orchestrator = AgentOrchestrator(
            OrchestratorConfig(mode="mock", ocr_mode="off")
        )
        question = (
            state.get("question")
            or "Detecta senales de baja trazabilidad y requisitos restrictivos"
        )
        result = orchestrator.analyze_pdf(str(pdf_path), question)
    except Exception as exc:  # noqa: BLE001 — surface as state error
        state["status"] = "error"
        state["error"] = f"document_intelligence pipeline failed: {exc}"
        state["audit_trace"].append(
            _trace("detect_flags", "error", t0, error=state["error"])
        )
        return state

    tdr_id = state.get("tdr_id") or state.get("ocid")
    flags = [_to_tdr_flag(flag, tdr_id) for flag in result.flags]
    state["flags"] = flags
    state["score"] = result.score
    state["risk_level"] = _risk_level_for_score(result.score)
    state["status"] = "flags_detected"
    state["audit_trace"].append(
        _trace(
            "detect_flags",
            "ok",
            t0,
            extra={
                "flags": len(flags),
                "score": result.score,
                "risk_level": state["risk_level"],
                "graph_rag_activation": result.graph_rag.activation,
                "engine": "document_intelligence",
            },
        )
    )
    return state


_SEVERITY_MAP: dict[str, TdrSeverity] = {
    "low": TdrSeverity.LOW,
    "medium": TdrSeverity.MEDIUM,
    "high": TdrSeverity.HIGH,
}


def _to_tdr_flag(record: FlagRecord, tdr_id: str | None) -> TdrFlag:
    """Adapt ``FlagRecord`` (document_intelligence) into ``TdrFlag`` (scrapers).

    Preserves:
      - flag_code, flag_name, severity (via ``_SEVERITY_MAP``)
      - tdr_evidence.quote → evidence_quote
      - tdr_evidence.page_number → page_number
      - tdr_evidence.chunk_id → chunk_id
      - explanation (legal-safe, already filtered)
      - confidence-based score_contribution (rounded * 100)
    """
    severity = _SEVERITY_MAP.get(record.severity, TdrSeverity.LOW)
    score_contribution = max(0, min(100, int(round(record.confidence * 100))))
    return TdrFlag(
        tdr_id=tdr_id,
        chunk_id=record.tdr_evidence.chunk_id,
        flag_code=record.flag_code,
        flag_name=record.flag_name,
        severity=severity,
        score_contribution=score_contribution,
        evidence_quote=record.tdr_evidence.quote,
        page_number=record.tdr_evidence.page_number,
        explanation=record.explanation,
        detection_method="document_intelligence",
        rule_id=f"di::{record.flag_code}",
    )


def node_generate_dossier(state: AuditorState) -> AuditorState:
    """Build the JSON dossier and compute final risk level."""
    import time

    t0 = time.monotonic()
    state.setdefault("status", "generating_dossier")
    state.setdefault("audit_trace", [])

    pdf_path = state.get("pdf_path")
    if not pdf_path:
        state["status"] = "error"
        state["error"] = "pdf_path not set"
        return state

    if not state.get("pages") or not state.get("chunks"):
        state["status"] = "error"
        state["error"] = "Missing pages or chunks for dossier"
        return state

    dossier = generate_dossier(
        pdf_path=Path(pdf_path),
        sector=state.get("sector") or "desconocido",
        ocid=state.get("ocid") or state.get("document_id") or "sin_ocid",
        entity_name=state.get("entity_name"),
        procedure_code=state.get("procedure_code"),
        monto=state.get("monto"),
        coverage_pct=state.get("coverage_pct", 0.0),
        total_pages=state.get("total_pages", 0),
        pages=state["pages"],
        chunks=state["chunks"],
        flags=state.get("flags", []),
    )

    state["dossier"] = dossier
    state["status"] = "complete"
    state["audit_trace"].append(_trace("generate_dossier", "ok", t0))
    return state


def node_enrich_graph(state: AuditorState) -> AuditorState:
    """Enrich the dossier with Neo4j graph findings (obligatorio).

    Requires a valid Neo4j connection configured via NEO4J_URI, NEO4J_USERNAME,
    NEO4J_PASSWORD environment variables.  Raises ValueError / connection errors
    — does NOT swallow them silently.

    Called only when ``state["supplier_ruc"]`` is set
    (routing guard in ``should_continue_from_dossier``).
    """
    import time

    from agenteperry.graph.neo4j_enrichment import enrich_dossier_with_graph

    t0 = time.monotonic()
    state.setdefault("audit_trace", [])

    supplier_ruc = state.get("supplier_ruc") or ""
    buyer_ruc = state.get("buyer_ruc")

    if not supplier_ruc:
        # Safety guard — should not reach here due to routing, but be explicit.
        state["status"] = "error"
        state["error"] = "node_enrich_graph called without supplier_ruc"
        state["audit_trace"].append(
            _trace("enrich_graph", "error", t0, error=state["error"])
        )
        return state

    dossier = state.get("dossier", {})

    # enrich_dossier_with_graph mutates and returns the dossier.
    # Any exception propagates (obligatorio — no silent fallback).
    enriched = enrich_dossier_with_graph(
        dossier=dossier,
        supplier_ruc=supplier_ruc,
        buyer_ruc=buyer_ruc,
    )

    graph_findings: dict[str, Any] = enriched.get("graph_findings") or {}

    # If enrichment itself returned an error field, surface it as state error.
    if graph_findings.get("error"):
        state["status"] = "error"
        state["error"] = f"Neo4j enrichment failed: {graph_findings['error']}"
        state["audit_trace"].append(
            _trace("enrich_graph", "error", t0, error=state["error"])
        )
        return state

    state["dossier"] = enriched
    state["graph_findings"] = graph_findings
    state["status"] = "complete"
    state["audit_trace"].append(
        _trace(
            "enrich_graph",
            "ok",
            t0,
            extra={
                "supplier_ruc": supplier_ruc,
                "risk_delta": graph_findings.get("risk_delta", 0),
                "signals": len(graph_findings.get("signals") or []),
            },
        )
    )
    return state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trace(
    node: str,
    status: Literal["ok", "error"],
    t0: float,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import time

    duration_ms = (time.monotonic() - t0) * 1000
    trace: dict[str, Any] = {
        "node": node,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if error:
        trace["error"] = error
    if extra:
        trace.update(extra)
    return trace


def _risk_level_for_score(score: int) -> str:
    """Map document_intelligence aggregate score → risk label.

    Aligned with ``ARCHITECTURE_AGENTEPERRY.md`` Fase 3 thresholds:
      - score 0     → SIN_SENALES
      - score < 50  → BAJO
      - 50–74       → MEDIO
      - 75–89       → ALTO (would trigger GraphRAG gate when primary_key present)
      - >= 90       → CRITICO
    """
    if score <= 0:
        return "SIN_SENALES"
    if score < 50:
        return "BAJO"
    if score < 75:
        return "MEDIO"
    if score < 90:
        return "ALTO"
    return "CRITICO"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_auditor_graph(
    checkpointer: Any = None,
) -> Any:
    """Build and compile the AuditorState graph.

    Parameters
    ----------
    checkpointer:
        LangGraph checkpointer. Pass ``MemorySaver()`` for development
        or ``PostgresSaver(...)`` for production.
        If ``None``, checkpointing is disabled.

    Returns
    -------
    Compiled LangGraph ``StateGraph``.
    """
    builder = StateGraph(AuditorState)

    builder.add_node("check_pdf", node_check_pdf)
    builder.add_node("parse_pdf", node_parse_pdf)
    builder.add_node("chunk_text", node_chunk_text)
    builder.add_node("detect_flags", node_detect_flags)
    builder.add_node("generate_dossier", node_generate_dossier)
    builder.add_node("enrich_graph", node_enrich_graph)

    builder.add_edge(START, "check_pdf")
    builder.add_conditional_edges("check_pdf", should_continue_from_check)
    builder.add_conditional_edges("parse_pdf", should_continue_from_parse)
    builder.add_conditional_edges("chunk_text", should_continue_from_chunk)
    builder.add_conditional_edges("detect_flags", should_continue_from_flags)
    builder.add_conditional_edges("generate_dossier", should_continue_from_dossier)
    builder.add_edge("enrich_graph", END)

    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Convenience run function
# ---------------------------------------------------------------------------


def run_auditor(
    pdf_path: str,
    *,
    tdr_id: str | None = None,
    sector: str | None = None,
    ocid: str | None = None,
    entity_name: str | None = None,
    procedure_code: str | None = None,
    monto: float | None = None,
    supplier_ruc: str | None = None,
    buyer_ruc: str | None = None,
    checkpointer: Any = None,
    thread_id: str | None = None,
) -> dict[str, Any]:
    """Run the full TDR Auditor pipeline synchronously.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file on disk.
    tdr_id:
        Optional TDR identifier (used as ``tdr_id`` in page/chunk records).
    sector:
        Sector label for the dossier (e.g. ``"salud"``).
    ocid:
        OCID of the contracting process.
    entity_name:
        Name of the contracting entity.
    procedure_code:
        Internal procedure reference code.
    monto:
        Estimated contract amount in soles.
    supplier_ruc:
        RUC of the winning supplier (11 digits).  When provided, the
        ``enrich_graph`` node is activated and Neo4j enrichment runs
        (obligatorio — connection errors propagate, not swallowed).
    buyer_ruc:
        RUC of the contracting entity.  Used in conflict-of-interest path
        detection alongside ``supplier_ruc``.
    checkpointer:
        LangGraph checkpointer. If ``None`` a new ``MemorySaver`` is used.
    thread_id:
        Unique thread identifier for checkpointing.
        If ``None`` a UUID is generated.

    Returns
    -------
    Final state dict containing all accumulated fields including
    the generated ``dossier``, ``graph_findings``, and ``audit_trace``.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = build_auditor_graph(checkpointer=checkpointer)

    config: dict[str, Any] = {
        "configurable": {
            "thread_id": thread_id or str(uuid.uuid4()),
        }
    }

    initial_state: AuditorState = {
        "document_id": tdr_id or Path(pdf_path).stem,
        "pdf_path": pdf_path,
        "tdr_id": tdr_id,
        "sector": sector,
        "ocid": ocid,
        "entity_name": entity_name,
        "procedure_code": procedure_code,
        "monto": monto,
        "supplier_ruc": supplier_ruc,
        "buyer_ruc": buyer_ruc,
        "pages": [],
        "chunks": [],
        "flags": [],
        "score": 0,
        "risk_level": "SIN_SENALES",
        "graph_findings": None,
        "audit_trace": [],
        "status": "initialized",
    }

    result = graph.invoke(initial_state, config)
    return result
