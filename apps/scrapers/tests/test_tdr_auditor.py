"""Tests for the LangGraph AuditorGraph."""
# pyright: reportMissingTypeStubs=false, reportMissingImports=false
# pyright: reportTypedDictNotRequiredAccess=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

from pathlib import Path

import pytest

from agenteperry.tdr.auditor import (
    AuditorState,
    build_auditor_graph,
    run_auditor,
)

DATA_DIR = Path(__file__).parent.parent.parent.parent / "data"
TDR_PDF = DATA_DIR / "golden_set" / "pdfs" / "tdr_salud_pliego_001.pdf"


class TestAuditorState:
    def test_auditor_state_empty(self) -> None:
        state: AuditorState = {}
        assert state.get("pdf_path") is None
        assert state.get("status") is None

    def test_auditor_state_partial(self) -> None:
        state: AuditorState = {
            "pdf_path": "/tmp/test.pdf",
            "tdr_id": "test-001",
            "sector": "salud",
        }
        assert state["pdf_path"] == "/tmp/test.pdf"
        assert state["sector"] == "salud"


class TestBuildAuditorGraph:
    def test_build_graph_no_checkpointer(self) -> None:
        graph = build_auditor_graph(checkpointer=None)
        assert graph is not None

    def test_build_graph_with_memory_saver(self) -> None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        graph = build_auditor_graph(checkpointer=checkpointer)
        assert graph is not None


class TestRunAuditor:
    def test_run_auditor_missing_pdf(self) -> None:
        result = run_auditor(
            pdf_path="/nonexistent/file.pdf",
            sector="salud",
        )
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_run_auditor_on_real_pdf(self) -> None:
        if not TDR_PDF.exists():
            pytest.skip(f"Test PDF not found: {TDR_PDF}")

        result = run_auditor(
            pdf_path=str(TDR_PDF),
            sector="salud",
            ocid="test-ocid-001",
            entity_name="Entidad de Prueba",
            monto=100000.0,
        )

        assert result["status"] == "complete"
        assert result["pdf_path"] == str(TDR_PDF)
        assert result["sector"] == "salud"
        assert result["ocid"] == "test-ocid-001"
        assert result["entity_name"] == "Entidad de Prueba"
        assert result["monto"] == 100000.0
        assert len(result["pages"]) > 0
        assert len(result["chunks"]) > 0
        assert "dossier" in result
        assert "audit_trace" in result
        assert len(result["audit_trace"]) == 5
        assert result["risk_level"] in (
            "SIN_SENALES",
            "BAJO",
            "MEDIO",
            "ALTO",
            "CRITICO",
        )

    def test_run_auditor_checkpointer_replays(self) -> None:
        if not TDR_PDF.exists():
            pytest.skip(f"Test PDF not found: {TDR_PDF}")

        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()
        thread = "test-thread-replay-001"

        result1 = run_auditor(
            pdf_path=str(TDR_PDF),
            sector="salud",
            checkpointer=checkpointer,
            thread_id=thread,
        )
        assert result1["status"] == "complete"

        result2 = run_auditor(
            pdf_path=str(TDR_PDF),
            sector="salud",
            checkpointer=checkpointer,
            thread_id=thread,
        )
        assert result2["status"] == "complete"
        assert result2["pages"] == result1["pages"]
        assert result2["flags"] == result1["flags"]


class TestAuditorGraphNodes:
    def test_check_pdf_node_missing_file(self) -> None:
        state: AuditorState = {"pdf_path": "/nonexistent/test.pdf"}
        from agenteperry.tdr.auditor import node_check_pdf

        result = node_check_pdf(state)
        assert result["status"] == "error"
        assert "not found" in result["error"]

    def test_check_pdf_node_real_pdf(self) -> None:
        if not TDR_PDF.exists():
            pytest.skip(f"Test PDF not found: {TDR_PDF}")

        from agenteperry.tdr.auditor import node_check_pdf

        state: AuditorState = {"pdf_path": str(TDR_PDF)}
        result = node_check_pdf(state)
        assert result["status"] == "pdf_checked"
        assert result["total_pages"] > 0
        assert result["coverage_pct"] > 0


class TestCheckpointerDifferentThreads:
    def test_different_threads_independent(self) -> None:
        if not TDR_PDF.exists():
            pytest.skip(f"Test PDF not found: {TDR_PDF}")

        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

        result_a = run_auditor(
            pdf_path=str(TDR_PDF),
            sector="salud",
            checkpointer=checkpointer,
            thread_id="thread-A",
        )
        result_b = run_auditor(
            pdf_path=str(TDR_PDF),
            sector="ambiente",
            checkpointer=checkpointer,
            thread_id="thread-B",
        )

        assert result_a["sector"] == "salud"
        assert result_b["sector"] == "ambiente"