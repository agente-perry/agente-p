# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
"""CLI commands for OCR pipeline."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, cast

import click
from rich.console import Console
from rich.table import Table

from agenteperry.ocr.bridge import (
    build_ocr_bridge_bundles,
    prepare_analyzer_bundles,
    prepare_loader_inputs,
)
from agenteperry.ocr.pdf_classifier import classify_pdf, classify_pdf_dir
from agenteperry.ocr.processor import OcrProcessor, process_many

console = Console()


def _collect_pdfs(input_path: Path, recursive: bool) -> list[Path]:
    resolved = input_path.resolve()
    if resolved.is_file():
        return [resolved] if resolved.suffix.lower() == ".pdf" else []
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(path for path in resolved.glob(pattern) if path.is_file())


def _load_ready_from_manifest(
    loader_manifest: Path,
    *,
    limit: int | None,
    dry_run: bool,
) -> tuple[list[tuple[str, str, int, int, int, str]], int]:
    payload_raw = json.loads(loader_manifest.read_text(encoding="utf-8"))
    payload: dict[str, Any] = {}
    if isinstance(payload_raw, dict):
        payload = cast(dict[str, Any], payload_raw)
    bundles_raw = payload.get("bundles")
    bundles: list[dict[str, Any]] = []
    if isinstance(bundles_raw, list):
        for item_raw in bundles_raw:
            item: object = item_raw
            if isinstance(item, dict):
                bundles.append(cast(dict[str, Any], item))

    if limit is not None:
        bundles = bundles[:limit]

    rows: list[tuple[str, str, int, int, int, str]] = []
    loaded = 0
    from agenteperry.tdr.loader import load_pipeline_json

    for row in bundles:
        document_id = str(row.get("document_id") or "")
        manifest_jsonl = row.get("manifest_jsonl")
        chunks_json = row.get("chunks_json")
        flags_json = row.get("flags_json")
        if not isinstance(manifest_jsonl, str) or not isinstance(chunks_json, str) or not isinstance(flags_json, str):
            rows.append((document_id, "skipped", 0, 0, 0, "invalid_loader_entry"))
            continue

        if dry_run:
            rows.append((document_id, "ready", 0, 0, 0, "dry_run"))
            continue

        counts = load_pipeline_json(
            manifest_json=Path(manifest_jsonl),
            chunks_json=Path(chunks_json),
            flags_json=Path(flags_json),
        )
        loaded += 1
        rows.append(
            (
                document_id,
                "loaded",
                int(counts.get("tdr_documents", 0)),
                int(counts.get("tdr_chunks", 0)),
                int(counts.get("tdr_flags", 0)),
                "",
            )
        )

    return rows, loaded


@click.group("ocr")
def ocr_group() -> None:
    """OCR pipeline for scanned/mixed TDR PDFs."""


@ocr_group.command("classify")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
def ocr_classify(input_path: Path, recursive: bool) -> None:
    """Classify PDF files as textual/mixed/scanned."""
    if input_path.is_file():
        results = [classify_pdf(input_path)]
    else:
        results = classify_pdf_dir(input_path, recursive=recursive)

    table = Table(title="OCR classification")
    table.add_column("pdf")
    table.add_column("pages")
    table.add_column("coverage")
    table.add_column("classification")
    table.add_column("action")
    for result in results:
        table.add_row(
            Path(result.pdf_path).name,
            str(result.pages_total),
            f"{result.coverage_pct}%",
            result.classification,
            result.recommended_action,
        )
    console.print(table)


@ocr_group.command("run")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--recursive/--no-recursive", default=True, show_default=True)
@click.option("--limit", type=int, default=None)
@click.option("--workers", type=int, default=5, show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/ocr"), show_default=True)
@click.option("--only-needs-ocr", is_flag=True, default=False)
def ocr_run(
    input_path: Path,
    recursive: bool,
    limit: int | None,
    workers: int,
    dry_run: bool,
    force: bool,
    output_dir: Path,
    only_needs_ocr: bool,
) -> None:
    """Run OCR processing on a directory (or single file)."""
    pdf_paths = _collect_pdfs(input_path, recursive=recursive)
    processor = OcrProcessor(output_base_dir=output_dir)
    manifests = asyncio.run(
        process_many(
            processor,
            pdf_paths,
            limit=limit,
            workers=workers,
            dry_run=dry_run,
            force=force,
            only_needs_ocr=only_needs_ocr,
        )
    )

    table = Table(title="OCR run summary")
    table.add_column("pdf")
    table.add_column("pages")
    table.add_column("coverage_before")
    table.add_column("status")
    table.add_column("output_dir")
    for manifest in manifests:
        table.add_row(
            Path(manifest.source_pdf_path).name,
            str(manifest.pages_total),
            f"{manifest.coverage_before_pct}%",
            manifest.status,
            manifest.output_dir,
        )
    console.print(table)


@ocr_group.command("run-one")
@click.option("--pdf", "pdf_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--ocid", default=None)
@click.option("--workers", type=int, default=5, show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/ocr"), show_default=True)
def ocr_run_one(
    pdf_path: Path,
    ocid: str | None,
    workers: int,
    dry_run: bool,
    force: bool,
    output_dir: Path,
) -> None:
    """Run OCR processing for a single PDF."""
    processor = OcrProcessor(output_base_dir=output_dir)
    manifest = asyncio.run(
        processor.process_pdf(
            pdf_path=pdf_path,
            ocid=ocid,
            dry_run=dry_run,
            force=force,
            workers=workers,
        )
    )

    table = Table(title="OCR run-one result")
    table.add_column("field")
    table.add_column("value")
    for key in [
        "document_id",
        "ocid",
        "pages_total",
        "pages_attempted",
        "pages_succeeded",
        "pages_failed",
        "status",
        "coverage_before_pct",
        "coverage_after_pct",
        "output_dir",
    ]:
        table.add_row(key, str(getattr(manifest, key)))
    console.print(table)


@ocr_group.command("bridge")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--output-dir", type=click.Path(path_type=Path), default=Path("data/ocr_bridge"), show_default=True)
@click.option("--contracts-jsonl", type=click.Path(exists=True, path_type=Path), default=None)
@click.option("--limit", type=int, default=None)
@click.option("--strict/--no-strict", default=True, show_default=True, help="Skip bundles without contract context match.")
def ocr_bridge(
    input_path: Path,
    output_dir: Path,
    contracts_jsonl: Path | None,
    limit: int | None,
    strict: bool,
) -> None:
    """Build analyzer-ready bundles with provenance and contract context."""
    results = build_ocr_bridge_bundles(
        ocr_root=input_path,
        output_dir=output_dir,
        contracts_jsonl=contracts_jsonl,
        limit=limit,
        strict=strict,
    )

    table = Table(title="OCR bridge summary")
    table.add_column("document_id")
    table.add_column("ocid")
    table.add_column("status")
    table.add_column("bundle_dir")
    table.add_column("reason")
    for item in results:
        table.add_row(item.document_id, str(item.ocid), item.status, str(item.bundle_dir), str(item.reason))
    console.print(table)


@ocr_group.command("prepare-analyzer")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--limit", type=int, default=None)
@click.option("--max-chars", type=int, default=1200, show_default=True)
@click.option("--overlap-chars", type=int, default=160, show_default=True)
@click.option("--strict/--no-strict", default=True, show_default=True, help="Require contract/provenance context in each bridge bundle.")
def ocr_prepare_analyzer(
    input_path: Path,
    limit: int | None,
    max_chars: int,
    overlap_chars: int,
    strict: bool,
) -> None:
    """Generate chunks/flags from bridge bundles and write analyzer index manifest."""
    results = prepare_analyzer_bundles(
        bridge_root=input_path,
        limit=limit,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        strict=strict,
    )
    table = Table(title="OCR prepare-analyzer summary")
    table.add_column("document_id")
    table.add_column("ocid")
    table.add_column("status")
    table.add_column("chunks")
    table.add_column("flags")
    table.add_column("reason")
    for item in results:
        table.add_row(
            item.document_id,
            str(item.ocid),
            item.status,
            str(item.chunks_count),
            str(item.flags_count),
            str(item.reason),
        )
    console.print(table)
    console.print(f"[green]OK[/] analyzer manifest: {input_path.resolve() / 'analyzer_input_manifest.json'}")


@ocr_group.command("prepare-loader")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--limit", type=int, default=None)
@click.option("--strict/--no-strict", default=True, show_default=True, help="Require contract/provenance context for loader inputs.")
def ocr_prepare_loader(input_path: Path, limit: int | None, strict: bool) -> None:
    """Generate per-bundle tdr_manifest.jsonl + loader manifest index."""
    results = prepare_loader_inputs(
        bridge_root=input_path,
        limit=limit,
        strict=strict,
    )
    table = Table(title="OCR prepare-loader summary")
    table.add_column("document_id")
    table.add_column("ocid")
    table.add_column("status")
    table.add_column("manifest_jsonl")
    table.add_column("reason")
    for item in results:
        table.add_row(
            item.document_id,
            str(item.ocid),
            item.status,
            str(item.manifest_jsonl),
            str(item.reason),
        )
    console.print(table)
    console.print(f"[green]OK[/] loader manifest: {input_path.resolve() / 'loader_input_manifest.json'}")


@ocr_group.command("load-ready")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--limit", type=int, default=None)
@click.option("--dry-run", is_flag=True, default=False)
def ocr_load_ready(input_path: Path, limit: int | None, dry_run: bool) -> None:
    """Load ready bundles into TDR tables using loader_input_manifest.json."""
    loader_manifest = input_path.resolve() / "loader_input_manifest.json"
    if not loader_manifest.exists():
        raise click.ClickException(f"No existe loader manifest: {loader_manifest}")

    table = Table(title="OCR load-ready summary")
    table.add_column("document_id")
    table.add_column("status")
    table.add_column("tdr_documents")
    table.add_column("tdr_chunks")
    table.add_column("tdr_flags")
    table.add_column("reason")

    rows, loaded = _load_ready_from_manifest(loader_manifest, limit=limit, dry_run=dry_run)
    for row in rows:
        document_id, status, tdr_documents, tdr_chunks, tdr_flags, reason = row
        table.add_row(document_id, status, str(tdr_documents), str(tdr_chunks), str(tdr_flags), reason)

    console.print(table)
    if dry_run:
        console.print("[green]OK[/] dry-run completado")
    else:
        console.print(f"[green]OK[/] bundles cargados: {loaded}")


@ocr_group.command("run-all")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--contracts-jsonl", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--recursive/--no-recursive", default=True, show_default=True)
@click.option("--limit", type=int, default=None)
@click.option("--workers", type=int, default=3, show_default=True)
@click.option("--ocr-output-dir", type=click.Path(path_type=Path), default=Path("data/ocr"), show_default=True)
@click.option("--bridge-output-dir", type=click.Path(path_type=Path), default=Path("data/ocr_bridge"), show_default=True)
@click.option("--strict/--no-strict", default=True, show_default=True)
@click.option("--load-ready/--no-load-ready", default=True, show_default=True)
@click.option("--load-dry-run/--no-load-dry-run", default=True, show_default=True)
def ocr_run_all(
    input_path: Path,
    contracts_jsonl: Path,
    recursive: bool,
    limit: int | None,
    workers: int,
    ocr_output_dir: Path,
    bridge_output_dir: Path,
    strict: bool,
    load_ready: bool,
    load_dry_run: bool,
) -> None:
    """End-to-end OCR pipeline: run -> bridge -> prepare-analyzer -> prepare-loader -> optional load-ready."""
    pdf_paths = _collect_pdfs(input_path, recursive=recursive)
    processor = OcrProcessor(output_base_dir=ocr_output_dir)
    manifests = asyncio.run(
        process_many(
            processor,
            pdf_paths,
            limit=limit,
            workers=workers,
            dry_run=False,
            force=False,
            only_needs_ocr=False,
        )
    )
    console.print(f"[green]OK[/] OCR processed docs: {len(manifests)}")

    bridge_results = build_ocr_bridge_bundles(
        ocr_root=ocr_output_dir,
        output_dir=bridge_output_dir,
        contracts_jsonl=contracts_jsonl,
        limit=limit,
        strict=strict,
    )
    bridge_ready = sum(1 for item in bridge_results if item.status == "ready")
    console.print(f"[green]OK[/] bridge bundles ready: {bridge_ready}/{len(bridge_results)}")

    analyzer_results = prepare_analyzer_bundles(
        bridge_root=bridge_output_dir,
        limit=limit,
        strict=strict,
    )
    analyzer_ready = sum(1 for item in analyzer_results if item.status == "ready")
    console.print(f"[green]OK[/] analyzer bundles ready: {analyzer_ready}/{len(analyzer_results)}")

    loader_results = prepare_loader_inputs(
        bridge_root=bridge_output_dir,
        limit=limit,
        strict=strict,
    )
    loader_ready_count = sum(1 for item in loader_results if item.status == "ready")
    console.print(f"[green]OK[/] loader bundles ready: {loader_ready_count}/{len(loader_results)}")

    if load_ready:
        loader_manifest = bridge_output_dir.resolve() / "loader_input_manifest.json"
        rows, loaded_count = _load_ready_from_manifest(loader_manifest, limit=limit, dry_run=load_dry_run)
        if load_dry_run:
            ready_count = sum(1 for row in rows if row[1] == "ready")
            console.print(f"[green]OK[/] load-ready dry-run bundles: {ready_count}")
        else:
            console.print(f"[green]OK[/] load-ready bundles loaded: {loaded_count}")
