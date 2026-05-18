# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownArgumentType=false
"""OCR processing pipeline for PDF documents."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import fitz

from agenteperry.ocr.minimax_client import MinimaxOCRClient
from agenteperry.ocr.models import (
    OcrDocumentStatus,
    OcrManifest,
    OcrPageResult,
    OcrPageStatus,
    PdfOcrClass,
)
from agenteperry.ocr.pdf_classifier import classify_pdf


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:80] or "document"


def _short_sha(sha: str) -> str:
    return sha[:8]


class OcrProcessor:
    def __init__(
        self,
        output_base_dir: Path = Path("data/ocr"),
        client: MinimaxOCRClient | None = None,
    ) -> None:
        self.output_base_dir = output_base_dir
        self.client = client or MinimaxOCRClient()

    async def process_pdf(
        self,
        pdf_path: Path,
        ocid: str | None = None,
        document_id: str | None = None,
        force: bool = False,
        dry_run: bool = False,
        workers: int = 5,
    ) -> OcrManifest:
        classification = classify_pdf(pdf_path)
        started_at = datetime.now(UTC).isoformat()
        if classification.classification == PdfOcrClass.UNSUPPORTED:
            manifest = OcrManifest(
                document_id=document_id or _safe_slug(pdf_path.stem),
                ocid=ocid,
                source_pdf_path=classification.pdf_path,
                source_pdf_sha256=classification.sha256,
                ocr_provider="minimax",
                ocr_model=self.client.model,
                pages_total=classification.pages_total,
                pages_attempted=0,
                pages_succeeded=0,
                pages_failed=0,
                status=OcrDocumentStatus.SKIPPED,
                coverage_before_pct=classification.coverage_pct,
                coverage_after_pct=classification.coverage_pct,
                output_dir=str(self.output_base_dir),
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                errors_count=0,
            )
            return manifest

        doc_id = document_id or self._build_document_id(classification.pdf_path, classification.sha256, ocid)
        out_dir = self.output_base_dir / doc_id
        out_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = out_dir / "ocr_manifest.json"
        existing = self._load_manifest_if_exists(manifest_path)
        if existing and not force:
            if (
                existing.source_pdf_sha256 == classification.sha256
                and existing.status == OcrDocumentStatus.COMPLETED
            ):
                skipped = existing.model_copy(
                    update={
                        "status": OcrDocumentStatus.SKIPPED,
                        "finished_at": datetime.now(UTC).isoformat(),
                    }
                )
                return skipped

        manifest = OcrManifest(
            document_id=doc_id,
            ocid=ocid,
            source_pdf_path=classification.pdf_path,
            source_pdf_sha256=classification.sha256,
            ocr_provider="minimax",
            ocr_model=self.client.model,
            pages_total=classification.pages_total,
            pages_attempted=0,
            pages_succeeded=0,
            pages_failed=0,
            status=OcrDocumentStatus.PENDING if dry_run else OcrDocumentStatus.RUNNING,
            coverage_before_pct=classification.coverage_pct,
            coverage_after_pct=classification.coverage_pct,
            output_dir=str(out_dir.resolve()),
            started_at=started_at,
            finished_at=None,
            errors_count=0,
        )

        if dry_run:
            manifest.status = OcrDocumentStatus.SKIPPED
            manifest.finished_at = datetime.now(UTC).isoformat()
            self._write_manifest(manifest_path, manifest)
            return manifest

        pages_data = self._extract_digital_pages(Path(classification.pdf_path))
        page_numbers_for_ocr: list[int]
        if classification.classification == PdfOcrClass.TEXTUAL:
            page_numbers_for_ocr = []
        elif classification.classification == PdfOcrClass.MIXED:
            page_numbers_for_ocr = [page_number for page_number, text in pages_data.items() if len(text.strip()) < 50]
        else:
            page_numbers_for_ocr = sorted(pages_data.keys())

        manifest.pages_attempted = len(page_numbers_for_ocr)

        ocr_results: list[OcrPageResult] = []
        if page_numbers_for_ocr:
            ocr_results = await self.client.ocr_pdf_pages(
                pdf_path=Path(classification.pdf_path),
                pages=page_numbers_for_ocr,
                workers=workers,
            )

        result_by_page = {result.page_number: result for result in ocr_results}
        merged_results: list[OcrPageResult] = []
        for page_number in sorted(pages_data.keys()):
            digital_text = pages_data[page_number]
            if page_number in result_by_page:
                result = result_by_page[page_number]
                text = result.text.strip() if result.status == OcrPageStatus.OK else digital_text.strip()
                merged_results.append(
                    result.model_copy(
                        update={
                            "text": text,
                            "text_length": len(text),
                        }
                    )
                )
            else:
                merged_results.append(
                    OcrPageResult(
                        page_number=page_number,
                        status=OcrPageStatus.SKIPPED if page_numbers_for_ocr else OcrPageStatus.OK,
                        text=digital_text,
                        text_length=len(digital_text),
                        provider="digital_text",
                        model="pymupdf",
                        latency_ms=None,
                        error=None,
                    )
                )

        pages_succeeded = sum(1 for result in ocr_results if result.status == OcrPageStatus.OK)
        pages_failed = sum(1 for result in ocr_results if result.status == OcrPageStatus.FAILED)
        manifest.pages_succeeded = pages_succeeded
        manifest.pages_failed = pages_failed
        manifest.errors_count = pages_failed

        merged_with_text = sum(1 for result in merged_results if len(result.text.strip()) >= 50)
        manifest.coverage_after_pct = round((merged_with_text / manifest.pages_total) * 100, 2) if manifest.pages_total else 0.0

        if manifest.pages_attempted == 0:
            manifest.status = OcrDocumentStatus.COMPLETED
        elif pages_succeeded == 0 and pages_failed > 0:
            manifest.status = OcrDocumentStatus.FAILED
        elif pages_failed > 0:
            manifest.status = OcrDocumentStatus.COMPLETED_WITH_ERRORS
        else:
            manifest.status = OcrDocumentStatus.COMPLETED
        manifest.finished_at = datetime.now(UTC).isoformat()

        self._write_manifest(manifest_path, manifest)
        self._write_pages_jsonl(out_dir / "ocr_pages.jsonl", merged_results)
        self._write_text_file(out_dir / "ocr_text.txt", merged_results)
        if pages_failed:
            self._write_errors_jsonl(out_dir / "ocr_errors.jsonl", ocr_results)

        return manifest

    def _build_document_id(self, pdf_path: str, sha256: str, ocid: str | None) -> str:
        if ocid:
            return f"{_safe_slug(ocid)}_{_short_sha(sha256)}"
        return f"{_safe_slug(Path(pdf_path).stem)}_{_short_sha(sha256)}"

    @staticmethod
    def _extract_digital_pages(pdf_path: Path) -> dict[int, str]:
        pages: dict[int, str] = {}
        with fitz.open(pdf_path) as doc:
            for page_index in range(len(doc)):
                text = str(doc.load_page(page_index).get_text("text") or "").strip()
                pages[page_index + 1] = text
        return pages

    @staticmethod
    def _load_manifest_if_exists(path: Path) -> OcrManifest | None:
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return OcrManifest.model_validate(payload)

    @staticmethod
    def _write_manifest(path: Path, manifest: OcrManifest) -> None:
        path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _write_pages_jsonl(path: Path, results: list[OcrPageResult]) -> None:
        lines = [json.dumps(result.to_dict(), ensure_ascii=False) for result in sorted(results, key=lambda item: item.page_number)]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    @staticmethod
    def _write_text_file(path: Path, results: list[OcrPageResult]) -> None:
        blocks: list[str] = []
        for result in sorted(results, key=lambda item: item.page_number):
            blocks.append(f"=== PAGE {result.page_number} ===\n{result.text.strip()}\n")
        path.write_text("\n".join(blocks), encoding="utf-8")

    @staticmethod
    def _write_errors_jsonl(path: Path, results: list[OcrPageResult]) -> None:
        failed = [result for result in results if result.status == OcrPageStatus.FAILED]
        lines = [json.dumps(result.to_dict(), ensure_ascii=False) for result in failed]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


async def process_many(
    processor: OcrProcessor,
    pdf_paths: list[Path],
    *,
    limit: int | None = None,
    workers: int = 5,
    dry_run: bool = False,
    force: bool = False,
    only_needs_ocr: bool = False,
) -> list[OcrManifest]:
    selected = pdf_paths[: limit if limit is not None else len(pdf_paths)]
    manifests: list[OcrManifest] = []
    for path in selected:
        classification = classify_pdf(path)
        if only_needs_ocr and not classification.needs_ocr:
            continue
        manifest = await processor.process_pdf(path, dry_run=dry_run, workers=workers, force=force)
        manifests.append(manifest)
        await asyncio.sleep(0)
    return manifests
