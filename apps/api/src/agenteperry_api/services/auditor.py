"""On-demand AuditorGraph trigger.

Lazy-imports the heavy stack (document_intelligence + langgraph +
agenteperry.tdr.auditor) only when actually called. When the stack is
unavailable in the runtime venv, returns ``None`` so the router can emit
a 501.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def is_available() -> bool:
    try:
        import importlib

        importlib.import_module("agenteperry.tdr.auditor")
        importlib.import_module("document_intelligence.agents.orchestrator")
        return True
    except Exception:  # noqa: BLE001 — broad import-time failures
        return False


def run_auditor_on_pdf(
    *,
    pdf_path: Path,
    sector: str | None = None,
    ocid: str | None = None,
    entity_name: str | None = None,
    procedure_code: str | None = None,
    monto: float | None = None,
) -> dict[str, Any] | None:
    """Execute the LangGraph AuditorGraph and return its state.

    Returns ``None`` when the auditor stack is not importable.
    """
    if not is_available():
        return None

    from agenteperry.tdr.auditor import run_auditor

    state = run_auditor(
        pdf_path=str(pdf_path),
        sector=sector,
        ocid=ocid,
        entity_name=entity_name,
        procedure_code=procedure_code,
        monto=monto,
    )
    # The auditor state carries Pydantic objects; project to plain JSON
    # for the API response.
    flags = state.get("flags", [])
    state_out: dict[str, Any] = {
        "status": state.get("status"),
        "risk_level": state.get("risk_level"),
        "score": state.get("score"),
        "total_pages": state.get("total_pages"),
        "coverage_pct": state.get("coverage_pct"),
        "audit_trace": state.get("audit_trace", []),
        "flags": [
            {
                "flag_code": f.flag_code,
                "flag_name": f.flag_name,
                "severity": str(f.severity.value if hasattr(f.severity, "value") else f.severity),
                "score_contribution": f.score_contribution,
                "page_number": f.page_number,
                "chunk_id": f.chunk_id,
                "evidence_quote": f.evidence_quote,
                "explanation": f.explanation,
                "detection_method": f.detection_method,
                "rule_id": f.rule_id,
            }
            for f in flags
        ],
    }
    return state_out
