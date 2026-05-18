#!/usr/bin/env python3
"""Parallel OCR classifier using MiniMax API (unlimited key).

For each PDF in documents.csv that has:
  - ocr_status = "needed" (text coverage < 10% or missing)
  - ocr_class not set ("scanned" PDFs from SEACE download)

Extracts pages via PyMuPDF, sends images to MiniMax API, gets OCR text,
then updates documents.csv with pages_with_text, text_coverage_ratio,
ocr_class, ocr_status.

Supports parallel workers (default 20) and batch processing.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

SCRIPT_VERSION = "1.0.0"

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_BASE = os.environ.get("MINIMAX_API_BASE", "https://api.minimax.chat/v1")
MINIMAX_MODEL = os.environ.get("MINIMAX_OCR_MODEL", "MiniCPM-v2")
DEFAULT_WORKERS = int(os.environ.get("MINIMAX_OCR_WORKERS", "20"))


@dataclass
class OcrResult:
    document_id: str
    status: str
    pages_with_text: int
    total_pages: int
    coverage_ratio: float
    ocr_class: str
    error: str | None


def load_env_minimax() -> dict[str, str]:
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        key = os.environ.get("MINIMAX_OCR_KEY", "").strip()
    base = os.environ.get("MINIMAX_API_BASE", "https://api.minimax.chat/v1").strip()
    model = os.environ.get("MINIMAX_OCR_MODEL", "MiniCPM-v2").strip()
    return {"api_key": key, "base": base, "model": model}


def pdf_page_to_image(pdf_path: Path, page_num: int, dpi: int = 150) -> bytes:
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_num)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        clip = page.rect
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, clip=clip)
        return pix.tobytes("png")


def ocr_page_minimax(image_bytes: bytes, api_key: str, api_base: str, model: str, timeout: int = 60) -> str:
    import base64
    import urllib.request

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    data = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                    {
                        "type": "text",
                        "text": "Extract ALL text from this document page. Preserve line breaks. If no text is visible, respond only with: [NO_TEXT]",
                    },
                ],
            }
        ],
        "max_tokens": 4096,
        "temperature": 0.1,
    }

    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        f"{api_base.rstrip('/')}/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"AgentePerry-OCR/{SCRIPT_VERSION}",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as response:
        resp = json.loads(response.read().decode("utf-8"))

    content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    if content.strip() == "[NO_TEXT]":
        return ""
    return content


def process_pdf_for_ocr(
    pdf_path: Path,
    document_id: str,
    api_key: str,
    api_base: str,
    model: str,
    max_pages: int | None = None,
) -> OcrResult:
    try:
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            pages_to_process = min(total_pages, max_pages) if max_pages else total_pages
            pages_with_text = 0

            for page_num in range(pages_to_process):
                try:
                    image_bytes = pdf_page_to_image(pdf_path, page_num, dpi=150)
                    text = ocr_page_minimax(image_bytes, api_key, api_base, model, timeout=60)
                    if text and text.strip():
                        pages_with_text += 1
                except Exception:
                    continue

            coverage_ratio = pages_with_text / total_pages if total_pages > 0 else 0.0
            ocr_class = "textual" if coverage_ratio >= 0.90 else "mixed" if coverage_ratio >= 0.10 else "scanned"

            return OcrResult(
                document_id=document_id,
                status="success",
                pages_with_text=pages_with_text,
                total_pages=total_pages,
                coverage_ratio=round(coverage_ratio, 4),
                ocr_class=ocr_class,
                error=None,
            )
    except Exception as exc:
        return OcrResult(
            document_id=document_id,
            status="error",
            pages_with_text=0,
            total_pages=0,
            coverage_ratio=0.0,
            ocr_class="corrupt",
            error=str(exc)[:200],
        )


def run_ocr_classifier(
    base_dir: Path,
    workers: int = DEFAULT_WORKERS,
    max_pages_per_pdf: int | None = 10,
    dry_run: bool = False,
) -> dict[str, Any]:
    csv_path = base_dir / "documents.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"documents.csv not found at {csv_path}")

    env = load_env_minimax()
    if not env["api_key"]:
        raise ValueError("MINIMAX_API_KEY not set in environment")
    print(f"Using MiniMax API: {env['base']} model={env['model']} workers={workers}", flush=True)

    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    candidates = []
    for idx, row in enumerate(rows):
        file_path = row.get("file_path", "").strip()
        ocr_status = row.get("ocr_status", "").strip()
        ocr_class = row.get("ocr_class", "").strip()
        parse_status = row.get("parse_status", "").strip()
        pdf_exists = Path(file_path).exists() if file_path else False
        is_pdf = file_path.lower().endswith(".pdf") or row.get("mime_type", "").find("pdf") >= 0

        if pdf_exists and is_pdf and (ocr_status == "needed" or not ocr_class or parse_status in ("pending", "failed")):
            candidates.append((idx, row))

    print(f"Found {len(candidates)} documents needing OCR out of {len(rows)} total", flush=True)

    if dry_run:
        print(f"DRY RUN: would process {len(candidates)} documents with {workers} workers")
        return {"dry_run": True, "candidates": len(candidates), "workers": workers}

    success_count = 0
    error_count = 0
    errors: list[str] = []

    def process_one(idx_row: tuple[int, dict[str, str]]) -> tuple[int, OcrResult]:
        idx, row = idx_row
        file_path = row.get("file_path", "").strip()
        document_id = row.get("document_id", f"row_{idx}")
        result = process_pdf_for_ocr(
            pdf_path=Path(file_path),
            document_id=document_id,
            api_key=env["api_key"],
            api_base=env["base"],
            model=env["model"],
            max_pages=max_pages_per_pdf,
        )
        return idx, result

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(process_one, item): item for item in candidates}
        for future in as_completed(futures):
            try:
                idx, result = future.result()
                rows[idx]["pages_with_text"] = str(result.pages_with_text)
                rows[idx]["pages_needing_ocr"] = str(result.total_pages - result.pages_with_text)
                rows[idx]["text_coverage_ratio"] = str(result.coverage_ratio)
                rows[idx]["ocr_class"] = result.ocr_class
                rows[idx]["ocr_status"] = "done"
                rows[idx]["ocr_required"] = "false" if result.coverage_ratio >= 0.70 else "true"
                if result.error:
                    rows[idx]["error_message"] = f"OCR error: {result.error}"
                if result.status == "success":
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"{result.document_id}: {result.error}")
                if (success_count + error_count) % 10 == 0:
                    print(f"  OCR progress: {success_count} success, {error_count} errors", flush=True)
            except Exception as exc:
                error_count += 1
                errors.append(f"Future error: {str(exc)[:100]}")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return {
        "total_documents": len(rows),
        "candidates_ocr": len(candidates),
        "success": success_count,
        "errors": error_count,
        "errors_sample": errors[:20],
        "workers": workers,
        "max_pages_per_pdf": max_pages_per_pdf,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Parallel OCR classifier using MiniMax API.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel workers")
    parser.add_argument("--max-pages", type=int, default=10, help="Max pages per PDF to OCR")
    parser.add_argument("--dry-run", action="store_true", help="Show candidates without processing")
    args = parser.parse_args()

    result = run_ocr_classifier(
        base_dir=args.base_dir,
        workers=args.workers,
        max_pages_per_pdf=args.max_pages,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())