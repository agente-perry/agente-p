#!/usr/bin/env python3
"""Golden set batch runner for SPEC-0007.

Reads ``metadata.csv``, invokes ``python -m document_intelligence analyze`` for
each row, and writes a ``summary.json`` aggregating flag counts, errors, and a
naive expected-vs-actual comparison.

Usage::

    python scripts/run_golden_set.py \\
        --metadata data/golden_set/metadata.csv \\
        --pdf-dir data/golden_set/pdfs \\
        --out data/golden_set/outputs

Defaults match the layout documented in ``data/golden_set/README.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_QUESTION = "Detecta senales de baja trazabilidad y requisitos restrictivos."
OCR_MODES = ("off", "auto", "force")


@dataclass
class RowResult:
    id: str
    status: str  # "ok" | "missing_pdf" | "analyze_failed" | "invalid_metadata"
    expected_flags: list[str] = field(default_factory=lambda: [])
    actual_flags: list[str] = field(default_factory=lambda: [])
    output_path: str | None = None
    error: str | None = None


def _read_metadata(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise SystemExit(f"metadata not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"metadata is empty: {path}")
    required = {"id", "file_name", "document_type", "expected_flags"}
    missing = required - set(rows[0].keys())
    if missing:
        raise SystemExit(f"metadata missing required columns: {sorted(missing)}")
    return rows


def _parse_expected(raw: str) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.replace(",", ";").split(";") if item.strip()]


def _run_analyze(
    *,
    pdf_path: Path,
    question: str,
    output_path: Path,
    python_bin: str,
    ocr_mode: str = "off",
) -> tuple[bool, str]:
    cmd = [
        python_bin,
        "-m",
        "document_intelligence",
        "analyze",
        str(pdf_path),
        "--question",
        question,
        "--output",
        str(output_path),
        "--ocr",
        ocr_mode,
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "analyze timed out (>300s)"
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout).strip().splitlines()[-5:]
        return False, "analyze exited {code}: {tail}".format(
            code=completed.returncode, tail=" | ".join(tail)
        )
    return True, ""


def _load_actual_flags(output_path: Path) -> list[str]:
    if not output_path.exists():
        return []
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    flags = payload.get("flags") or []
    return [flag.get("flag_code", "") for flag in flags if flag.get("flag_code")]


def _coverage(expected: list[str], actual: list[str]) -> dict[str, float | list[str]]:
    expected_set = set(expected)
    actual_set = set(actual)
    if not expected_set:
        precision = 1.0 if not actual_set else 0.0
        recall = 1.0
    else:
        true_positives = expected_set & actual_set
        precision = len(true_positives) / len(actual_set) if actual_set else 0.0
        recall = len(true_positives) / len(expected_set)
    return {
        "precision_estimate": round(precision, 3),
        "recall_estimate": round(recall, 3),
        "missing": sorted(expected_set - actual_set),
        "unexpected": sorted(actual_set - expected_set),
    }


def run_golden_set(
    *,
    metadata_path: Path,
    pdf_dir: Path,
    out_dir: Path,
    default_question: str = DEFAULT_QUESTION,
    python_bin: str = sys.executable,
    ocr_mode: str = "off",
) -> dict[str, object]:
    rows = _read_metadata(metadata_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[RowResult] = []

    for row in rows:
        row_id = row.get("id", "").strip()
        file_name = row.get("file_name", "").strip()
        if not row_id or not file_name:
            results.append(
                RowResult(
                    id=row_id or "?",
                    status="invalid_metadata",
                    error="id and file_name are required per row",
                )
            )
            continue
        pdf_path = pdf_dir / file_name
        if not pdf_path.exists():
            results.append(
                RowResult(
                    id=row_id,
                    status="missing_pdf",
                    expected_flags=_parse_expected(row.get("expected_flags", "")),
                    error=f"{pdf_path} not found",
                )
            )
            continue
        question = row.get("question", "").strip() or default_question
        output_path = out_dir / f"{row_id}.analysis.json"
        ok, error = _run_analyze(
            pdf_path=pdf_path,
            question=question,
            output_path=output_path,
            python_bin=python_bin,
            ocr_mode=ocr_mode,
        )
        if not ok:
            results.append(
                RowResult(
                    id=row_id,
                    status="analyze_failed",
                    expected_flags=_parse_expected(row.get("expected_flags", "")),
                    error=error,
                )
            )
            continue
        actual = _load_actual_flags(output_path)
        results.append(
            RowResult(
                id=row_id,
                status="ok",
                expected_flags=_parse_expected(row.get("expected_flags", "")),
                actual_flags=actual,
                output_path=str(output_path),
            )
        )

    flags_counter: Counter[str] = Counter()
    documents_with_no_flags = 0
    errors: list[dict[str, str]] = []
    per_doc: dict[str, dict[str, object]] = {}
    ocr_documents_needing = 0
    ocr_pages_needing = 0
    ocr_pages_applied = 0
    ocr_available_seen: bool | None = None
    for result in results:
        if result.status == "ok":
            flags_counter.update(result.actual_flags)
            if not result.actual_flags:
                documents_with_no_flags += 1
            per_doc[result.id] = {
                "expected": result.expected_flags,
                "actual": result.actual_flags,
                "output_path": result.output_path,
                **_coverage(result.expected_flags, result.actual_flags),
            }
            # Best-effort: peek inside the analysis JSON for parse-summary breadcrumbs
            # left by the orchestrator. The schema is forward-compatible: missing
            # fields just collapse to zeros.
            ocr_stats = _read_ocr_stats(Path(result.output_path)) if result.output_path else None
            if ocr_stats is not None:
                if ocr_stats.get("pages_needing_ocr", 0) > 0:
                    ocr_documents_needing += 1
                ocr_pages_needing += int(ocr_stats.get("pages_needing_ocr", 0))
                ocr_pages_applied += int(ocr_stats.get("ocr_applied_pages", 0))
                available = ocr_stats.get("ocr_available")
                if isinstance(available, bool):
                    ocr_available_seen = (
                        available if ocr_available_seen is None else ocr_available_seen or available
                    )
        else:
            errors.append(
                {
                    "id": result.id,
                    "status": result.status,
                    "error": result.error or "",
                }
            )

    analyzed = sum(1 for r in results if r.status == "ok")
    summary: dict[str, object] = {
        "documents_total": len(rows),
        "documents_analyzed": analyzed,
        "flags_total": sum(flags_counter.values()),
        "flags_by_code": dict(flags_counter),
        "documents_with_no_flags": documents_with_no_flags,
        "errors": errors,
        "per_document": per_doc,
        "ocr": {
            "mode": ocr_mode,
            "documents_needing_ocr": ocr_documents_needing,
            "pages_needing_ocr": ocr_pages_needing,
            "pages_ocr_applied": ocr_pages_applied,
            "ocr_available": ocr_available_seen,
        },
        "command_default": shlex.join(
            [
                python_bin,
                "-m",
                "document_intelligence",
                "analyze",
                "<pdf_path>",
                "--question",
                default_question,
                "--ocr",
                ocr_mode,
                "--output",
                "<out>/<id>.analysis.json",
            ]
        ),
    }
    return summary


def _read_ocr_stats(analysis_path: Path) -> dict[str, object] | None:
    """Pull OCR breadcrumbs from an analysis JSON, if present.

    The orchestrator emits OCR fields via its structured ``logs``, not the
    public AnalysisResult schema. ``analysis.json`` therefore may or may not
    carry OCR breadcrumbs depending on the CLI output mode. When absent, this
    function returns None and the caller treats OCR stats as unknown.
    """
    if not analysis_path.exists():
        return None
    try:
        payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    # Future-proof: the CLI may surface a top-level "parse_summary" key.
    parse_summary = payload.get("parse_summary")
    if isinstance(parse_summary, dict):
        return parse_summary
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run document_intelligence analyze on a golden set.")
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("data/golden_set/metadata.csv"),
        help="Path to metadata CSV (default: data/golden_set/metadata.csv)",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=Path("data/golden_set/pdfs"),
        help="Directory holding the PDFs referenced by metadata.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/golden_set/outputs"),
        help="Directory where per-document JSON + summary.json are written",
    )
    parser.add_argument(
        "--question",
        type=str,
        default=DEFAULT_QUESTION,
        help="Default question for analyze when metadata row has no override",
    )
    parser.add_argument(
        "--python",
        type=str,
        default=sys.executable,
        help="Python interpreter that has document-intelligence installed",
    )
    parser.add_argument(
        "--ocr",
        choices=OCR_MODES,
        default="off",
        help="OCR mode passed through to the analyze CLI (off|auto|force).",
    )
    args = parser.parse_args()

    summary = run_golden_set(
        metadata_path=args.metadata,
        pdf_dir=args.pdf_dir,
        out_dir=args.out,
        default_question=args.question,
        python_bin=args.python,
        ocr_mode=args.ocr,
    )
    summary_path = args.out / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(  # noqa: T201 — CLI script
        f"Analyzed {summary['documents_analyzed']}/{summary['documents_total']} documents. "
        f"Flags total: {summary['flags_total']}. "
        f"Summary: {summary_path}"
    )
    if summary["errors"]:
        print(f"  {len(summary['errors'])} document(s) reported errors.", file=sys.stderr)  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
