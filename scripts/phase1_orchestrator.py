#!/usr/bin/env python3
"""Phase 1 Orchestrator: run the complete scraping pipeline end-to-end.

Steps:
1. Download and filter OCDS (salud + ambiente)
2. Download SUNAT Padrón Reducido
3. Download SEACE PDF documents
4. Classify OCR with MiniMax API (parallel)
5. Validate delivery manifests
6. Build process_document_packs.jsonl
7. Select Golden Set

Usage:
    python scripts/phase1_orchestrator.py --base-dir data/scraped/seace_salud
    python scripts/phase1_orchestrator.py --base-dir data/scraped/seace_salud --skip-ocr
    python scripts/phase1_orchestrator.py --limit-contracts 100 --limit-docs 20
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_VERSION = "1.0.0"

STEPS = [
    ("ocds_filter", "Download and filter OCDS (salud + ambiente)"),
    ("sunat_padron", "Download SUNAT Padrón Reducido"),
    ("seace_documents", "Download SEACE PDF documents"),
    ("ocr_classifier", "Classify OCR with MiniMax API"),
    ("validate", "Validate delivery manifests"),
    ("build_packs", "Build process_document_packs.jsonl"),
    ("golden_set", "Select Golden Set candidates"),
]


def run_step(script_name: str, args: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    script_path = Path(__file__).parent / script_name
    cmd = [sys.executable, str(script_path)] + args
    print(f"\n{'=' * 60}", flush=True)
    print(f"STEP: {script_name}", flush=True)
    print(f"CMD:  {' '.join(cmd)}", flush=True)
    print("=" * 60, flush=True)
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=env or None,
            timeout=7200,
        )
        elapsed = time.monotonic() - t0
        ok = result.returncode == 0
        print(f"\n[{'OK' if ok else 'FAIL'}] {script_name} ({elapsed:.1f}s)", flush=True)
        if result.stdout:
            print(result.stdout[:2000], flush=True)
        if result.stderr and not ok:
            print(result.stderr[:1000], flush=True, file=sys.stderr)
        return {"step": script_name, "ok": ok, "elapsed": round(elapsed, 1), "rc": result.returncode, "stdout": result.stdout[:500]}
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - t0
        print(f"\n[TIMEOUT] {script_name} ({elapsed:.1f}s)", flush=True)
        return {"step": script_name, "ok": False, "elapsed": round(elapsed, 1), "rc": -1, "error": "timeout"}
    except Exception as exc:
        elapsed = time.monotonic() - t0
        print(f"\n[ERROR] {script_name}: {exc}", flush=True)
        return {"step": script_name, "ok": False, "elapsed": round(elapsed, 1), "rc": -1, "error": str(exc)[:200]}


def run_orchestrator(
    base_dir: Path,
    skip_ocr: bool = False,
    limit_contracts: int | None = None,
    limit_docs: int | None = None,
    dry_run: bool = False,
    workers: int = 20,
) -> dict[str, Any]:
    base_dir = base_dir.resolve()
    results: list[dict[str, Any]] = []
    t0_total = time.monotonic()

    step_args: dict[str, list[str]] = {
        "1_ocds_filter": [
            "--output-dir", str(base_dir),
        ],
        "2_sunat_padron": [
            "--output-dir", str(base_dir.parent / "sunat"),
            "--processes-csv", str(base_dir / "processes.csv"),
        ],
        "3_seace_documents": [
            "--base-dir", str(base_dir),
        ],
        "4_ocr_classifier": [
            "--base-dir", str(base_dir),
            "--workers", str(workers),
        ],
    }

    if limit_contracts:
        step_args["1_ocds_filter"].extend(["--limit", str(limit_contracts)])
    if limit_docs:
        step_args["3_seace_documents"].extend(["--limit", str(limit_docs)])
    if skip_ocr:
        step_args["4_ocr_classifier"].append("--dry-run")

    for step_id, step_desc in STEPS:
        script_name = f"phase1_{step_id}.py"
        script_path = Path(__file__).parent / script_name

        if not script_path.exists():
            print(f"[SKIP] {step_id} — {script_name} not found ({step_desc})", flush=True)
            continue

        if skip_ocr and step_id == "4_ocr_classifier":
            print(f"[SKIP] {step_id} — OCR skipped by --skip-ocr flag", flush=True)
            results.append({"step": step_id, "ok": True, "skipped": True, "reason": "skip-ocr"})
            continue

        if dry_run and step_id in ("3_seace_documents", "4_ocr_classifier"):
            print(f"[SKIP] {step_id} — dry run ({step_desc})", flush=True)
            results.append({"step": step_id, "ok": True, "skipped": True, "reason": "dry-run"})
            continue

        args = step_args.get(step_id, [])
        result = run_step(script_name, args)
        results.append(result)

        if not result["ok"] and step_id not in ("5_validate", "6_build_packs", "7_golden_set"):
            print(f"[ABORT] Pipeline aborted at {step_id} — non-critical step failed", flush=True)
            break

    elapsed_total = time.monotonic() - t0_total

    summary: dict[str, Any] = {
        "total_steps": len(STEPS),
        "completed_steps": len(results),
        "ok_steps": sum(1 for r in results if r.get("ok")),
        "failed_steps": sum(1 for r in results if not r.get("ok")),
        "elapsed_total_seconds": round(elapsed_total, 1),
        "base_dir": str(base_dir),
        "results": results,
    }

    print(f"\n{'=' * 60}", flush=True)
    print("PHASE 1 ORCHESTRATOR SUMMARY", flush=True)
    print("=" * 60, flush=True)
    print(f"Total steps: {summary['total_steps']}", flush=True)
    print(f"Completed:   {summary['completed_steps']}", flush=True)
    print(f"OK:          {summary['ok_steps']}", flush=True)
    print(f"Failed:      {summary['failed_steps']}", flush=True)
    print(f"Elapsed:     {elapsed_total:.1f}s", flush=True)
    for r in results:
        status = "OK" if r.get("ok") else ("SKIP" if r.get("skipped") else "FAIL")
        step = r.get("step", "?")
        elapsed = r.get("elapsed", "?")
        print(f"  [{status}] {step} ({elapsed}s)", flush=True)

    report_path = base_dir / "phase1_orchestrator_report.json"
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nReport: {report_path}", flush=True)

    return summary


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Phase 1 Orchestrator for scraping pipeline.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--skip-ocr", action="store_true", help="Skip OCR classification step")
    parser.add_argument("--limit-contracts", type=int, default=None, help="Limit contracts for testing")
    parser.add_argument("--limit-docs", type=int, default=None, help="Limit documents for testing")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (skip downloads)")
    parser.add_argument("--workers", type=int, default=20, help="Parallel workers for OCR")
    args = parser.parse_args()

    summary = run_orchestrator(
        base_dir=args.base_dir,
        skip_ocr=args.skip_ocr,
        limit_contracts=args.limit_contracts,
        limit_docs=args.limit_docs,
        dry_run=args.dry_run,
        workers=args.workers,
    )

    failed = sum(1 for r in summary["results"] if not r.get("ok") and not r.get("skipped"))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())