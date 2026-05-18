#!/usr/bin/env python3
"""PR #14 — Validate a SEACE Salud batch and run AuditorGraph over valid packs.

Inputs
------
A JSONL manifest delivered by the scraping team, conforming to
``docs/SCRAPING_DELIVERY_CONTRACT.md``:

    data/scraped/seace_salud/manifests/<batch>.jsonl

Outputs
-------
- ``data/scraped/seace_salud/reports/<batch>_validation.md``  — human report.
- ``data/scraped/seace_salud/reports/<batch>_summary.json``  — machine metrics.
- ``data/scraped/seace_salud/outputs/<batch>/<pack_id>.auditor.json`` per pack.

Usage
-----

    python scripts/validate_seace_batch.py data/scraped/seace_salud/manifests/batch_001.jsonl

The script is **deterministic**: no LLM, no network, just the calibrated
``document_intelligence`` engine wired through the LangGraph AuditorGraph.

Reglas:
- No relaja el validador.
- Si un pack rechazado tiene errores, los registra textualmente.
- Si la entrega no incluye RUC/quote, lo marca como blocker (no inventa).
- GraphRAG NUNCA se activa desde este script — solo reporta `graph_rag_candidates`.
"""
# pyright: reportMissingImports=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "scrapers" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "document_intelligence" / "src"))


@dataclass
class PackOutcome:
    pack_id: str
    status: str  # "ok" | "rejected" | "no_runnable_document" | "auditor_error"
    process_id: str
    mode: str
    has_supplier_ruc: bool
    has_award_quote: bool
    runnable_doc_id: str | None = None
    flags_count: int = 0
    flags_by_code: dict[str, int] = field(default_factory=lambda: {})
    risk_level: str | None = None
    score: int = 0
    graph_rag_activation: bool = False
    graph_rag_blockers: list[str] = field(default_factory=lambda: [])
    errors: list[str] = field(default_factory=lambda: [])
    auditor_output_path: str | None = None


def _load_batch(path: Path) -> tuple[list[Any], list[tuple[int, list[str]]]]:
    from document_intelligence.document_pack import load_valid_packs_from_jsonl

    if not path.exists():
        raise SystemExit(f"manifest not found: {path}")
    return load_valid_packs_from_jsonl(path, skip_invalid=True)


def _pick_runnable_document(pack: Any) -> Any | None:
    primary_types = {"tdr", "bases", "bases_integradas"}
    secondary_types = {"absolucion_consultas", "adjudicacion", "buena_pro"}

    for doc in pack.documents:
        if doc.document_type.value in primary_types and doc.usable_for_analysis:
            return doc
    for doc in pack.documents:
        if doc.document_type.value in secondary_types and doc.usable_for_analysis:
            return doc
    return None


def _run_auditor_on_pack(pack: Any, outputs_dir: Path) -> PackOutcome:
    from agenteperry.tdr.auditor import run_auditor

    outcome = PackOutcome(
        pack_id=pack.pack_id,
        status="ok",
        process_id=pack.process_id,
        mode=pack.mode.value,
        has_supplier_ruc=bool(pack.award and pack.award.supplier_ruc),
        has_award_quote=bool(pack.award and pack.award.award_source_quote.strip()),
    )

    doc = _pick_runnable_document(pack)
    if doc is None:
        outcome.status = "no_runnable_document"
        outcome.errors.append(
            "no usable tdr/bases/bases_integradas/absolucion_consultas/buena_pro doc"
        )
        return outcome

    outcome.runnable_doc_id = doc.document_id
    file_path = doc.file_path
    abs_path = Path(file_path)
    if not abs_path.is_absolute():
        abs_path = REPO_ROOT / file_path
    if not abs_path.exists():
        outcome.status = "auditor_error"
        outcome.errors.append(f"document file not found at {abs_path}")
        return outcome

    try:
        result = run_auditor(
            pdf_path=str(abs_path),
            sector=pack.sector,
            ocid=pack.ocid or pack.process_id,
            entity_name=pack.entity_name,
            procedure_code=pack.procedure_code,
            monto=(pack.award.award_amount if pack.award else None),
        )
    except Exception as exc:  # noqa: BLE001 — surface as outcome error
        outcome.status = "auditor_error"
        outcome.errors.append(f"auditor crashed: {type(exc).__name__}: {exc}")
        return outcome

    flags = result.get("flags", [])
    outcome.flags_count = len(flags)
    counter: Counter[str] = Counter(f.flag_code for f in flags)
    outcome.flags_by_code = dict(counter)
    outcome.risk_level = result.get("risk_level")
    outcome.score = int(result.get("score") or 0)

    # GraphRAG candidates: investigative mode + supplier_ruc + score >= 75.
    # We REPORT these — we DO NOT trigger.
    can_activate = (
        pack.mode.value == "investigative"
        and outcome.has_supplier_ruc
        and outcome.has_award_quote
        and outcome.score >= 75
    )
    outcome.graph_rag_activation = False  # hard invariant for this script
    if not can_activate:
        if pack.mode.value != "investigative":
            outcome.graph_rag_blockers.append("not_investigative_mode")
        if not outcome.has_supplier_ruc:
            outcome.graph_rag_blockers.append("missing_supplier_ruc")
        if not outcome.has_award_quote:
            outcome.graph_rag_blockers.append("missing_award_quote")
        if outcome.score < 75:
            outcome.graph_rag_blockers.append(f"score_below_threshold({outcome.score}<75)")

    # Persist auditor JSON output.
    outputs_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "pack_id": pack.pack_id,
        "process_id": pack.process_id,
        "ocid": pack.ocid,
        "entity_name": pack.entity_name,
        "mode": pack.mode.value,
        "runnable_doc_id": doc.document_id,
        "document_type": doc.document_type.value,
        "risk_level": result.get("risk_level"),
        "score": result.get("score"),
        "audit_trace": result.get("audit_trace", []),
        "flags": [
            {
                "flag_code": f.flag_code,
                "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                "page_number": f.page_number,
                "evidence_quote": f.evidence_quote,
                "explanation": f.explanation,
                "score_contribution": f.score_contribution,
            }
            for f in flags
        ],
        "graph_rag_activation": False,
        "graph_rag_candidate": can_activate,
        "graph_rag_blockers": outcome.graph_rag_blockers,
    }
    out_path = outputs_dir / f"{pack.pack_id}.auditor.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        outcome.auditor_output_path = str(out_path.relative_to(REPO_ROOT))
    except ValueError:
        outcome.auditor_output_path = str(out_path)
    return outcome


def _aggregate_metrics(
    outcomes: list[PackOutcome],
    rejected: list[tuple[int, list[str]]],
) -> dict[str, Any]:
    flags_by_code: Counter[str] = Counter()
    risk_dist: Counter[str] = Counter()
    score_dist = Counter[str]()
    error_counter: Counter[str] = Counter()
    runnable = 0
    score_50 = 0
    score_75 = 0
    investigative = 0
    preventive = 0
    with_ruc = 0
    with_quote = 0
    graphrag_candidates = 0

    for outcome in outcomes:
        if outcome.status != "ok":
            error_counter[outcome.status] += 1
            continue
        runnable += 1
        for code, count in outcome.flags_by_code.items():
            flags_by_code[code] += count
        if outcome.risk_level:
            risk_dist[outcome.risk_level] += 1
        bucket = _score_bucket(outcome.score)
        score_dist[bucket] += 1
        if outcome.score >= 50:
            score_50 += 1
        if outcome.score >= 75:
            score_75 += 1
        if outcome.mode == "investigative":
            investigative += 1
        else:
            preventive += 1
        if outcome.has_supplier_ruc:
            with_ruc += 1
        if outcome.has_award_quote:
            with_quote += 1
        if (
            outcome.mode == "investigative"
            and outcome.has_supplier_ruc
            and outcome.has_award_quote
            and outcome.score >= 75
        ):
            graphrag_candidates += 1

    rejected_error_counter: Counter[str] = Counter()
    for _line, errs in rejected:
        for err in errs:
            head = err.split(":", 1)[0].strip()
            rejected_error_counter[head] += 1

    return {
        "packs_total": len(outcomes) + len(rejected),
        "packs_valid": len(outcomes),
        "packs_rejected": len(rejected),
        "packs_runnable_by_auditor": runnable,
        "preventive_count": preventive,
        "investigative_count": investigative,
        "packs_with_supplier_ruc": with_ruc,
        "packs_with_award_quote": with_quote,
        "packs_score_50_plus": score_50,
        "packs_score_75_plus": score_75,
        "graph_rag_candidates": graphrag_candidates,
        "flags_by_code": dict(flags_by_code),
        "risk_distribution": dict(risk_dist),
        "score_distribution": dict(score_dist),
        "outcome_status_counts": dict(error_counter),
        "rejected_error_heads": dict(rejected_error_counter),
    }


def _score_bucket(score: int) -> str:
    if score == 0:
        return "0"
    if score < 25:
        return "1-24"
    if score < 50:
        return "25-49"
    if score < 75:
        return "50-74"
    if score < 100:
        return "75-99"
    return "100"


def _render_report(
    batch_path: Path,
    outcomes: list[PackOutcome],
    rejected: list[tuple[int, list[str]]],
    metrics: dict[str, Any],
) -> str:
    lines: list[str] = []
    lines.append(f"# Batch Validation Report — `{batch_path.name}`")
    lines.append("")
    lines.append("PR: #14 — Real Pack Validation")
    lines.append(f"Manifest: `{batch_path}`")
    lines.append("")
    lines.append("## Top-line metrics")
    lines.append("")
    lines.append("| metric | value |")
    lines.append("|--------|------:|")
    for key in (
        "packs_total",
        "packs_valid",
        "packs_rejected",
        "packs_runnable_by_auditor",
        "preventive_count",
        "investigative_count",
        "packs_with_supplier_ruc",
        "packs_with_award_quote",
        "packs_score_50_plus",
        "packs_score_75_plus",
        "graph_rag_candidates",
    ):
        lines.append(f"| `{key}` | {metrics[key]} |")
    lines.append("")
    lines.append("## Flags by code")
    if metrics["flags_by_code"]:
        lines.append("")
        lines.append("| flag_code | count |")
        lines.append("|-----------|------:|")
        for code, count in sorted(metrics["flags_by_code"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| `{code}` | {count} |")
    else:
        lines.append("")
        lines.append("_no flags emitted across the batch_")
    lines.append("")
    lines.append("## Risk distribution")
    if metrics["risk_distribution"]:
        lines.append("")
        lines.append("| risk_level | count |")
        lines.append("|------------|------:|")
        for risk, count in metrics["risk_distribution"].items():
            lines.append(f"| {risk} | {count} |")
    else:
        lines.append("")
        lines.append("_no risk_level entries_")
    lines.append("")
    lines.append("## Score distribution")
    lines.append("")
    lines.append("| bucket | count |")
    lines.append("|--------|------:|")
    for bucket in ("0", "1-24", "25-49", "50-74", "75-99", "100"):
        lines.append(f"| {bucket} | {metrics['score_distribution'].get(bucket, 0)} |")
    lines.append("")
    lines.append("## Rejected packs (validator errors)")
    if rejected:
        lines.append("")
        for line_no, errs in rejected:
            lines.append(f"- **line {line_no}** ({len(errs)} errors)")
            for err in errs:
                lines.append(f"  - {err}")
    else:
        lines.append("")
        lines.append("_no packs rejected by the validator_")
    lines.append("")
    lines.append("## GraphRAG candidates (REPORTED, NOT ACTIVATED)")
    candidates = [
        o
        for o in outcomes
        if o.mode == "investigative"
        and o.has_supplier_ruc
        and o.has_award_quote
        and o.score >= 75
    ]
    if candidates:
        lines.append("")
        for o in candidates:
            lines.append(
                f"- `{o.pack_id}` — process_id={o.process_id} score={o.score} "
                f"flags={o.flags_count}"
            )
    else:
        lines.append("")
        lines.append(
            "_no packs cross the activation gate. Most common blockers below._"
        )
    blocker_counter: Counter[str] = Counter()
    for o in outcomes:
        for blocker in o.graph_rag_blockers:
            head = blocker.split("(", 1)[0]
            blocker_counter[head] += 1
    if blocker_counter:
        lines.append("")
        lines.append("| blocker | count |")
        lines.append("|---------|------:|")
        for blocker, count in blocker_counter.most_common():
            lines.append(f"| `{blocker}` | {count} |")
    lines.append("")
    lines.append("## Per-pack outcomes")
    lines.append("")
    lines.append("| pack_id | status | mode | runnable_doc | risk | score | flags | output |")
    lines.append("|---------|--------|------|--------------|------|------:|------:|--------|")
    for o in outcomes:
        out_link = f"`{o.auditor_output_path}`" if o.auditor_output_path else "—"
        lines.append(
            f"| `{o.pack_id}` | {o.status} | {o.mode} | "
            f"`{o.runnable_doc_id or '—'}` | {o.risk_level or '—'} | "
            f"{o.score} | {o.flags_count} | {out_link} |"
        )
    lines.append("")
    lines.append("## Recomendación")
    lines.append("")
    if metrics["packs_valid"] == 0:
        lines.append(
            "🛑 **NO-GO** — el batch entregado no tiene packs válidos. Revisar "
            "errores arriba y volver a entregar."
        )
    elif metrics["graph_rag_candidates"] == 0:
        lines.append(
            "🟡 **CALIBRATION** — el motor corrió sin errores pero ningún pack "
            "cruzó la gate de GraphRAG (score≥75 + supplier_ruc + investigative). "
            "GraphRAG sigue correctamente bloqueado. Siguiente paso: pedir al "
            "equipo scraping packs investigativos con award_evidence completo."
        )
    else:
        lines.append(
            f"🟢 **GO** — {metrics['graph_rag_candidates']} pack(s) candidato(s) a "
            "GraphRAG. NO activar aún — confirmar verificación humana de los flags "
            "antes de proceder a PR #15."
        )
    return "\n".join(lines) + "\n"


def run(
    manifest: Path,
    *,
    outputs_root: Path | None = None,
    reports_root: Path | None = None,
) -> dict[str, Any]:
    outputs_root = outputs_root or (REPO_ROOT / "data" / "scraped" / "seace_salud" / "outputs")
    reports_root = reports_root or (REPO_ROOT / "data" / "scraped" / "seace_salud" / "reports")
    outputs_dir = outputs_root / manifest.stem
    reports_root.mkdir(parents=True, exist_ok=True)

    valid_packs, rejected = _load_batch(manifest)

    outcomes: list[PackOutcome] = []
    for pack in valid_packs:
        outcomes.append(_run_auditor_on_pack(pack, outputs_dir))

    metrics = _aggregate_metrics(outcomes, rejected)
    report_md = _render_report(manifest, outcomes, rejected, metrics)

    report_path = reports_root / f"{manifest.stem}_validation.md"
    report_path.write_text(report_md, encoding="utf-8")

    summary_path = reports_root / f"{manifest.stem}_summary.json"
    summary_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(REPO_ROOT))
        except ValueError:
            return str(p)

    metrics["report_path"] = _rel(report_path)
    metrics["summary_path"] = _rel(summary_path)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "manifest",
        type=Path,
        help="JSONL manifest from the scraping team (e.g. batch_001.jsonl)",
    )
    parser.add_argument("--outputs-root", type=Path, default=None)
    parser.add_argument("--reports-root", type=Path, default=None)
    args = parser.parse_args()
    metrics = run(
        args.manifest, outputs_root=args.outputs_root, reports_root=args.reports_root
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0 if metrics["packs_valid"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
