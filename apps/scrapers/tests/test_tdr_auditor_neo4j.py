# pyright: reportMissingTypeStubs=false, reportMissingImports=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Tests for the Neo4j enrichment node in the LangGraph auditor — SPEC-0012.

All tests mock ``enrich_dossier_with_graph`` so no real Neo4j connection
is required.  The tests verify:

- ``node_enrich_graph`` populates ``state["graph_findings"]`` and ``state["dossier"]``.
- When ``supplier_ruc`` is absent, the node sets state to error (should-not-reach,
  but the guard is tested explicitly).
- When ``enrich_dossier_with_graph`` returns an error field, the node surfaces it.
- ``AuditorState`` accepts the two new fields without breaking existing usage.
- ``should_continue_from_dossier`` routes to ``enrich_graph`` when supplier_ruc is set,
  and to ``END`` when it is absent.
- ``run_auditor`` passes ``supplier_ruc``/``buyer_ruc`` through to the initial state.
- The routing guard means ``enrich_graph`` is only invoked when supplier_ruc is set.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from agenteperry.tdr.auditor import (
    AuditorState,
    node_enrich_graph,
    run_auditor,
    should_continue_from_dossier,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_BASE_DOSSIER: dict[str, Any] = {
    "schema_version": "1.0",
    "document": {"ocid": "ocds-test-001:A-1"},
    "risk_summary": {"total_flags": 2, "risk_level": "MEDIO", "total_score": 30},
    "flags": [],
    "questions_for_authority": [],
}


def _state_with_dossier(
    supplier_ruc: str | None = "20605681281",
    buyer_ruc: str | None = "20131370645",
) -> AuditorState:
    return {
        "pdf_path": "/tmp/test.pdf",
        "ocid": "ocds-test-001:A-1",
        "sector": "salud",
        "supplier_ruc": supplier_ruc,
        "buyer_ruc": buyer_ruc,
        "dossier": dict(_BASE_DOSSIER),
        "pages": [],
        "chunks": [],
        "flags": [],
        "score": 30,
        "risk_level": "MEDIO",
        "audit_trace": [],
        "status": "complete",
    }


def _mock_enrichment(findings: dict[str, Any]) -> Any:
    """Return a mock of enrich_dossier_with_graph that injects findings."""
    def enricher(*, dossier: dict, supplier_ruc: str, buyer_ruc: str | None = None, neo4j_client: Any = None) -> dict:
        dossier["graph_findings"] = findings
        return dossier
    return enricher


# ---------------------------------------------------------------------------
# AuditorState: new fields
# ---------------------------------------------------------------------------


def test_auditor_state_accepts_supplier_ruc() -> None:
    state: AuditorState = {
        "supplier_ruc": "20605681281",
        "buyer_ruc": "20131370645",
        "graph_findings": None,
    }
    assert state["supplier_ruc"] == "20605681281"
    assert state["buyer_ruc"] == "20131370645"
    assert state["graph_findings"] is None


def test_auditor_state_backwards_compatible_without_new_fields() -> None:
    """Existing code that doesn't set supplier_ruc/buyer_ruc still works."""
    state: AuditorState = {
        "pdf_path": "/tmp/test.pdf",
        "status": "initialized",
    }
    assert state.get("supplier_ruc") is None
    assert state.get("buyer_ruc") is None
    assert state.get("graph_findings") is None


# ---------------------------------------------------------------------------
# should_continue_from_dossier routing
# ---------------------------------------------------------------------------


def test_routing_to_enrich_graph_when_supplier_ruc_present() -> None:
    state: AuditorState = {"status": "complete", "supplier_ruc": "20605681281"}
    assert should_continue_from_dossier(state) == "enrich_graph"


def test_routing_to_end_when_no_supplier_ruc() -> None:
    state: AuditorState = {"status": "complete", "supplier_ruc": None}
    assert should_continue_from_dossier(state) == "__end__"


def test_routing_to_end_when_supplier_ruc_not_set_at_all() -> None:
    state: AuditorState = {"status": "complete"}
    assert should_continue_from_dossier(state) == "__end__"


def test_routing_to_end_on_error_status() -> None:
    state: AuditorState = {"status": "error", "supplier_ruc": "20605681281"}
    assert should_continue_from_dossier(state) == "__end__"


# ---------------------------------------------------------------------------
# node_enrich_graph: happy path
# ---------------------------------------------------------------------------


def test_node_enrich_graph_populates_findings() -> None:
    findings = {
        "supplier_ruc": "20605681281",
        "flags_in_graph": 3,
        "risk_delta": 15,
        "signals": [{"type": "HISTORIAL_SENALES", "description": "..."}],
        "error": None,
    }
    state = _state_with_dossier()

    with patch(
        "agenteperry.graph.neo4j_enrichment.enrich_dossier_with_graph",
        side_effect=_mock_enrichment(findings),
    ):
        result = node_enrich_graph(state)

    assert result["status"] == "complete"
    assert result["graph_findings"] == findings
    assert result["dossier"]["graph_findings"] == findings


def test_node_enrich_graph_writes_audit_trace() -> None:
    findings = {"risk_delta": 25, "signals": [{}, {}], "error": None}
    state = _state_with_dossier()

    with patch(
        "agenteperry.graph.neo4j_enrichment.enrich_dossier_with_graph",
        side_effect=_mock_enrichment(findings),
    ):
        result = node_enrich_graph(state)

    traces = result.get("audit_trace") or []
    enrich_trace = next((t for t in traces if t.get("node") == "enrich_graph"), None)
    assert enrich_trace is not None
    assert enrich_trace["status"] == "ok"
    assert enrich_trace["risk_delta"] == 25
    assert enrich_trace["signals"] == 2
    assert enrich_trace["supplier_ruc"] == "20605681281"
    assert "duration_ms" in enrich_trace


def test_node_enrich_graph_passes_buyer_ruc() -> None:
    """Verify buyer_ruc is forwarded to enrich_dossier_with_graph."""
    captured: dict[str, Any] = {}

    def capturing_enricher(*, dossier: dict, supplier_ruc: str, buyer_ruc: str | None = None, neo4j_client: Any = None) -> dict:
        captured["supplier_ruc"] = supplier_ruc
        captured["buyer_ruc"] = buyer_ruc
        dossier["graph_findings"] = {"risk_delta": 0, "signals": [], "error": None}
        return dossier

    state = _state_with_dossier(supplier_ruc="20605681281", buyer_ruc="20131370645")

    with patch("agenteperry.graph.neo4j_enrichment.enrich_dossier_with_graph", side_effect=capturing_enricher):
        node_enrich_graph(state)

    assert captured["supplier_ruc"] == "20605681281"
    assert captured["buyer_ruc"] == "20131370645"


# ---------------------------------------------------------------------------
# node_enrich_graph: error propagation (obligatorio)
# ---------------------------------------------------------------------------


def test_node_enrich_graph_surfaces_enrichment_error_field() -> None:
    """When enrich_dossier_with_graph returns graph_findings.error, node sets state error."""
    findings = {
        "risk_delta": 0,
        "signals": [],
        "error": "Neo4j connection refused: neo4j+s://98d0987c.databases.neo4j.io",
    }
    state = _state_with_dossier()

    with patch(
        "agenteperry.graph.neo4j_enrichment.enrich_dossier_with_graph",
        side_effect=_mock_enrichment(findings),
    ):
        result = node_enrich_graph(state)

    assert result["status"] == "error"
    assert "Neo4j" in (result.get("error") or "")
    traces = result.get("audit_trace") or []
    enrich_trace = next((t for t in traces if t.get("node") == "enrich_graph"), None)
    assert enrich_trace is not None
    assert enrich_trace["status"] == "error"


def test_node_enrich_graph_raises_on_exception() -> None:
    """Neo4j connection errors propagate — no silent swallowing (obligatorio)."""
    state = _state_with_dossier()

    with patch(
        "agenteperry.graph.neo4j_enrichment.enrich_dossier_with_graph",
        side_effect=ConnectionError("Neo4j Aura unreachable"),
    ):
        with pytest.raises(ConnectionError, match="Neo4j Aura unreachable"):
            node_enrich_graph(state)


def test_node_enrich_graph_errors_without_supplier_ruc() -> None:
    """Safety guard: if called without supplier_ruc, sets state error."""
    state = _state_with_dossier(supplier_ruc=None)

    result = node_enrich_graph(state)

    assert result["status"] == "error"
    assert "supplier_ruc" in (result.get("error") or "")


# ---------------------------------------------------------------------------
# run_auditor: new parameters forwarded to initial state
# ---------------------------------------------------------------------------


def test_run_auditor_accepts_supplier_and_buyer_ruc_without_pdf() -> None:
    """When PDF is missing, run_auditor returns error but new params are accepted."""
    result = run_auditor(
        pdf_path="/nonexistent/file.pdf",
        sector="salud",
        supplier_ruc="20605681281",
        buyer_ruc="20131370645",
    )
    # PDF not found → error (graph node never reached)
    assert result["status"] == "error"
    assert "not found" in result["error"]


def test_run_auditor_without_supplier_ruc_skips_graph_node() -> None:
    """When supplier_ruc is not set, graph enrichment is skipped entirely."""
    result = run_auditor(
        pdf_path="/nonexistent/file.pdf",
        sector="salud",
        # supplier_ruc intentionally omitted
    )
    # Still fails on missing PDF — but supplier_ruc was None so enrich_graph
    # would have been routed away from even if PDF existed.
    assert result.get("supplier_ruc") is None
    assert result.get("graph_findings") is None
