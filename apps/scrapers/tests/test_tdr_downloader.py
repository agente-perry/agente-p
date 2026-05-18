from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz

from agenteperry.tdr import downloader


def test_select_tdr_documents_prioritizes_bases_integradas_over_actas() -> None:
    documents = [
        {"title": "Acta de apertura de ofertas", "url": "https://example.test/a.pdf"},
        {"title": "Bases Integradas del proceso", "url": "https://example.test/b.pdf"},
        {"title": "Pliego de observaciones", "url": "https://example.test/c.pdf"},
    ]

    selected = downloader.select_tdr_documents(documents)

    assert selected
    assert selected[0]["title"] == "Bases Integradas del proceso"


def test_select_tdr_documents_pdf_only_excludes_archives() -> None:
    documents = [
        {"title": "Bases Integradas", "url": "https://example.test/a", "format": "rar"},
        {"title": "TDR", "url": "https://example.test/b", "format": "pdf"},
        {"title": "Bases Administrativas", "url": "https://example.test/c", "format": "zip"},
    ]

    selected = downloader.select_tdr_documents(documents, pdf_only=True)

    assert len(selected) == 1
    assert selected[0]["format"] == "pdf"


def test_safe_filename_normalizes_spanish_title() -> None:
    assert downloader.safe_filename("Términos de Referencia Nº 01/2026") == "terminos_de_referencia_no_01_2026"


def test_compute_sha256() -> None:
    value = downloader.compute_sha256(b"abc")
    assert value == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_download_document_mock(monkeypatch, tmp_path: Path) -> None:
    class FakeResponse:
        def __init__(self, content: bytes):
            self._content = content
            self.headers = {"Content-Type": "application/pdf"}

        def read(self) -> bytes:
            return self._content

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    def fake_urlopen(request: Any, timeout: int = 30) -> FakeResponse:  # noqa: ARG001
        return FakeResponse(b"%PDF-1.4 demo")

    monkeypatch.setattr(downloader, "urlopen", fake_urlopen)

    result = downloader.download_document("https://example.test/file", tmp_path / "doc", timeout=5, retries=1)

    assert result.status == "downloaded"
    assert result.output_path is not None
    assert result.output_path.exists()
    assert result.file_type == "pdf"
    assert result.checksum


def test_download_tdr_batch_respects_limit_and_max_docs(monkeypatch, tmp_path: Path) -> None:
    records = [
        {
            "ocid": "ocds-1",
            "entity": "Entidad A",
            "monto": 100.0,
            "fecha": "2025-01-01",
            "documents": [
                {"title": "Bases Integradas", "url": "https://example.test/a.pdf"},
                {"title": "TDR", "url": "https://example.test/b.pdf"},
            ],
        },
        {
            "ocid": "ocds-2",
            "entity": "Entidad B",
            "monto": 200.0,
            "fecha": "2025-01-02",
            "documents": [
                {"title": "Términos de referencia", "url": "https://example.test/c.pdf"},
            ],
        },
    ]
    input_jsonl = tmp_path / "input.jsonl"
    input_jsonl.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    class FakeDb:
        def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return []

    monkeypatch.setattr(downloader, "DbClient", lambda: FakeDb())

    def fake_download(  # noqa: ARG001
        url: str,
        output_path: Path,
        timeout: int = 30,
        retries: int = 3,
        declared_format: str | None = None,
    ) -> downloader.DownloadResult:
        output_path = output_path.with_suffix(".pdf")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-pdf")
        return downloader.DownloadResult(
            status="downloaded",
            checksum="abc123",
            content_type="application/pdf",
            file_type="pdf",
            error=None,
            output_path=output_path,
            bytes_written=8,
        )

    monkeypatch.setattr(downloader, "download_document", fake_download)

    payload = downloader.download_tdr_batch(
        input_jsonl=input_jsonl,
        sector="salud",
        limit=1,
        max_docs_per_contract=1,
        timeout=5,
        retries=1,
    )

    audit = payload["audit"]
    assert audit["total_contracts_seen"] == 1
    assert audit["documents_selected"] == 1
    assert audit["downloaded"] == 1
    assert len(payload["results"]) == 1


def test_download_tdr_batch_stops_when_usable(monkeypatch, tmp_path: Path) -> None:
    records = [
        {
            "ocid": "ocds-1",
            "documents": [{"title": "Bases Integradas", "url": "https://example.test/a.pdf", "format": "pdf"}],
        },
        {
            "ocid": "ocds-2",
            "documents": [{"title": "TDR", "url": "https://example.test/b.pdf", "format": "pdf"}],
        },
        {
            "ocid": "ocds-3",
            "documents": [{"title": "TDR", "url": "https://example.test/c.pdf", "format": "pdf"}],
        },
    ]
    input_jsonl = tmp_path / "input.jsonl"
    input_jsonl.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")

    class FakeDb:
        def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return []

    monkeypatch.setattr(downloader, "DbClient", lambda: FakeDb())

    def fake_download(  # noqa: ARG001
        url: str,
        output_path: Path,
        timeout: int = 30,
        retries: int = 3,
        declared_format: str | None = None,
    ) -> downloader.DownloadResult:
        path = output_path.with_suffix(".pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-pdf")
        return downloader.DownloadResult("downloaded", "abc123", "application/pdf", "pdf", None, path, 8)

    def fake_inspect(path: Path) -> dict[str, Any]:
        is_usable = "ocds_2" in str(path)
        return {
            "path": str(path),
            "total_pages": 1,
            "pages_with_text": 1 if is_usable else 0,
            "pages_needs_ocr": 0 if is_usable else 1,
            "coverage_pct": 100.0 if is_usable else 0.0,
            "tdr_status": "available" if is_usable else "needs_ocr",
            "is_usable": is_usable,
        }

    monkeypatch.setattr(downloader, "download_document", fake_download)
    monkeypatch.setattr(downloader, "inspect_pdf_text_layer", fake_inspect)
    monkeypatch.setattr(downloader, "time", type("FakeTime", (), {"sleep": staticmethod(lambda seconds: None)}))

    payload = downloader.download_tdr_batch(
        input_jsonl=input_jsonl,
        sector="salud",
        limit=30,
        max_docs_per_contract=1,
        pdf_only=True,
        stop_when_usable=1,
        download_root=tmp_path / "tdrs",
    )

    audit = payload["audit"]
    assert audit["attempted_downloads"] == 2
    assert audit["needs_ocr_count"] == 1
    assert audit["usable_found"] == 1
    assert audit["stopped_early"] is True
    assert len(payload["results"]) == 2


def test_download_tdr_batch_skip_existing(monkeypatch, tmp_path: Path) -> None:
    records = [
        {
            "ocid": "ocds-existing",
            "documents": [{"title": "TDR", "url": "https://example.test/a.pdf", "format": "pdf"}],
        }
    ]
    input_jsonl = tmp_path / "input.jsonl"
    input_jsonl.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    existing = tmp_path / "tdrs" / "salud" / "ocds_existing" / "tdr.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    class FakeDb:
        def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:  # noqa: ARG002
            return []

    monkeypatch.setattr(downloader, "DbClient", lambda: FakeDb())

    payload = downloader.download_tdr_batch(
        input_jsonl=input_jsonl,
        sector="salud",
        limit=1,
        max_docs_per_contract=1,
        pdf_only=True,
        skip_existing=True,
        download_root=tmp_path / "tdrs",
    )

    audit = payload["audit"]
    assert audit["attempted_downloads"] == 0
    assert audit["skipped_existing"] == 1
    assert payload["results"][0]["status"] == "skipped_existing"


def test_inspect_pdf_text_layer_available(tmp_path: Path) -> None:
    pdf_path = tmp_path / "text.pdf"
    _write_pdf(pdf_path, ["Texto digital usable para el parser de TDR. " * 4])

    result = downloader.inspect_pdf_text_layer(pdf_path)

    assert result["tdr_status"] == "available"
    assert result["is_usable"] is True
    assert result["pages_with_text"] == 1


def test_inspect_pdf_text_layer_needs_ocr(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    _write_pdf(pdf_path, [""])

    result = downloader.inspect_pdf_text_layer(pdf_path)

    assert result["tdr_status"] == "needs_ocr"
    assert result["is_usable"] is False
    assert result["pages_needs_ocr"] == 1


def test_inspect_pdf_text_layer_partial_threshold(tmp_path: Path) -> None:
    pdf_path = tmp_path / "partial.pdf"
    pages = ["Texto digital usable para el parser de TDR. " * 4] + [""] * 9
    _write_pdf(pdf_path, pages)

    result = downloader.inspect_pdf_text_layer(pdf_path)

    assert result["tdr_status"] == "partial"
    assert result["coverage_pct"] == 10.0


def test_audit_pdf_usability_marks_archives_pending(tmp_path: Path) -> None:
    base = tmp_path / "tdrs"
    sector_dir = base / "salud" / "ocds_1"
    sector_dir.mkdir(parents=True)
    _write_pdf(sector_dir / "text.pdf", ["Texto digital usable para el parser de TDR. " * 4])
    (sector_dir / "archive.zip").write_bytes(b"zip")
    (sector_dir / "archive.rar").write_bytes(b"rar")

    audit = downloader.audit_pdf_usability(base)

    assert audit["pdf_files"] == 1
    assert audit["pdf_available"] == 1
    assert audit["archives_pending"] == 2


def test_audit_pdf_usability_recommends_highest_coverage(tmp_path: Path) -> None:
    base = tmp_path / "tdrs"
    sector_dir = base / "salud" / "ocds_1"
    sector_dir.mkdir(parents=True)
    _write_pdf(sector_dir / "low.pdf", ["Texto digital usable para el parser de TDR. " * 4] + [""])
    _write_pdf(sector_dir / "high.pdf", ["Texto digital usable para el parser de TDR. " * 4])

    audit = downloader.audit_pdf_usability(base)

    assert audit["recommended_for_golden_set"][0]["path"].endswith("high.pdf")


def _write_pdf(path: Path, page_texts: list[str]) -> None:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text)
    document.save(path)
    document.close()
