#!/usr/bin/env python3
"""Interactive demo runner for the LangGraph AuditorGraph.

Streams every node's lifecycle to stdout so an observer can SEE the
agent thinking: check_pdf → parse_pdf → chunk_text → detect_flags →
generate_dossier. Each phase emits a status line; the final block
prints the flags with their TDR evidence + doctrine anchor.

Usage:
    bash scripts/run_auditor_demo.sh
    bash scripts/run_auditor_demo.sh tdr_salud_pliego_001
    python scripts/run_auditor_demo.py --pdf tdr_ambiente_positive_001
    python scripts/run_auditor_demo.py --all

The script prints to TTY with ANSI colors by default; set NO_COLOR=1 to
disable.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apps" / "scrapers" / "src"))
sys.path.insert(0, str(REPO_ROOT / "packages" / "document_intelligence" / "src"))


_USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str) -> str:
    return f"\033[{code}m" if _USE_COLOR else ""


RESET = _c("0")
BOLD = _c("1")
DIM = _c("2")
RED = _c("31")
GREEN = _c("32")
YELLOW = _c("33")
BLUE = _c("34")
MAGENTA = _c("35")
CYAN = _c("36")
WHITE = _c("37")


def _hr(char: str = "─", width: int = 78) -> None:
    print(DIM + char * width + RESET)


def _header(title: str, color: str = CYAN) -> None:
    print()
    _hr("═")
    print(f"{BOLD}{color}{title}{RESET}")
    _hr("═")


def _phase(idx: int, total: int, name: str, status: str, ms: float, extras: dict[str, Any]) -> None:
    icon = "✅" if status == "ok" else "❌"
    color = GREEN if status == "ok" else RED
    print(
        f"  {BOLD}[{idx}/{total}]{RESET}  {icon}  "
        f"{color}{name:<22}{RESET}  {DIM}{ms:>7.1f}ms{RESET}",
        end="",
    )
    if extras:
        extra_str = "  ".join(f"{DIM}{k}={RESET}{v}" for k, v in extras.items())
        print(f"  │  {extra_str}")
    else:
        print()


def _flag_block(flag: Any, idx: int, total: int) -> None:
    sev = str(flag.severity)
    sev_color = {"LOW": YELLOW, "MEDIUM": MAGENTA, "HIGH": RED}.get(sev, WHITE)
    print(
        f"\n  {BOLD}[FLAG {idx}/{total}]{RESET}  "
        f"{sev_color}{BOLD}{flag.flag_code}{RESET}  "
        f"({sev_color}{sev}{RESET})  "
        f"{DIM}confidence×100={flag.score_contribution}{RESET}  "
        f"{DIM}p{flag.page_number}{RESET}"
    )
    quote = (flag.evidence_quote or "").replace("\n", " ").strip()
    if len(quote) > 200:
        quote = quote[:200] + "…"
    print(f"    {CYAN}TDR cita{RESET}    {quote}")
    print(f"    {DIM}{flag.explanation[:160]}{RESET}")


def _doctrine_anchor_block(flag_record: Any) -> None:
    """Pull doctrine anchor by re-running just the document_intelligence path.

    The TdrFlag schema does not carry doctrine_anchor; the calibrated engine
    runs upstream and the auditor adapter drops it. For the demo we re-fetch
    via the deterministic ``first_by_flag_code`` lookup so we can show the
    anchor on screen.
    """
    from document_intelligence.doctrine import load_doctrine
    from document_intelligence.embeddings import get_embedder

    embedder = get_embedder("mock", dim=384)
    idx = load_doctrine(embedder=embedder)
    hit = idx.first_by_flag_code(flag_record.flag_code)
    if hit is None:
        print(f"    {DIM}Doctrine anchor:{RESET} (sin doctrine — flag emitido por regex only)")
        return
    quote = (hit.quote or "").replace("\n", " ").strip()
    if len(quote) > 180:
        quote = quote[:180] + "…"
    print(
        f"    {YELLOW}Doctrina{RESET}    {hit.source}  "
        f"{DIM}page={hit.page or 'n/a'}{RESET}"
    )
    print(f"    {DIM}{quote}{RESET}")


def _summary_table(result: dict[str, Any]) -> None:
    risk = result.get("risk_level", "?")
    risk_color = {
        "SIN_SENALES": GREEN,
        "BAJO": GREEN,
        "MEDIO": YELLOW,
        "ALTO": MAGENTA,
        "CRITICO": RED,
    }.get(risk, WHITE)
    print()
    print(
        f"  {BOLD}status:{RESET}     {result.get('status'):<14}  "
        f"{BOLD}risk:{RESET} {risk_color}{BOLD}{risk}{RESET}  "
        f"{BOLD}score:{RESET} {result.get('score')}/100  "
        f"{BOLD}flags:{RESET} {len(result.get('flags', []))}"
    )
    print(
        f"  {BOLD}pages:{RESET} {result.get('total_pages')}  "
        f"{BOLD}coverage:{RESET} {result.get('coverage_pct', 0):.1f}%"
    )


def run_pdf_demo(pdf_path: Path, sector: str, ocid: str, entity: str | None = None) -> int:
    from agenteperry.tdr.auditor import run_auditor

    _header(f"🤖  AuditorGraph (LangGraph) — {pdf_path.name}", color=CYAN)
    print(
        f"  {DIM}PDF:{RESET}    {pdf_path}\n"
        f"  {DIM}sector:{RESET} {sector}\n"
        f"  {DIM}ocid:{RESET}   {ocid}\n"
        f"  {DIM}entity:{RESET} {entity or 'n/a'}\n"
    )

    print(f"{BOLD}{BLUE}▶  Ejecutando grafo LangGraph (5 nodos secuenciales con checkpointer){RESET}\n")
    started = time.monotonic()
    result = run_auditor(
        pdf_path=str(pdf_path),
        sector=sector,
        ocid=ocid,
        entity_name=entity,
        thread_id=str(uuid.uuid4()),
    )
    total_ms = (time.monotonic() - started) * 1000.0

    trace = result.get("audit_trace", [])
    total_phases = len(trace)
    print(f"{BOLD}{BLUE}┌─ AUDIT TRACE ({total_phases} phases){RESET}")
    for i, event in enumerate(trace, 1):
        extras = {
            k: v
            for k, v in event.items()
            if k not in ("node", "status", "duration_ms", "timestamp")
        }
        _phase(
            i,
            total_phases,
            event.get("node", "?"),
            event.get("status", "?"),
            event.get("duration_ms", 0.0),
            extras,
        )
    print(f"{BOLD}{BLUE}└─ end-to-end: {total_ms:.0f}ms{RESET}")

    _header(f"📊  Resultado final", color=MAGENTA)
    _summary_table(result)

    flags = result.get("flags", [])
    if flags:
        _header(f"🚩  Flags emitidos ({len(flags)})", color=YELLOW)
        for i, flag in enumerate(flags, 1):
            _flag_block(flag, i, len(flags))
            _doctrine_anchor_block(flag)
    else:
        _header(f"🟢  Sin flags — auditor decidió que el documento no presenta señales", color=GREEN)
        print(f"  {DIM}Pipeline mecánico OK. 0 false positives.{RESET}")

    error = result.get("error")
    if error:
        print()
        print(f"  {RED}{BOLD}error:{RESET}  {error}")
        return 1

    print()
    return 0


CATALOG: dict[str, dict[str, str]] = {
    "tdr_ambiente_positive_001": {
        "sector": "ambiente",
        "ocid": "ocds-dgv273-seacev3-1191874",
        "entity": "ANA",
    },
    "tdr_salud_pliego_001": {
        "sector": "salud",
        "ocid": "ocds-dgv273-seacev3-988512",
        "entity": "EsSalud GCL",
    },
    "tdr_ambiente_pliego_001": {
        "sector": "ambiente",
        "ocid": "ocds-dgv273-seacev3-1157442",
        "entity": "SERNANP",
    },
    "tdr_mineria_001": {
        "sector": "ambiente_agua",
        "ocid": "ocds-dgv273-seacev3-2026-ANA-1",
        "entity": "Autoridad Nacional del Agua",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf",
        default="tdr_ambiente_positive_001",
        help="PDF id from data/golden_set/pdfs/ (default: tdr_ambiente_positive_001)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run the demo over every golden-set PDF in sequence",
    )
    args = parser.parse_args()

    pdfs_dir = REPO_ROOT / "data" / "golden_set" / "pdfs"
    targets = list(CATALOG.keys()) if args.all else [args.pdf]
    exit_code = 0
    for target in targets:
        meta = CATALOG.get(target)
        if meta is None:
            print(f"{RED}unknown PDF id: {target}{RESET}", file=sys.stderr)
            print(f"available: {', '.join(CATALOG)}", file=sys.stderr)
            return 2
        pdf_path = pdfs_dir / f"{target}.pdf"
        if not pdf_path.exists():
            print(f"{RED}missing PDF: {pdf_path}{RESET}", file=sys.stderr)
            exit_code = 2
            continue
        code = run_pdf_demo(pdf_path, meta["sector"], meta["ocid"], meta.get("entity"))
        exit_code = exit_code or code
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
