from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from agenteperry.ocr.minimax_client import MinimaxOCRClient
from agenteperry.ocr.models import OcrDocumentStatus, OcrPageResult, OcrPageStatus
from agenteperry.ocr.processor import OcrProcessor


def _make_pdf(path: Path, page_texts: list[str]) -> Path:
    doc = fitz.open()
    for text in page_texts:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()
    return path


class FakeClient(MinimaxOCRClient):
    def __init__(self, *, fail_pages: set[int] | None = None) -> None:
        super().__init__(api_key="test", api_base="http://fake", model="fake")
        self.calls: list[list[int]] = []
        self.fail_pages = fail_pages or set()

    async def ocr_pdf_pages(self, pdf_path: Path, pages: list[int] | None = None, workers: int = 5) -> list[OcrPageResult]:
        target = pages or []
        self.calls.append(target)
        results: list[OcrPageResult] = []
        for page in target:
            if page in self.fail_pages:
                results.append(
                    OcrPageResult(
                        page_number=page,
                        status=OcrPageStatus.FAILED,
                        text="",
                        text_length=0,
                        provider="fake",
                        model="fake",
                        latency_ms=1,
                        error="boom",
                    )
                )
            else:
                text = f"ocr page {page}"
                results.append(
                    OcrPageResult(
                        page_number=page,
                        status=OcrPageStatus.OK,
                        text=text,
                        text_length=len(text),
                        provider="fake",
                        model="fake",
                        latency_ms=1,
                        error=None,
                    )
                )
        return results


@pytest.mark.asyncio
async def test_dry_run_does_not_call_client(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scan.pdf", ["", ""])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf, dry_run=True)

    assert manifest.status == OcrDocumentStatus.SKIPPED
    assert client.calls == []
    assert (Path(manifest.output_dir) / "ocr_manifest.json").exists()


@pytest.mark.asyncio
async def test_textual_pdf_generates_text_without_ocr_call(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "text.pdf", ["x" * 120, "y" * 120])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf)

    assert manifest.status == OcrDocumentStatus.COMPLETED
    assert manifest.pages_attempted == 0
    assert client.calls == []
    text_path = Path(manifest.output_dir) / "ocr_text.txt"
    assert text_path.exists()
    assert "PAGE 1" in text_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_scanned_pdf_calls_client(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scan.pdf", ["", "", ""])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf)

    assert manifest.pages_attempted == 3
    assert client.calls == [[1, 2, 3]]
    assert (Path(manifest.output_dir) / "ocr_pages.jsonl").exists()


@pytest.mark.asyncio
async def test_mixed_pdf_ocr_only_missing_pages(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "mixed.pdf", ["x" * 120, "", "short"])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf)

    assert manifest.pages_attempted == 2
    assert client.calls == [[2, 3]]


@pytest.mark.asyncio
async def test_manifest_and_pages_written(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scan.pdf", ["", ""])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf)
    out_dir = Path(manifest.output_dir)

    assert (out_dir / "ocr_manifest.json").exists()
    assert (out_dir / "ocr_pages.jsonl").exists()
    payload = json.loads((out_dir / "ocr_manifest.json").read_text(encoding="utf-8"))
    assert payload["document_id"] == manifest.document_id


@pytest.mark.asyncio
async def test_idempotency_skip_then_force(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scan.pdf", ["", ""])
    client = FakeClient()
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    first = await processor.process_pdf(pdf_path=pdf)
    second = await processor.process_pdf(pdf_path=pdf)
    third = await processor.process_pdf(pdf_path=pdf, force=True)

    assert first.status == OcrDocumentStatus.COMPLETED
    assert second.status == OcrDocumentStatus.SKIPPED
    assert third.status in (OcrDocumentStatus.COMPLETED, OcrDocumentStatus.COMPLETED_WITH_ERRORS)
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_page_errors_generate_completed_with_errors(tmp_path: Path) -> None:
    pdf = _make_pdf(tmp_path / "scan.pdf", ["", "", ""])
    client = FakeClient(fail_pages={2})
    processor = OcrProcessor(output_base_dir=tmp_path / "out", client=client)

    manifest = await processor.process_pdf(pdf_path=pdf)
    out_dir = Path(manifest.output_dir)

    assert manifest.status == OcrDocumentStatus.COMPLETED_WITH_ERRORS
    assert manifest.pages_failed == 1
    assert (out_dir / "ocr_errors.jsonl").exists()
