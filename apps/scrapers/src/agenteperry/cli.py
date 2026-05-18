"""Command line interface for AgentePerry TDR Scanner."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any, cast

import click
import structlog
from rich.console import Console
from rich.table import Table

from agenteperry.cdc.detector import (
    SEACEChangeDetector,
    compute_record_hash,
    detect_sector,
    is_priority,
)
from agenteperry.cdc.pipeline import (
    STATUS_DOSSIER_GENERATED,
    STATUS_NEEDS_OCR,
    STATUS_NO_FLAGS,
    STATUS_NO_TDR,
    STATUS_NOT_PDF,
    CDCPipeline,
)
from agenteperry.collectors import build_collector
from agenteperry.graph import FIND_CONFLICTS_SQL, GET_SUBGRAPH_SQL, map_records_to_graph
from agenteperry.ocr.cli import ocr_group
from agenteperry.patterns import get_pattern, list_patterns
from agenteperry.patterns.coi import COI_PATTERNS
from agenteperry.radar.cli import radar_group
from agenteperry.sources import build_default_registry
from agenteperry.tdr.chunking import chunk_pages
from agenteperry.tdr.dossier import generate_dossier, render_dossier_markdown
from agenteperry.tdr.downloader import (
    audit_pdf_usability,
    download_tdr_batch,
    inspect_pdf_text_layer,
)
from agenteperry.tdr.embeddings import build_embedding_inputs
from agenteperry.tdr.flags import detect_flags_in_pages
from agenteperry.tdr.index import TDR_COMMANDS, TDR_DIRECTORIES, TDR_RULES
from agenteperry.tdr.ingestion import calculate_sha256, load_manual_manifest, sync_to_db
from agenteperry.tdr.models import TdrChunk, TdrPage
from agenteperry.tdr.parsing import extract_pdf_pages
from agenteperry.tdr.search import search_chunks

console = Console()


@click.group()
@click.version_option()
def main() -> None:
    """AgentePerry: scanner preventivo de Terminos de Referencia."""
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


main.add_command(radar_group)
main.add_command(ocr_group)


@main.group("tdr")
def tdr_group() -> None:
    """Pipeline TDR: ingest, parse, chunk, embed, flag and search."""


@tdr_group.command("index")
def tdr_index() -> None:
    """Show the current MVP structure and available commands."""
    dirs = Table(title="AgentePerry TDR package index")
    dirs.add_column("Path")
    dirs.add_column("Purpose")
    for path, purpose in TDR_DIRECTORIES:
        dirs.add_row(path, purpose)
    console.print(dirs)

    commands = Table(title="TDR commands")
    commands.add_column("Command")
    commands.add_column("Purpose")
    for command, purpose in TDR_COMMANDS:
        commands.add_row(command, purpose)
    console.print(commands)

    rules = Table(title="MVP rule-based signals")
    rules.add_column("Rule")
    rules.add_column("Flag")
    for rule_id, flag_code in TDR_RULES:
        rules.add_row(rule_id, flag_code)
    console.print(rules)


@tdr_group.command("load-manual")
@click.argument("manifest", type=click.Path(exists=True, path_type=Path))
@click.option("--sync", is_flag=True, help="Persist records to database.")
def tdr_load_manual(manifest: Path, sync: bool) -> None:
    """Validate and summarize a manual TDR CSV manifest."""
    records = load_manual_manifest(manifest)
    table = Table(title=f"Manual TDR manifest: {manifest}")
    table.add_column("External ID")
    table.add_column("Title")
    table.add_column("File")
    table.add_column("SHA256")
    table.add_column("Exists")

    for record in records:
        local_path = record.local_path
        exists = bool(local_path and local_path.exists())
        checksum = calculate_sha256(local_path)[:12] if local_path and exists else "missing"
        table.add_row(
            record.external_id or "-", record.title, str(local_path), checksum, "yes" if exists else "no"
        )
    console.print(table)

    if sync:
        count = sync_to_db(records)
        console.print(f"[green]OK[/] upserted {count} records to database")


@tdr_group.command("parse")
@click.argument("pdf", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
def tdr_parse(pdf: Path, output_path: Path | None) -> None:
    """Extract clean text page-by-page from a PDF."""
    pages = extract_pdf_pages(pdf)
    payload = {"source_pdf": str(pdf), "pages": [page.model_dump(mode="json") for page in pages]}
    _write_json_or_print(payload, output_path)
    console.print(f"[green]OK[/] extracted {len(pages)} pages")


@tdr_group.command("chunk")
@click.argument("pages_json", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
@click.option("--max-chars", type=int, default=1200, show_default=True)
@click.option("--overlap-chars", type=int, default=160, show_default=True)
def tdr_chunk(pages_json: Path, output_path: Path | None, max_chars: int, overlap_chars: int) -> None:
    """Create searchable chunks from parsed pages."""
    pages = _load_pages(pages_json)
    chunks = chunk_pages(pages, max_chars=max_chars, overlap_chars=overlap_chars)
    payload = {"source_pages": str(pages_json), "chunks": [chunk.model_dump(mode="json") for chunk in chunks]}
    _write_json_or_print(payload, output_path)
    console.print(f"[green]OK[/] created {len(chunks)} chunks")


@tdr_group.command("embed-inputs")
@click.argument("chunks_json", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
def tdr_embed_inputs(chunks_json: Path, output_path: Path | None) -> None:
    """Prepare provider-ready embedding payloads without calling an API."""
    chunks = _load_chunks(chunks_json)
    inputs = build_embedding_inputs(chunks)
    payload = {"source_chunks": str(chunks_json), "embedding_inputs": [item.model_dump(mode="json") for item in inputs]}
    _write_json_or_print(payload, output_path)
    console.print(f"[green]OK[/] prepared {len(inputs)} embedding inputs")


@tdr_group.command("flags")
@click.argument("pages_json", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
def tdr_flags(pages_json: Path, output_path: Path | None) -> None:
    """Detect rule-based TDR signals with direct evidence."""
    pages = _load_pages(pages_json)
    flags = detect_flags_in_pages(pages)
    payload = {"source_pages": str(pages_json), "flags": [flag.model_dump(mode="json") for flag in flags]}
    _write_json_or_print(payload, output_path)
    console.print(f"[green]OK[/] detected {len(flags)} flags")


@tdr_group.command("smoke-search")
@click.argument("chunks_json", type=click.Path(exists=True, path_type=Path))
@click.argument("query")
@click.option("--limit", type=int, default=10, show_default=True)
def tdr_smoke_search(chunks_json: Path, query: str, limit: int) -> None:
    """Run a local lexical smoke-search over chunk JSON."""
    chunks = _load_chunks(chunks_json)
    matches = search_chunks(chunks, query, limit=limit)
    table = Table(title=f"Smoke search: {query}")
    table.add_column("Chunk")
    table.add_column("Page")
    table.add_column("Excerpt")
    for chunk in matches:
        table.add_row(str(chunk.chunk_index), str(chunk.page_start), chunk.text[:180])
    console.print(table)


@tdr_group.command("load-pipeline")
@click.argument("manifest_jsonl", type=click.Path(exists=True, path_type=Path))
@click.option("--pages", "pages_json", type=click.Path(path_type=Path), default=None)
@click.option("--chunks", "chunks_json", type=click.Path(path_type=Path), default=None)
@click.option("--flags", "flags_json", type=click.Path(path_type=Path), default=None)
@click.option("--embeddings", "embeddings_json", type=click.Path(path_type=Path), default=None)
def tdr_load_pipeline(
    manifest_jsonl: Path,
    pages_json: Path | None,
    chunks_json: Path | None,
    flags_json: Path | None,
    embeddings_json: Path | None,
) -> None:
    """Load TDR pipeline JSON output into Supabase (pages, chunks, embeddings, flags)."""
    from agenteperry.tdr.loader import load_pipeline_json

    counts = load_pipeline_json(
        manifest_jsonl,
        pages_json=pages_json,
        chunks_json=chunks_json,
        flags_json=flags_json,
        embeddings_json=embeddings_json,
    )
    table = Table(title="Pipeline load results")
    table.add_column("Table")
    table.add_column("Rows upserted")
    for table_name, count in counts.items():
        table.add_row(table_name, str(count))
    console.print(table)


@tdr_group.command("download")
@click.option("--input", "input_jsonl", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--sector", type=click.Choice(["salud", "ambiente"]), required=True)
@click.option("--limit", type=int, default=5, show_default=True)
@click.option("--max-docs", "max_docs_per_contract", type=int, default=1, show_default=True)
@click.option("--timeout", type=int, default=30, show_default=True)
@click.option("--retries", type=int, default=3, show_default=True)
@click.option("--dry-run", is_flag=True)
@click.option("--pdf-only", is_flag=True, help="Only consider documents whose OCDS format is PDF.")
@click.option("--skip-existing", is_flag=True, help="Skip candidate files already present on disk.")
@click.option("--audit-after-download", is_flag=True, help="Refresh data/scraped/tdrs PDF usability audit after the batch.")
@click.option("--stop-when-usable", type=int, default=0, show_default=True, help="Stop after N usable PDFs are found.")
def tdr_download(
    input_jsonl: Path,
    sector: str,
    limit: int,
    max_docs_per_contract: int,
    timeout: int,
    retries: int,
    dry_run: bool,
    pdf_only: bool,
    skip_existing: bool,
    audit_after_download: bool,
    stop_when_usable: int,
) -> None:
    """Download TDR/Bases documents from filtered OCDS contracts."""
    sector_norm = "ambiente_mineria" if sector == "ambiente" else "salud"
    payload = download_tdr_batch(
        input_jsonl=input_jsonl,
        sector=sector_norm,
        limit=limit,
        max_docs_per_contract=max_docs_per_contract,
        timeout=timeout,
        retries=retries,
        dry_run=dry_run,
        pdf_only=pdf_only,
        skip_existing=skip_existing,
        audit_after_download=audit_after_download,
        stop_when_usable=stop_when_usable,
    )

    audit = cast(Mapping[str, Any], payload["audit"])
    table = Table(title=f"TDR download audit: {sector_norm}")
    table.add_column("Metric")
    table.add_column("Value")
    for key in [
        "total_contracts_seen",
        "documents_candidates",
        "documents_selected",
        "downloaded",
        "failed",
        "unsupported_format",
        "skipped_no_documents",
        "avg_docs_per_contract",
        "total_candidates_considered",
        "attempted_downloads",
        "usable_found",
        "first_usable_path",
        "needs_ocr_count",
        "failed_count",
        "skipped_existing",
        "stopped_early",
    ]:
        table.add_row(key, str(audit.get(key)))
    table.add_row("audit_path", str(payload["audit_path"]))
    console.print(table)


@tdr_group.command("audit-pdfs")
@click.option("--base", "base_dir", type=click.Path(exists=True, file_okay=False, path_type=Path), required=True)
def tdr_audit_pdfs(base_dir: Path) -> None:
    """Audit downloaded PDFs for usable digital text layers."""
    audit = audit_pdf_usability(base_dir)
    table = Table(title="PDF usability audit")
    table.add_column("Metric")
    table.add_column("Value")
    for key in [
        "total_files",
        "pdf_files",
        "pdf_available",
        "pdf_partial",
        "pdf_needs_ocr",
        "archives_pending",
        "report_path",
        "audit_path",
    ]:
        table.add_row(key, str(audit.get(key)))
    console.print(table)


@tdr_group.command("analyze")
@click.argument("pdf", type=click.Path(exists=True, path_type=Path))
@click.option("--sector", required=True, help="Sector: salud, ambiente, ambiente_mineria, etc.")
@click.option("--ocid", default=None, help="OCID del proceso (ej. ocds-dgv273-seacev3-988512).")
@click.option("--entity", "entity_name", default=None, help="Nombre de la entidad contratante.")
@click.option("--procedure-code", default=None, help="Codigo del procedimiento de contratacion.")
@click.option("--monto", type=float, default=None, help="Monto del contrato en soles.")
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(path_type=Path),
    default=Path("data/results"),
    show_default=True,
    help="Directorio base de salida.",
)
@click.option("--max-chars", type=int, default=1200, show_default=True)
@click.option("--overlap-chars", type=int, default=160, show_default=True)
def tdr_analyze(
    pdf: Path,
    sector: str,
    ocid: str | None,
    entity_name: str | None,
    procedure_code: str | None,
    monto: float | None,
    out_dir: Path,
    max_chars: int,
    overlap_chars: int,
) -> None:
    """Full TDR pipeline on a single PDF: verify → parse → chunk → flags → dossier.

    Outputs pages.json, chunks.json, flags.json, dossier.json, dossier.md
    under --out-dir/<slug>/.  No database required.

    Example:
        agenteperry tdr analyze data/scraped/tdrs/salud/pliego.pdf \\
          --sector salud --ocid ocds-dgv273-seacev3-988512 \\
          --entity "SEGURO SOCIAL DE SALUD" --monto 195383235.96
    """
    import re

    pdf = pdf.resolve()
    ocid_str = ocid or pdf.stem
    slug = re.sub(r"[^a-z0-9]+", "_", ocid_str.lower()).strip("_")[:60]
    result_dir = out_dir / slug
    result_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------
    # Step 1: Verify text layer
    # -------------------------------------------------------------------
    console.print(f"[bold cyan]Step 1:[/] Verificar capa de texto — {pdf.name}")
    usability = inspect_pdf_text_layer(pdf)
    if not usability["is_usable"]:
        raise click.ClickException(
            f"PDF no tiene capa de texto usable: status={usability['tdr_status']} "
            f"coverage={usability['coverage_pct']}%. No se usa OCR en este MVP."
        )
    total_pages: int = usability["total_pages"]
    coverage_pct: float = usability["coverage_pct"]
    console.print(
        f"  OK — {total_pages} paginas, {coverage_pct}% coverage, status={usability['tdr_status']}"
    )

    # -------------------------------------------------------------------
    # Step 2: Extract pages
    # -------------------------------------------------------------------
    console.print("[bold cyan]Step 2:[/] Extraer paginas con PyMuPDF")
    pages = extract_pdf_pages(pdf, tdr_id=ocid_str)
    pages_payload = {
        "source_pdf": str(pdf),
        "ocid": ocid_str,
        "pages": [page.model_dump(mode="json") for page in pages],
    }
    pages_path = result_dir / "pages.json"
    pages_path.write_text(json.dumps(pages_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"  OK — {len(pages)} paginas extraidas → {pages_path}")

    # -------------------------------------------------------------------
    # Step 3: Chunk pages
    # -------------------------------------------------------------------
    console.print("[bold cyan]Step 3:[/] Crear chunks")
    chunks = chunk_pages(pages, max_chars=max_chars, overlap_chars=overlap_chars)
    chunks_payload = {
        "source_pages": str(pages_path),
        "ocid": ocid_str,
        "chunks": [chunk.model_dump(mode="json") for chunk in chunks],
    }
    chunks_path = result_dir / "chunks.json"
    chunks_path.write_text(json.dumps(chunks_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"  OK — {len(chunks)} chunks creados → {chunks_path}")

    # -------------------------------------------------------------------
    # Step 4: Detect flags
    # -------------------------------------------------------------------
    console.print("[bold cyan]Step 4:[/] Detectar flags")
    flags = detect_flags_in_pages(pages)
    flags_payload = {
        "source_pages": str(pages_path),
        "ocid": ocid_str,
        "flags": [flag.model_dump(mode="json") for flag in flags],
    }
    flags_path = result_dir / "flags.json"
    flags_path.write_text(json.dumps(flags_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if flags:
        console.print(f"  OK — {len(flags)} flags detectados → {flags_path}")
    else:
        console.print(f"  OK — 0 flags (ninguna regla activo en este documento) → {flags_path}")

    # -------------------------------------------------------------------
    # Step 5: Generate dossier
    # -------------------------------------------------------------------
    console.print("[bold cyan]Step 5:[/] Generar dossier legal-safe")
    dossier = generate_dossier(
        pdf_path=pdf,
        sector=sector,
        ocid=ocid_str,
        entity_name=entity_name,
        procedure_code=procedure_code,
        monto=monto,
        coverage_pct=coverage_pct,
        total_pages=total_pages,
        pages=pages,
        chunks=chunks,
        flags=flags,
    )
    dossier_json_path = result_dir / "dossier.json"
    dossier_json_path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"  OK — dossier JSON → {dossier_json_path}")

    md = render_dossier_markdown(dossier)
    dossier_md_path = result_dir / "dossier.md"
    dossier_md_path.write_text(md, encoding="utf-8")
    console.print(f"  OK — dossier Markdown → {dossier_md_path}")

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    risk = dossier["risk_summary"]
    console.print("")
    table = Table(title=f"Resultado: {ocid_str}")
    table.add_column("Metrica")
    table.add_column("Valor")
    table.add_row("Sector", sector)
    table.add_row("Entidad", entity_name or "Sin dato")
    table.add_row("Paginas", str(total_pages))
    table.add_row("Coverage", f"{coverage_pct}%")
    table.add_row("Chunks", str(len(chunks)))
    table.add_row("Flags totales", str(risk["total_flags"]))
    table.add_row("  HIGH", str(risk["high_flags"]))
    table.add_row("  MEDIUM", str(risk["medium_flags"]))
    table.add_row("  LOW", str(risk["low_flags"]))
    table.add_row("Score acumulado", str(risk["total_score"]))
    table.add_row("Nivel de riesgo", risk["risk_level"])
    table.add_row("Resultado dir", str(result_dir))
    console.print(table)


@main.group("cdc")
def cdc_group() -> None:
    """Change Data Capture: detect new/modified contracts and run TDR pipeline."""


@cdc_group.command("run")
@click.option(
    "--input", "input_jsonl",
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help="JSONL file with OCDS contracts (e.g. data/filtered/salud_2024_2025_with_documents.jsonl).",
)
@click.option(
    "--sector",
    type=click.Choice(["salud", "ambiente", "todos"]),
    default="todos",
    show_default=True,
    help="Filter by sector. 'todos' processes all priority sectors.",
)
@click.option("--limit", type=int, default=50, show_default=True,
              help="Max contracts to process after change detection.")
@click.option("--dry-run", is_flag=True,
              help="Detect and report changes but do not download or analyze.")
@click.option(
    "--hash-db",
    "hash_db_path",
    type=click.Path(path_type=Path),
    default=Path("data/cdc/hashes.json"),
    show_default=True,
    help="Path to the persistent hash registry JSON file.",
)
@click.option(
    "--out-dir",
    "out_dir",
    type=click.Path(path_type=Path),
    default=Path("data/results"),
    show_default=True,
    help="Base directory for generated dossiers.",
)
@click.option("--pdf-only", is_flag=True, default=True, show_default=True,
              help="Only download PDF documents (skip RAR/ZIP).")
@click.option("--rate-limit", type=float, default=1.0, show_default=True,
              help="Seconds to wait between downloads.")
@click.option("--ocr-fallback/--no-ocr-fallback", default=False, show_default=True,
              help="If PDF has no digital text layer, run OCR fallback before analysis.")
@click.option("--ocr-workers", type=int, default=2, show_default=True,
              help="Concurrent OCR workers per PDF when OCR fallback is enabled.")
@click.option(
    "--ocr-out-dir",
    "ocr_out_dir",
    type=click.Path(path_type=Path),
    default=Path("data/ocr"),
    show_default=True,
    help="Base directory for OCR intermediate outputs.",
)
def cdc_run(
    input_jsonl: Path,
    sector: str,
    limit: int,
    dry_run: bool,
    hash_db_path: Path,
    out_dir: Path,
    pdf_only: bool,
    rate_limit: float,
    ocr_fallback: bool,
    ocr_workers: int,
    ocr_out_dir: Path,
) -> None:
    """Run the CDC pipeline: detect changes → download TDRs → analyze → dossier.

    Examples:

    \\b
      # First pass: see all contracts, no downloads
      agenteperry cdc run --input data/filtered/salud_2024_2025_with_documents.jsonl --sector salud --dry-run

      # Process up to 5 new salud contracts
      agenteperry cdc run --input data/filtered/salud_2024_2025_with_documents.jsonl --sector salud --limit 5
    """
    sector_filter: str | None = None if sector == "todos" else sector

    # ------------------------------------------------------------------
    # Load records
    # ------------------------------------------------------------------
    console.print(f"[bold cyan]CDC Run[/] — input: [blue]{input_jsonl.name}[/]")
    records = _load_jsonl(input_jsonl)
    console.print(f"  Cargados [green]{len(records):,}[/] registros OCDS")

    # ------------------------------------------------------------------
    # Detect changes
    # ------------------------------------------------------------------
    detector = SEACEChangeDetector(hash_file=hash_db_path)
    console.print(
        f"  Hash DB: [blue]{hash_db_path}[/] "
        f"([yellow]{detector.total_known:,}[/] hashes conocidos)"
    )

    # Pre-scan all records for summary stats
    total = len(records)
    new_count = 0
    mod_count = 0
    priority_sector_count = 0
    sector_breakdown: dict[str, int] = {}

    for rec in records:
        ocid = str(rec.get("ocid") or "")
        current_hash = compute_record_hash(rec)
        prev = detector.get_known_hash(ocid)
        if prev is None:
            new_count += 1
        elif prev != current_hash:
            mod_count += 1

        if is_priority(rec):
            s = detect_sector(rec)
            priority_sector_count += 1
            sector_breakdown[s] = sector_breakdown.get(s, 0) + 1

    unchanged = total - new_count - mod_count
    console.print("")
    console.print(f"[bold]Resumen de cambios detectados en {total:,} registros:[/]")
    console.print(f"  [green]✅ {new_count:,} contratos NUEVOS[/]")
    if mod_count:
        console.print(f"  [yellow]✏️  {mod_count:,} contratos MODIFICADOS[/]")
    console.print(f"  [dim]⏭️  {unchanged:,} sin cambios — ignorados[/]")
    console.print(f"  [magenta]🎯 {priority_sector_count:,} contratos de sectores prioritarios[/]")
    for s, n in sorted(sector_breakdown.items()):
        filter_flag = " ← filtrado" if sector_filter and s == sector_filter else ""
        console.print(f"       {s}: {n:,}{filter_flag}")

    if dry_run:
        console.print("")
        console.print("[yellow]--dry-run: no se descarga ni analiza nada.[/]")
        if sector_filter:
            relevant = [r for r in records if detect_sector(r) == sector_filter and is_priority(r)]
        else:
            relevant = [r for r in records if is_priority(r)]
        shown = relevant[:limit]

        if shown:
            tbl = Table(title=f"Contratos prioritarios (top {len(shown)} de {len(relevant)})")
            tbl.add_column("OCID")
            tbl.add_column("Entidad")
            tbl.add_column("Monto (S/)")
            tbl.add_column("Sector")
            tbl.add_column("Docs")
            tbl.add_column("Estado")
            for rec in shown:
                ocid = str(rec.get("ocid") or "")
                entity = str(rec.get("entity") or rec.get("entity_name") or "—")[:40]
                monto_raw = rec.get("monto") or rec.get("amount")
                monto_str = f"{float(monto_raw):,.0f}" if monto_raw else "—"
                s = detect_sector(rec)
                docs: list[Any] = rec.get("documents") or []
                doc_count = len(docs)
                prev_hash = detector.get_known_hash(ocid)
                estado = "[green]new[/]" if prev_hash is None else "[yellow]modified[/]"
                tbl.add_row(ocid[-20:], entity, monto_str, s, str(doc_count), estado)
            console.print(tbl)
        else:
            console.print("[yellow]No hay contratos prioritarios en el input dado el filtro actual.[/]")
        return

    # ------------------------------------------------------------------
    # Full pipeline
    # ------------------------------------------------------------------
    console.print("")
    pipeline = CDCPipeline(
        sector_filter=sector_filter,
        limit=limit,
        dry_run=False,
        output_dir=out_dir,
        rate_limit_seconds=rate_limit,
        pdf_only=pdf_only,
        enable_ocr_fallback=ocr_fallback,
        ocr_output_dir=ocr_out_dir,
        ocr_workers=ocr_workers,
    )

    import time as _time
    t0 = _time.monotonic()
    stats, results = pipeline.run(records, detector)
    elapsed = _time.monotonic() - t0

    # ------------------------------------------------------------------
    # Results table
    # ------------------------------------------------------------------
    console.print("")
    if results:
        res_tbl = Table(title="Contratos procesados")
        res_tbl.add_column("OCID")
        res_tbl.add_column("Entidad")
        res_tbl.add_column("Estado")
        res_tbl.add_column("Pp")
        res_tbl.add_column("Chunks")
        res_tbl.add_column("Flags")
        res_tbl.add_column("Riesgo")
        for r in results:
            status_icon = {
                STATUS_DOSSIER_GENERATED: "[green]✅ dossier[/]",
                STATUS_NO_FLAGS: "[blue]0 flags[/]",
                STATUS_NEEDS_OCR: "[yellow]⚠ needs_ocr[/]",
                STATUS_NOT_PDF: "[dim]📁 archive[/]",
                STATUS_NO_TDR: "[dim]— no_tdr[/]",
                "download_error": "[red]✖ error[/]",
            }.get(r.status, r.status)
            res_tbl.add_row(
                r.ocid[-24:],
                r.entity_name[:32],
                status_icon,
                str(r.pages) if r.pages else "—",
                str(r.chunks) if r.chunks else "—",
                str(r.flags) if r.flags else "—",
                r.risk_level if r.risk_level != "SIN_SENALES" else "—",
            )
        console.print(res_tbl)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    summary = Table(title="Resumen del run CDC")
    summary.add_column("Métrica")
    summary.add_column("Valor")
    summary.add_row("Total evaluados", f"{stats.total_evaluated:,}")
    summary.add_row("Contratos nuevos", f"{stats.new_contracts:,}")
    summary.add_row("Contratos modificados", f"{stats.modified_contracts:,}")
    summary.add_row("Sin cambios (ignorados)", f"{stats.skipped_no_change:,}")
    summary.add_row("Prioritarios procesados", f"{stats.priority_contracts:,}")
    summary.add_row("TDRs con URL", f"{stats.tdrs_url_found:,}")
    summary.add_row("TDRs sin URL", f"{stats.tdrs_url_not_found:,}")
    summary.add_row("TDRs descargados", f"{stats.tdrs_downloaded:,}")
    summary.add_row("TDRs con texto (available)", f"{stats.tdrs_available:,}")
    summary.add_row("TDRs escaneados (needs_ocr)", f"{stats.tdrs_needs_ocr:,}")
    summary.add_row("TDRs procesados con OCR", f"{stats.tdrs_processed_with_ocr:,}")
    summary.add_row("Dossiers generados", f"[green]{stats.dossiers_generated:,}[/]")
    summary.add_row("  con flags", f"{stats.dossiers_with_flags:,}")
    summary.add_row("  sin flags (0 señales)", f"{stats.dossiers_no_flags:,}")
    summary.add_row("Tiempo total", f"{elapsed:.1f}s")
    console.print(summary)

    # Save audit json
    audit_dir = hash_db_path.parent
    audit_dir.mkdir(parents=True, exist_ok=True)
    audit_path = audit_dir / f"audit_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.json"
    audit_path.write_text(
        json.dumps(stats.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    console.print(f"  Audit guardado en [blue]{audit_path}[/]")

    # Print dossiers generated
    generated = [r for r in results if r.status == STATUS_DOSSIER_GENERATED]
    if generated:
        console.print("")
        console.print("[bold green]Dossiers generados:[/]")
        for r in generated:
            console.print(f"  → {r.dossier_path}")


@cdc_group.command("status")
@click.option(
    "--hash-db",
    "hash_db_path",
    type=click.Path(path_type=Path),
    default=Path("data/cdc/hashes.json"),
    show_default=True,
)
def cdc_status(hash_db_path: Path) -> None:
    """Show the current state of the CDC hash registry."""
    detector = SEACEChangeDetector(hash_file=hash_db_path)
    tbl = Table(title="CDC Hash Registry Status")
    tbl.add_column("Campo")
    tbl.add_column("Valor")
    tbl.add_row("Hash DB path", str(hash_db_path))
    tbl.add_row("Existe", "Sí" if hash_db_path.exists() else "No")
    tbl.add_row("Contratos conocidos", f"{detector.total_known:,}")
    if hash_db_path.exists():
        size_kb = hash_db_path.stat().st_size / 1024
        tbl.add_row("Tamaño del archivo", f"{size_kb:.1f} KB")
    console.print(tbl)


@cdc_group.command("reset")
@click.option(
    "--hash-db",
    "hash_db_path",
    type=click.Path(path_type=Path),
    default=Path("data/cdc/hashes.json"),
    show_default=True,
)
@click.confirmation_option(prompt="¿Seguro? Esto borrará todos los hashes conocidos.")
def cdc_reset(hash_db_path: Path) -> None:
    """Reset the hash registry (next run will treat all records as new)."""
    detector = SEACEChangeDetector(hash_file=hash_db_path)
    old_count = detector.total_known
    detector.reset()
    console.print(f"[yellow]Hash registry reseteado.[/] {old_count:,} hashes eliminados.")


@main.group("sources")
def sources_group() -> None:
    """Source registry and catalog commands."""


def _collector_status(source_code: str) -> tuple[str, bool]:
    """Return (emoji, is_implemented) for a source code."""
    try:
        registry = build_default_registry()
        source = registry.get(source_code)
        if source is None:
            return "❌", False
        build_collector(source)
        return "✅", True
    except NotImplementedError:
        return "⏳", False
    except Exception:
        return "⚠️", False


@sources_group.command("list")
@click.option("--priority", type=click.Choice(["P0", "P1", "P2", "P3"]), default=None)
@click.option("--status", type=click.Choice(["planned", "active", "paused", "deprecated"]), default=None)
@click.option("--implemented/--all", "implemented_only", default=False, help="Show only sources with implemented collectors.")
def sources_list(priority: str | None, status: str | None, implemented_only: bool) -> None:
    """List all registered data sources."""
    registry = build_default_registry()
    sources = registry.list_all()
    if priority:
        sources = [s for s in sources if s.priority == priority]
    if status:
        sources = [s for s in sources if s.status == status]

    table = Table(title="Data Sources")
    table.add_column("Impl")
    table.add_column("Code")
    table.add_column("Name")
    table.add_column("Type")
    table.add_column("Priority")
    table.add_column("Status")
    table.add_column("Owner")
    for s in sources:
        status_icon, is_impl = _collector_status(s.source_code)
        if implemented_only and not is_impl:
            continue
        table.add_row(
            status_icon,
            s.source_code,
            s.source_name,
            s.source_type.value,
            s.priority.value,
            s.status.value,
            s.owner or "-",
        )
    console.print(table)


@sources_group.command("show")
@click.argument("source_code")
def sources_show(source_code: str) -> None:
    """Show details of a specific source."""
    registry = build_default_registry()
    source = registry.get(source_code)
    if not source:
        console.print(f"[red]Source not found:[/] {source_code}")
        return
    console.print(f"[bold]{source.source_name}[/]")
    console.print(f"  Code: {source.source_code}")
    console.print(f"  URL: {source.source_url}")
    console.print(f"  Type: {source.source_type.value}")
    console.print(f"  Priority: {source.priority.value}")
    console.print(f"  Status: {source.status.value}")
    console.print(f"  Owner: {source.owner}")
    console.print(f"  Method: {source.method_notes}")
    if source.fields:
        console.print(f"  Fields: {', '.join(source.fields)}")
    if source.red_flags:
        console.print(f"  Red Flags: {', '.join(source.red_flags)}")


@sources_group.command("collect")
@click.argument("source_code")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--download-url", default=None, help="Direct public file URL for bulk sources.")
@click.option(
    "--download-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw"),
    show_default=True,
)
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
@click.option("--limit", type=int, default=None, help="Limit records for smoke tests.")
@click.option("--category", default=None, help="OECE/SEACE category, e.g. procedimientos.")
@click.option("--year", type=int, default=None, help="Dataset year when available.")
@click.option("--format", "file_format", default="csv", help="Expected download format: csv or xlsx.")
@click.option("--query", default=None, help="CKAN search query for CKAN sources.")
@click.option("--rows", type=int, default=50, show_default=True, help="CKAN row count.")
def sources_collect(
    source_code: str,
    input_path: Path | None,
    download_url: str | None,
    download_dir: Path,
    output_path: Path | None,
    limit: int | None,
    category: str | None,
    year: int | None,
    file_format: str,
    query: str | None,
    rows: int,
) -> None:
    """Collect a supported source and emit source_records-compatible JSONL."""
    registry = build_default_registry()
    source = registry.get(source_code)
    if not source:
        raise click.ClickException(f"Source not found: {source_code}")
    try:
        collector = build_collector(source)
    except NotImplementedError as exc:
        raise click.ClickException(str(exc)) from exc

    try:
        results = collector.collect(
            input_path=input_path,
            download_url=download_url,
            download_dir=download_dir,
            limit=limit,
            category=category,
            year=year,
            file_format=file_format,
            query=query,
            rows=rows,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    records = [result.to_record() for result in results]
    _write_jsonl_or_print(records, output_path)
    console.print(f"[green]OK[/] collected {len(records)} records from {source_code}")


@sources_group.command("pipeline")
@click.argument("source_code")
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), default=None, help="Local input file instead of downloading.")
@click.option("--download-dir", type=click.Path(path_type=Path), default=Path("data/raw"), show_default=True)
@click.option("--limit", type=int, default=None, help="Limit records (use for smoke tests).")
@click.option("--category", default=None, help="OECE/SEACE category.")
@click.option("--year", type=int, default=None, help="Dataset year.")
@click.option("--batch-size", type=int, default=500, show_default=True)
@click.option("--skip-chunks", is_flag=True, default=False, help="Skip document_chunks step.")
@click.option("--download-url", default=None)
def sources_pipeline(
    source_code: str,
    input_path: Path | None,
    download_dir: Path,
    limit: int | None,
    category: str | None,
    year: int | None,
    batch_size: int,
    skip_chunks: bool,
    download_url: str | None,
) -> None:
    """Run the complete source pipeline: collect → sync → map → sync-graph → chunk.

    This is the primary command to ingest a new data source into the graph.

    Example:
        agenteperry sources pipeline ocds_peru --limit 100
        agenteperry sources pipeline sunat_padron
        agenteperry sources pipeline contraloria_sanciones
    """
    from agenteperry.sync.loader import upsert_entities, upsert_relationships, upsert_source_records

    registry = build_default_registry()
    source = registry.get(source_code)
    if not source:
        raise click.ClickException(f"Source not found: {source_code}")
    try:
        collector = build_collector(source)
    except NotImplementedError as exc:
        raise click.ClickException(str(exc)) from exc

    # Step 1: Collect
    console.print(f"[bold cyan]Step 1: Collect[/] {source_code}")
    try:
        results = collector.collect(
            input_path=input_path,
            download_url=download_url,
            download_dir=download_dir,
            limit=limit,
            category=category,
            year=year,
        )
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Collection failed: {exc}") from exc
    records = [result.to_record() for result in results]
    console.print(f"  Collected [green]{len(records)}[/] records")

    if not records:
        console.print("[yellow]No records collected — stopping.[/]")
        return

    # Save records JSONL
    records_path = download_dir / source_code / "records.jsonl"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    _write_jsonl_or_print(records, records_path)
    console.print(f"  Saved to [blue]{records_path}[/]")

    # Step 2: Upsert source_records
    console.print("[bold cyan]Step 2: Sync to source_records[/]")
    try:
        count_records = upsert_source_records(records_path, batch_size=batch_size)
    except Exception as exc:
        raise click.ClickException(f"DB sync failed: {exc}") from exc
    console.print(f"  Upserted [green]{count_records}[/] source_records")

    # Step 3: Map to graph
    console.print("[bold cyan]Step 3: Map to graph[/]")
    mapped = map_records_to_graph(records)
    console.print(f"  {len(mapped.entities)} entities, {len(mapped.relationships)} relationships")

    if mapped.entities or mapped.relationships:
        graph_path = download_dir / source_code / "graph.json"
        payload = mapped.model_dump(mode="json")
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"  Saved graph to [blue]{graph_path}[/]")

        # Step 4: Upsert entities and relationships
        console.print("[bold cyan]Step 4: Sync graph to source_entities + source_relationships[/]")
        try:
            count_entities = upsert_entities(graph_path, batch_size=batch_size)
            count_rels = upsert_relationships(graph_path, batch_size=batch_size)
        except Exception as exc:
            raise click.ClickException(f"Graph sync failed: {exc}") from exc
        console.print(f"  Upserted [green]{count_entities}[/] entities, [green]{count_rels}[/] relationships")
    else:
        console.print("  [yellow]No graph entities/relationships to upsert[/]")

    # Step 5: Enrich companies from SUNAT (sunat_padron only)
    enrichment_metrics: dict[str, Any] = {}
    if source_code == "sunat_padron":
        console.print("[bold cyan]Step 5: Enrich companies with SUNAT metadata[/]")
        try:
            from agenteperry.sync.loader import enrich_companies_from_sunat

            enrichment_metrics = enrich_companies_from_sunat(records_path, batch_size=batch_size)
            console.print(f"  Seen [green]{enrichment_metrics.get('companies_seen', 0)}[/] companies")
            console.print(f"  Enriched [green]{enrichment_metrics.get('companies_enriched', 0)}[/] companies")
            if enrichment_metrics.get("companies_unmatched", 0):
                console.print(f"  Unmatched [yellow]{enrichment_metrics['companies_unmatched']}[/] companies")
        except Exception as exc:
            console.print(f"  [yellow]Enrichment skipped: {exc}[/]")

    # Step 6: Build document_chunks (for contract-like records)
    count_chunks = 0
    if not skip_chunks and source_code in {"ocds_peru", "seace_oece"}:
        console.print("[bold cyan]Step 6: Build document_chunks[/]")
        from agenteperry.sync.chunks import upsert_contract_chunks

        try:
            count_chunks = upsert_contract_chunks(source_code=source_code, limit=limit, batch_size=batch_size)
        except Exception as exc:
            console.print(f"  [yellow]Chunks skipped (DB may be unavailable): {exc}[/]")
        else:
            console.print(f"  Upserted [green]{count_chunks}[/] document_chunks")

    # Step 7: Generate audit
    console.print("[bold cyan]Step 7: Generate audit[/]")
    if source_code == "sunat_padron":
        audit = _build_sunat_audit(
            records=records,
            entities=list(mapped.entities) if mapped else [],
            relationships=list(mapped.relationships) if mapped else [],
            enrichment_metrics=enrichment_metrics,
        )
    else:
        audit = _build_audit(
            records=records,
            entities=list(mapped.entities) if mapped else [],
            relationships=list(mapped.relationships) if mapped else [],
            chunks_count=count_chunks,
        )
        audit["relationships_upserted_unique"] = _count_db_relationships() if mapped else 0
    audit_path = download_dir / source_code / "audit.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    console.print(f"  Saved to [blue]{audit_path}[/]")

    console.print(f"[bold green]✓ Pipeline complete for {source_code}[/]")


@main.group("patterns")
def patterns_group() -> None:
    """Detection patterns for conflict of interest."""


@patterns_group.command("list")
def patterns_list() -> None:
    """List all detection patterns."""
    table = Table(title="Detection Patterns")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Severity")
    table.add_column("Score Max")
    table.add_column("Sources")
    for p in list_patterns():
        table.add_row(p.pattern_id, p.name, p.severity, str(p.score_max), ", ".join(p.sources_required))
    console.print(table)


@patterns_group.command("coi-sql")
def patterns_coi_sql() -> None:
    """Print conflict-of-interest detection SQL using graph relationships."""
    console.print("[bold]COI Detection Patterns SQL:[/]")
    for pattern in COI_PATTERNS:
        console.print(f"\n[bold cyan]{pattern.rel_type}[/] (+{pattern.score} pts)")
        console.print(f"  {pattern.explanation}")
        console.print(f"  Evidence: {pattern.evidence}")


@patterns_group.command("show")
@click.argument("pattern_id")
def patterns_show(pattern_id: str) -> None:
    """Show a specific pattern with its SQL query."""
    pattern = get_pattern(pattern_id)
    if not pattern:
        console.print(f"[red]Pattern not found:[/] {pattern_id}")
        return
    console.print(f"[bold]{pattern.name}[/] — {pattern.subtitle}")
    console.print(f"Severity: {pattern.severity}")
    console.print(f"Score Max: {pattern.score_max}")
    console.print(f"Flag Code: {pattern.flag_code}")
    console.print(f"Sources: {', '.join(pattern.sources_required)}")
    console.print(f"\n[bold]Narrative:[/]\n{pattern.narrative}")
    console.print(f"\n[bold]SQL Query:[/]\n{pattern.sql_query}")


@main.group("graph")
def graph_group() -> None:
    """Graph queries and subgraph traversal."""


@graph_group.command("subgraph-sql")
@click.argument("canonical_id")
@click.option("--max-depth", type=int, default=3)
def graph_subgraph_sql(canonical_id: str, max_depth: int) -> None:
    """Print the subgraph SQL for a canonical ID (RUC/DNI)."""
    console.print(f"[bold]Subgraph query for {canonical_id} (depth {max_depth}):[/]")
    console.print(GET_SUBGRAPH_SQL)


@graph_group.command("conflicts-sql")
def graph_conflicts_sql() -> None:
    """Print the conflict of interest detection SQL."""
    console.print("[bold]Conflict of Interest Detection SQL:[/]")
    console.print(FIND_CONFLICTS_SQL)


@graph_group.command("map-records")
@click.argument("records_jsonl", type=click.Path(exists=True, path_type=Path))
@click.option("--out", "output_path", type=click.Path(path_type=Path), default=None)
def graph_map_records(records_jsonl: Path, output_path: Path | None) -> None:
    """Map collected source records JSONL into graph entity/relationship candidates."""
    records = _load_jsonl(records_jsonl)
    mapped = map_records_to_graph(records)
    payload = mapped.model_dump(mode="json")
    _write_json_or_print(payload, output_path)
    console.print(
        f"[green]OK[/] mapped {len(mapped.entities)} entities and "
        f"{len(mapped.relationships)} relationships"
    )


# ---------------------------------------------------------------------------
# Neo4j graph commands — SPEC-0012
# ---------------------------------------------------------------------------


@graph_group.command("neo4j-verify")
def graph_neo4j_verify() -> None:
    """Verify the Neo4j Aura connection (credentials + reachability).

    Example:

    \\b
      agenteperry graph neo4j-verify
    """
    try:
        from agenteperry.graph.neo4j_client import Neo4jClient
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    console.print("[bold]Verificando conexion Neo4j Aura...[/]")
    try:
        with Neo4jClient() as client:
            ok = client.verify_connection()
        if ok:
            console.print("[green]OK[/] Conexion exitosa.")
        else:
            console.print("[red]FAIL[/] La instancia no respondio correctamente.")
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@graph_group.command("neo4j-setup")
def graph_neo4j_setup() -> None:
    """Create Neo4j constraints + indexes (idempotent — safe to run multiple times).

    Example:

    \\b
      agenteperry graph neo4j-setup
    """
    try:
        from agenteperry.graph.neo4j_schema import setup_schema
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    console.print("[bold]Configurando esquema Neo4j...[/]")
    try:
        result = setup_schema()
        console.print(
            f"[green]OK[/] Esquema configurado — "
            f"created={result['created']} skipped={result['skipped']}"
        )
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc


@graph_group.command("neo4j-ingest")
@click.option("--limit", type=int, default=10_000, show_default=True,
              help="Max rows per table (use 200 for smoke test).")
@click.option("--batch-size", type=int, default=500, show_default=True,
              help="UNWIND batch size per Cypher call.")
def graph_neo4j_ingest(limit: int, batch_size: int) -> None:
    """Ingest graph from Postgres into Neo4j (Companies, Contracts, TDRs, Flags).

    Runs setup-schema automatically then ingests all tables in dependency order:
    Nodes first, edges second.  Safe to re-run (all writes use MERGE).

    Examples:

    \\b
      # smoke test — 200 rows per table
      agenteperry graph neo4j-ingest --limit 200

      # full ingestion
      agenteperry graph neo4j-ingest
    """
    try:
        from agenteperry.graph.neo4j_ingestion import GraphIngestion
        from agenteperry.graph.neo4j_schema import setup_schema
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    console.print("[bold]Neo4j Ingestion — Postgres → Aura[/]")

    # Step 0: schema
    console.print("[cyan]Step 0:[/] Schema setup")
    try:
        sr = setup_schema()
        console.print(f"  OK — created={sr['created']} skipped={sr['skipped']}")
    except Exception as exc:
        raise click.ClickException(f"Schema setup failed: {exc}") from exc

    # Step 1: ingest
    console.print(f"[cyan]Step 1:[/] Ingest (limit={limit:,} rows/table)")
    ingestion = GraphIngestion(batch_size=batch_size)
    stats = ingestion.run(limit=limit)

    tbl = Table(title="Ingestion Results")
    tbl.add_column("Entity")
    tbl.add_column("Count", justify="right")
    for key, value in stats.to_dict().items():
        if key == "errors":
            continue
        tbl.add_row(key, f"{value:,}")
    console.print(tbl)

    if stats.errors:
        console.print(f"[yellow]Warnings ({len(stats.errors)}):[/]")
        for err in stats.errors[:5]:
            console.print(f"  {err}")

    if stats.companies == 0 and stats.contracts == 0:
        console.print(
            "[yellow]Sin datos ingresados. "
            "Verifica que DATABASE_URL apunte a la base con datos reales.[/]"
        )
    else:
        console.print("[green]Ingestion completada.[/]")


@graph_group.command("neo4j-inspect")
@click.option("--ruc", required=True, help="RUC de la empresa (11 digitos).")
def graph_neo4j_inspect(ruc: str) -> None:
    """Inspect a company: its risk flags, contracts, and business community.

    Example:

    \\b
      agenteperry graph neo4j-inspect --ruc 20605681281
    """
    try:
        from agenteperry.graph.neo4j_queries import InvestigativeQueries
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    with InvestigativeQueries() as q:
        # Flags
        flags_result = q.find_flags_for_company(ruc)
        if flags_result and flags_result.flag_count > 0:
            console.print(
                f"\n[bold red]🚩 {flags_result.company_name}[/] (RUC: {ruc})"
            )
            console.print(
                f"   {flags_result.flag_count} senales de riesgo documentadas "
                f"({flags_result.high_count} HIGH):"
            )
            flag_tbl = Table(show_header=True)
            flag_tbl.add_column("Codigo")
            flag_tbl.add_column("Severidad")
            flag_tbl.add_column("OCID")
            flag_tbl.add_column("Monto (S/)")
            flag_tbl.add_column("Pagina")
            for f in flags_result.flags[:20]:
                flag_tbl.add_row(
                    f.flag_code,
                    f.severity,
                    (f.ocid or "")[-20:],
                    f"{f.contract_amount:,.0f}" if f.contract_amount else "—",
                    str(f.page_number) if f.page_number else "—",
                )
            console.print(flag_tbl)
            # Show evidence_quote for first flag
            first_with_quote = next(
                (f for f in flags_result.flags if f.evidence_quote), None
            )
            if first_with_quote:
                evidence_quote = first_with_quote.evidence_quote or ""
                console.print(
                    f"\n  [italic]Evidencia (pag. {first_with_quote.page_number}):[/] "
                    f'"{evidence_quote[:200]}"'
                )
        elif flags_result:
            console.print(
                f"\n[green]{flags_result.company_name}[/] (RUC: {ruc}) — "
                "sin senales de riesgo en el grafo actual."
            )
        else:
            console.print(f"[yellow]Empresa RUC {ruc} no encontrada en el grafo.[/]")

        # Community
        community = q.find_community_around_company(ruc)
        if community.community_size > 0:
            console.print(
                f"\n[bold]Red empresarial:[/] "
                f"{community.community_size} empresa(s) bajo el mismo control"
            )
            console.print(
                f"  Representantes compartidos: "
                f"{', '.join(community.shared_persons[:3])}"
            )
            for c in community.community_companies[:5]:
                console.print(f"  • {c.get('name', '—')} ({c.get('ruc', '—')})")


@graph_group.command("neo4j-high-risk")
@click.option("--min-flags", type=int, default=2, show_default=True,
              help="Minimum number of flags to include a company.")
@click.option("--limit", type=int, default=20, show_default=True,
              help="Max companies to return.")
def graph_neo4j_high_risk(min_flags: int, limit: int) -> None:
    """List companies with the most documentary risk signals.

    Example:

    \\b
      agenteperry graph neo4j-high-risk --min-flags 2
      agenteperry graph neo4j-high-risk --min-flags 1 --limit 50
    """
    try:
        from agenteperry.graph.neo4j_queries import InvestigativeQueries
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    with InvestigativeQueries() as q:
        suppliers = q.get_high_risk_suppliers(min_flags=min_flags, limit=limit)

    if not suppliers:
        console.print(
            f"[yellow]No se encontraron empresas con >={min_flags} senales de riesgo.[/]"
        )
        return

    tbl = Table(title=f"Empresas con >= {min_flags} senales de riesgo")
    tbl.add_column("Empresa")
    tbl.add_column("RUC")
    tbl.add_column("Flags", justify="right")
    tbl.add_column("Contratos", justify="right")
    tbl.add_column("Monto total (S/)", justify="right")
    tbl.add_column("Codigos")
    for s in suppliers:
        tbl.add_row(
            s.name[:40],
            s.ruc,
            str(s.flag_count),
            str(s.contract_count),
            f"{s.total_amount:,.0f}" if s.total_amount else "—",
            ", ".join(s.flag_codes[:3]),
        )
    console.print(tbl)


@graph_group.command("neo4j-counts")
def graph_neo4j_counts() -> None:
    """Show node count per label in the Neo4j graph (quick health check).

    Example:

    \\b
      agenteperry graph neo4j-counts
    """
    try:
        from agenteperry.graph.neo4j_queries import InvestigativeQueries
    except ImportError:
        raise click.ClickException(
            "neo4j driver not installed. Run: uv pip install 'agenteperry[graph]'"
        ) from None

    with InvestigativeQueries() as q:
        counts = q.get_node_counts()

    if not counts:
        console.print("[yellow]El grafo esta vacio. Ejecuta: agenteperry graph neo4j-ingest[/]")
        return

    tbl = Table(title="Neo4j Node Counts")
    tbl.add_column("Label")
    tbl.add_column("Count", justify="right")
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        tbl.add_row(label, f"{count:,}")
    console.print(tbl)


def _build_audit(
    records: list[dict[str, Any]],
    entities: list[Any],
    relationships: list[Any],
    chunks_count: int = 0,
) -> dict[str, Any]:
    """Build audit metrics from pipeline results."""
    total = len(records)
    contracts = [r for r in records if r.get("record_type") == "contract"]
    procedures = [r for r in records if r.get("record_type") == "procedure"]
    with_entity_ruc = sum(1 for r in records if r.get("entity_ruc") and len(str(r["entity_ruc"])) == 11)
    with_supplier_ruc = sum(1 for r in records if r.get("supplier_ruc") and len(str(r["supplier_ruc"])) == 11)
    with_monto = sum(1 for r in records if r.get("monto") is not None)
    with_region = sum(1 for r in records if r.get("region"))
    with_external_id = sum(1 for r in records if r.get("external_id"))
    with_checksum = sum(1 for r in records if r.get("checksum"))

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "total_records": total,
        "contracts_count": len(contracts),
        "procedures_count": len(procedures),
        "with_entity_ruc": with_entity_ruc,
        "with_supplier_ruc": with_supplier_ruc,
        "with_monto": with_monto,
        "with_region": with_region,
        "with_external_id": with_external_id,
        "with_checksum": with_checksum,
        "entities_created": len(entities),
        "relationships_created": len(relationships),
        "document_chunks_created": chunks_count,
    }


def _count_db_relationships() -> int:
    from agenteperry.db.client import DbClient

    try:
        rows = DbClient().execute("SELECT COUNT(*) AS c FROM source_relationships")
        return rows[0]["c"]
    except Exception:
        return 0


def _build_sunat_audit(
    records: list[dict[str, Any]],
    entities: list[Any],
    relationships: list[Any],
    enrichment_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Build audit metrics specific to SUNAT padron pipeline."""
    from agenteperry.db.client import DbClient

    db = DbClient()
    total = len(records)
    with_valid_ruc = sum(
        1 for r in records
        if r.get("entity_ruc") and len(str(r["entity_ruc"])) == 11
    )
    with_name = sum(1 for r in records if r.get("entity_name"))
    with_estado = sum(
        1 for r in records
        if r.get("parsed_data", {}).get("estado")
    )
    with_condicion = sum(
        1 for r in records
        if r.get("parsed_data", {}).get("condicion")
    )
    with_ubigeo = sum(
        1 for r in records
        if r.get("parsed_data", {}).get("ubigeo")
    )

    active_count = sum(
        1 for r in records
        if (r.get("parsed_data", {}).get("estado") or "").upper() == "ACTIVO"
    )
    baja_count = sum(
        1 for r in records
        if (r.get("parsed_data", {}).get("estado") or "").upper() == "BAJA"
    )
    no_habido_count = sum(
        1 for r in records
        if (r.get("parsed_data", {}).get("condicion") or "").upper() == "NO HABIDO"
    )

    ocds_stats: dict[str, Any] = {}
    try:
        ocds_total = db.execute(
            "SELECT COUNT(*) AS c FROM source_entities WHERE entity_type = 'company'"
        )
        ocds_with_ruc = db.execute(
            "SELECT COUNT(*) AS c FROM source_entities WHERE entity_type = 'company' AND canonical_id ~ '^[0-9]{11}$'"
        )
        matched_sunat = db.execute("""
            SELECT COUNT(*) AS c
            FROM source_entities ocds
            WHERE ocds.entity_type = 'company'
              AND ocds.canonical_id ~ '^[0-9]{11}$'
              AND EXISTS (
                  SELECT 1 FROM source_records sunat
                  JOIN source_catalog c ON c.id = sunat.source_id
                  WHERE sunat.entity_ruc = ocds.canonical_id
                    AND c.source_code = 'sunat_padron'
              )
        """)
        total_companies = ocds_total[0]["c"] if ocds_total else 0
        with_ruc = ocds_with_ruc[0]["c"] if ocds_with_ruc else 0
        matched = matched_sunat[0]["c"] if matched_sunat else 0
        ocds_stats = {
            "ocds_companies_total": total_companies,
            "ocds_companies_with_ruc": with_ruc,
            "ocds_companies_matched_sunat": matched,
            "ocds_match_rate": round(matched / max(with_ruc, 1) * 100, 2),
        }
    except Exception:
        ocds_stats = {
            "ocds_companies_total": None,
            "ocds_companies_with_ruc": None,
            "ocds_companies_matched_sunat": None,
            "ocds_match_rate": None,
        }

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        "source_code": "sunat_padron",
        "total_records": total,
        "with_valid_ruc": with_valid_ruc,
        "with_name": with_name,
        "with_estado": with_estado,
        "with_condicion": with_condicion,
        "with_ubigeo": with_ubigeo,
        "entities_created": len(entities),
        "relationships_created": len(relationships),
        "companies_enriched": enrichment_metrics.get("companies_enriched", 0),
        "companies_unmatched": enrichment_metrics.get("companies_unmatched", 0),
        "records_skipped": enrichment_metrics.get("records_skipped", 0),
        "errors": enrichment_metrics.get("errors", 0),
        "active_count": active_count,
        "baja_count": baja_count,
        "no_habido_count": no_habido_count,
        **ocds_stats,
    }


def _write_json_or_print(payload: Mapping[str, object], output_path: Path | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if output_path is None:
        console.print(rendered)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered + "\n", encoding="utf-8")


def _write_jsonl_or_print(records: Sequence[Mapping[str, Any]], output_path: Path | None) -> None:
    rendered = "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records)
    if output_path is None:
        console.print(rendered)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered + ("\n" if rendered else ""), encoding="utf-8")


def _load_pages(path: Path) -> list[TdrPage]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    raw_pages = cast(list[Any], payload if isinstance(payload, list) else payload.get("pages", []))
    return [TdrPage.model_validate(page) for page in raw_pages]


def _load_chunks(path: Path) -> list[TdrChunk]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    raw_chunks = cast(list[Any], payload if isinstance(payload, list) else payload.get("chunks", []))
    return [TdrChunk.model_validate(chunk) for chunk in raw_chunks]


def _load_jsonl(path: Path) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        payload: Any = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ValueError(f"JSONL line is not an object in {path}")
        records.append(cast(Mapping[str, Any], payload))
    return records


@main.group("phase1")
def phase1_group() -> None:
    """Phase 1 Scraping Pipeline: OCDS + SUNAT + SEACE docs + OCR + manifests."""


@phase1_group.command("run")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
@click.option("--skip-ocr", is_flag=True, help="Skip MiniMax OCR classification.")
@click.option("--limit-contracts", type=int, default=None, help="Limit contracts (for smoke test).")
@click.option("--limit-docs", type=int, default=None, help="Limit documents (for smoke test).")
@click.option("--dry-run", is_flag=True, help="Skip downloads, show what would run.")
@click.option("--workers", type=int, default=20, show_default=True, help="Parallel workers for OCR.")
def phase1_run(base_dir: Path, skip_ocr: bool, limit_contracts: int | None, limit_docs: int | None, dry_run: bool, workers: int) -> None:
    """Run the complete Phase 1 scraping pipeline end-to-end.

    Steps: OCDS filter → SUNAT Padrón → SEACE documents → OCR → validate → build packs → golden set.

    Example:
        agenteperry phase1 run
        agenteperry phase1 run --skip-ocr --limit-contracts 50 --limit-docs 10
    """
    import subprocess
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase1_orchestrator.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve()), "--workers", str(workers)]
    if skip_ocr:
        args.append("--skip-ocr")
    if limit_contracts:
        args.extend(["--limit-contracts", str(limit_contracts)])
    if limit_docs:
        args.extend(["--limit-docs", str(limit_docs)])
    if dry_run:
        args.append("--dry-run")
    result = subprocess.run(args, capture_output=True, text=True, timeout=7200)
    if result.stdout:
        console.print(result.stdout[:3000])
    if result.returncode != 0 and result.stderr:
        console.print(f"[red]{result.stderr[:500]}[/]")
    if result.returncode == 0:
        console.print("[green]OK[/] Phase 1 pipeline complete")
    else:
        console.print(f"[red]FAIL[/] Phase 1 pipeline failed (rc={result.returncode})")


@phase1_group.command("ocds")
@click.option("--years", type=int, nargs="+", default=[2024, 2025, 2026], help="Years to download")
@click.option("--output-dir", "output_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
@click.option("--limit", type=int, default=None, help="Limit contracts (for testing).")
def phase1_ocds(years: list[int], output_dir: Path, limit: int | None) -> None:
    """Step 1: Download and filter OCDS Peru for salud + ambiente."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase1_ocds_filter.py"
    args = [sys.executable, str(script), "--output-dir", str(output_dir.resolve())]
    if years != [2024, 2025, 2026]:
        args.extend([str(y) for y in years])
    if limit:
        args.extend(["--limit", str(limit)])
    result = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            console.print(f"[green]OK[/] {data['total_contracts']} contracts ({data['salud_contracts']} salud, {data['ambiente_contracts']} ambiente)")
        except Exception:
            console.print(result.stdout[:500])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("sunat")
@click.option("--output-dir", "output_dir", type=click.Path(path_type=Path), default=Path("data/sunat"))
@click.option("--processes-csv", "processes_csv", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud/processes.csv"))
@click.option("--limit", type=int, default=None, help="Limit matched rows.")
@click.option("--download-only", is_flag=True, help="Download only, skip parsing.")
def phase1_sunat(output_dir: Path, processes_csv: Path, limit: int | None, download_only: bool) -> None:
    """Step 2: Download and parse SUNAT Padrón Reducido."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase1_sunat_padron.py"
    args = [sys.executable, str(script), "--output-dir", str(output_dir.resolve()), "--processes-csv", str(processes_csv.resolve())]
    if download_only:
        args.append("--download-only")
    if limit:
        args.extend(["--limit", str(limit)])
    result = subprocess.run(args, capture_output=True, text=True, timeout=3600)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            console.print(f"[green]OK[/] matched {data['matched_rows']} rows (active={data['active_count']} baja={data['baja_count']} no_habido={data['no_habido_count']})")
        except Exception:
            console.print(result.stdout[:500])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("seace-docs")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
@click.option("--limit", type=int, default=None, help="Limit documents to download.")
@click.option("--rate-limit", type=float, default=1.0, show_default=True, help="Seconds between requests.")
def phase1_seace_docs(base_dir: Path, limit: int | None, rate_limit: float) -> None:
    """Step 3: Download SEACE PDF documents with rate limiting."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase1_seace_documents.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve()), "--rate-limit", str(rate_limit)]
    if limit:
        args.extend(["--limit", str(limit)])
    result = subprocess.run(args, capture_output=True, text=True, timeout=7200)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            console.print(f"[green]OK[/] downloaded={data['downloaded']} failed={data['failed']} skipped={data['skipped_existing']}")
        except Exception:
            console.print(result.stdout[:500])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("ocr")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
@click.option("--workers", type=int, default=20, show_default=True, help="Parallel workers.")
@click.option("--max-pages", type=int, default=10, show_default=True, help="Max pages per PDF to OCR.")
@click.option("--dry-run", is_flag=True, help="Show candidates without processing.")
def phase1_ocr(base_dir: Path, workers: int, max_pages: int, dry_run: bool) -> None:
    """Step 4: Classify PDF OCR level using MiniMax API (parallel, unlimited key)."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "phase1_ocr_classifier.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve()), "--workers", str(workers), "--max-pages", str(max_pages)]
    if dry_run:
        args.append("--dry-run")
    result = subprocess.run(args, capture_output=True, text=True, timeout=7200)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            console.print(f"[green]OK[/] candidates={data.get('candidates_ocr','?')} success={data.get('success','?')} errors={data.get('errors','?')}")
        except Exception:
            console.print(result.stdout[:500])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("validate")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
def phase1_validate(base_dir: Path) -> None:
    """Step 5: Validate delivery manifests (processes.csv, documents.csv, awards.csv)."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "validate_scraping_delivery.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve()), "--no-pdf-open"]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            if data.get("ok"):
                console.print(f"[green]OK[/] validation passed: {data['processes_total']} processes, {data['documents_total']} documents")
            else:
                console.print("[red]FAIL[/] validation errors:")
                for error in data.get("errors", [])[:20]:
                    console.print(f"  {error}")
        except Exception:
            console.print(result.stdout[:500])
    if result.returncode != 0 and result.stderr:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("build-packs")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
def phase1_build_packs(base_dir: Path) -> None:
    """Step 6: Build process_document_packs.jsonl."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "build_process_document_packs.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve())]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.stdout:
        try:
            data = json.loads(result.stdout)
            console.print(f"[green]OK[/] output={data.get('output_path','?')}")
        except Exception:
            console.print(result.stdout[:300])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@phase1_group.command("golden")
@click.option("--base-dir", "base_dir", type=click.Path(path_type=Path), default=Path("data/scraped/seace_salud"))
@click.option("--output-dir", "output_dir", type=click.Path(path_type=Path), default=Path("data/golden_set/metadata.csv"))
@click.option("--min-text-coverage", type=float, default=0.70, show_default=True)
def phase1_golden(base_dir: Path, output_dir: Path, min_text_coverage: float) -> None:
    """Step 7: Select Golden Set candidates."""
    repo_root = Path(__file__).resolve().parents[4]
    script = repo_root / "scripts" / "select_golden_candidates.py"
    args = [sys.executable, str(script), "--base-dir", str(base_dir.resolve()), "--out", str(output_dir.resolve()), "--min-text-coverage", str(min_text_coverage)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.stdout:
        console.print(result.stdout[:300])
    if result.returncode != 0:
        console.print(f"[red]FAIL[/] {result.stderr[:200]}")


@main.group("db")
def db_group() -> None:
    """Sync collected records and graph output to Supabase/Postgres."""


@db_group.command("sync")
@click.argument("records_jsonl", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--graph",
    "graph_json",
    type=click.Path(path_type=Path),
    default=None,
    help="Graph JSON from `graph map-records`.",
)
@click.option("--batch-size", type=int, default=500, show_default=True)
def db_sync(records_jsonl: Path, graph_json: Path | None, batch_size: int) -> None:
    """Upsert source_records and optionally entities+relationships from graph JSON."""
    from agenteperry.sync.loader import upsert_entities, upsert_relationships, upsert_source_records

    counts: dict[str, int] = {}
    counts["source_records"] = upsert_source_records(records_jsonl, batch_size=batch_size)
    if graph_json:
        counts["source_entities"] = upsert_entities(graph_json, batch_size=batch_size)
        counts["source_relationships"] = upsert_relationships(graph_json, batch_size=batch_size)

    table = Table(title="Sync results")
    table.add_column("Table")
    table.add_column("Rows upserted")
    for table_name, count in counts.items():
        table.add_row(table_name, str(count))
    console.print(table)


@db_group.command("chunk-contracts")
@click.option("--source-code", default="ocds_peru", show_default=True)
@click.option("--limit", type=int, default=None, help="Limit records for smoke runs.")
@click.option("--batch-size", type=int, default=500, show_default=True)
def db_chunk_contracts(source_code: str, limit: int | None, batch_size: int) -> None:
    """Create narrative document_chunks from source_records contracts."""
    from agenteperry.sync.chunks import upsert_contract_chunks

    count = upsert_contract_chunks(source_code=source_code, limit=limit, batch_size=batch_size)
    table = Table(title="Contract chunk results")
    table.add_column("Source")
    table.add_column("Chunks upserted")
    table.add_row(source_code, str(count))
    console.print(table)


if __name__ == "__main__":
    main()
