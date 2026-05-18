#!/usr/bin/env python3
"""Download SEACE PDF documents with rate limiting (1 req/s) and PyMuPDF page analysis.

Reads documents.csv, downloads each PDF from file_url, computes SHA-256,
counts pages and text layer coverage, then updates documents.csv with metadata.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

import fitz

SCRIPT_VERSION = "1.0.0"
RATE_LIMIT_SECONDS = 1.0
USER_AGENT = f"AgentePerry-SEACE-Downloader/{SCRIPT_VERSION}"

MINIMUM_PAGES_FOR_COVERAGE = 3


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def infer_mime_type(url: str, content_type_header: str | None) -> str:
    if content_type_header:
        mime = content_type_header.split(";")[0].strip().lower()
        if mime in {"application/pdf", "application/x-pdf"}:
            return "application/pdf"
        if "zip" in mime or "rar" in mime or "x-rar" in mime:
            return "application/zip"
        if "msword" in mime or "word" in mime:
            return "application/msword"
    ext = url.rsplit(".", 1)[-1].lower() if "." in url else ""
    ext_map = {"pdf": "application/pdf", "zip": "application/zip", "rar": "application/vnd.rar", "doc": "application/msword", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    return ext_map.get(ext, "application/octet-stream")


def inspect_pdf_pages(pdf_path: Path) -> dict[str, Any]:
    try:
        with fitz.open(pdf_path) as doc:
            total_pages = len(doc)
            if total_pages == 0:
                return {"total_pages": 0, "pages_with_text": 0, "pages_needing_ocr": 0, "coverage_ratio": 0.0, "error": None}

            pages_with_text = 0
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                text = page.get_text("text").strip()
                if len(text) >= 50:
                    pages_with_text += 1

            coverage = pages_with_text / total_pages if total_pages > 0 else 0.0
            return {
                "total_pages": total_pages,
                "pages_with_text": pages_with_text,
                "pages_needing_ocr": total_pages - pages_with_text,
                "coverage_ratio": round(coverage, 4),
                "error": None,
            }
    except Exception as exc:
        return {"total_pages": 0, "pages_with_text": 0, "pages_needing_ocr": 0, "coverage_ratio": 0.0, "error": str(exc)}


def classify_ocr_class(coverage_ratio: float) -> str:
    if coverage_ratio >= 0.90:
        return "textual"
    elif coverage_ratio >= 0.10:
        return "mixed"
    else:
        return "scanned"


def _download_file(url: str, timeout: int = 30) -> tuple[bytes, str | None]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        content = response.read()
        content_type = response.headers.get("Content-Type")
        return content, content_type


def download_documents(
    base_dir: Path,
    limit: int | None = None,
    rate_limit: float = RATE_LIMIT_SECONDS,
) -> dict[str, Any]:
    csv_path = base_dir / "documents.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"documents.csv not found at {csv_path}")

    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    pdfs_dir = base_dir / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    failed = 0
    skipped = 0
    errors: list[str] = []

    for idx, row in enumerate(rows):
        if limit and idx >= limit:
            break

        file_url = row.get("file_url", "").strip()
        if not file_url:
            skipped += 1
            continue

        if row.get("sha256") and row.get("file_size_bytes"):
            skipped += 1
            continue

        process_id = row.get("process_id", "unknown")
        document_id = row.get("document_id", f"doc_{idx}")
        safe_name = "".join(ch for ch in (row.get("file_name", f"{document_id}.pdf") or f"{document_id}.pdf")[:80] if ch.isalnum() or ch in "._- ")
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"

        out_dir = pdfs_dir / process_id.replace("/", "_").replace("\\", "_")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / safe_name

        try:
            content, content_type = _download_file(file_url)
            mime = infer_mime_type(file_url, content_type)

            if "pdf" not in mime and not file_url.lower().endswith(".pdf"):
                row["file_size_bytes"] = str(len(content))
                row["error_message"] = f"Unsupported mime: {mime}"
                errors.append(f"{document_id}: Unsupported mime: {mime}")
                failed += 1
                continue

            sha256 = compute_sha256(content)
            out_path.write_bytes(content)
            row["file_path"] = str(out_path)
            row["sha256"] = sha256
            row["file_size_bytes"] = str(len(content))
            row["mime_type"] = mime
            row["downloaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            if mime == "application/pdf" or file_url.lower().endswith(".pdf"):
                page_info = inspect_pdf_pages(out_path)
                row["pages_total"] = str(page_info["total_pages"])
                row["pages_with_text"] = str(page_info["pages_with_text"])
                row["pages_needing_ocr"] = str(page_info["pages_needing_ocr"])
                row["text_coverage_ratio"] = str(page_info["coverage_ratio"])
                row["ocr_class"] = classify_ocr_class(page_info["coverage_ratio"])
                row["ocr_status"] = "not_needed" if page_info["coverage_ratio"] >= 0.10 else "needed"
                row["ocr_required"] = "true" if page_info["coverage_ratio"] < 0.70 else "false"
                if page_info["error"]:
                    row["error_message"] = f"PDF inspect error: {page_info['error']}"
                row["parse_status"] = "parsed" if page_info["total_pages"] > 0 else "failed"
            else:
                row["parse_status"] = "pending"

            downloaded += 1

            if idx % 50 == 0 and idx > 0:
                print(f"  Downloaded {downloaded}, failed {failed}, skipped {skipped} (at row {idx})", flush=True)

        except Exception as exc:
            failed += 1
            err_msg = str(exc)[:200]
            row["error_message"] = f"Download error: {err_msg}"
            errors.append(f"{document_id}: {err_msg}")
            continue

        time.sleep(rate_limit)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    return {
        "total_rows": len(rows),
        "downloaded": downloaded,
        "failed": failed,
        "skipped_existing": skipped,
        "pdfs_dir": str(pdfs_dir),
        "errors_sample": errors[:20],
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Download SEACE PDF documents with rate limiting.")
    parser.add_argument("--base-dir", type=Path, default=Path("data/scraped/seace_salud"))
    parser.add_argument("--limit", type=int, default=None, help="Limit documents to download")
    parser.add_argument("--rate-limit", type=float, default=RATE_LIMIT_SECONDS, help="Seconds between requests")
    args = parser.parse_args()

    result = download_documents(
        base_dir=args.base_dir,
        limit=args.limit,
        rate_limit=args.rate_limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())