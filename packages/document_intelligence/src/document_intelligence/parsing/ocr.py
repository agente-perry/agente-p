"""Optional OCR adapter layer for scanned PDFs.

Design rules
------------

- The package must run with **no OCR dependencies installed**. Importing this
  module never raises.
- ``NoopOCRAdapter`` is always available and used when ``ocr_mode='off'`` or
  when the chosen real adapter is unavailable.
- ``TesseractOCRAdapter`` is best-effort: it probes both ``pytesseract`` and
  the system ``tesseract`` binary at construction. If either is missing it
  reports ``available=False`` with a structured ``unavailable_reason`` and
  every page OCR returns an ``OCRResult`` with ``applied=False`` plus the
  same error string. Callers get a clean signal, never a stacktrace.
- Adapters are stateless beyond availability + config so they can be swapped
  for a deterministic ``FakeOCRAdapter`` in tests without touching production
  code.
"""
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

OCRMode = Literal["off", "auto", "force"]


@dataclass(frozen=True)
class OCRResult:
    """Outcome of a single page OCR attempt."""

    text: str
    applied: bool
    error: str | None = None


@runtime_checkable
class BaseOCRAdapter(Protocol):
    """Minimal OCR adapter contract."""

    @property
    def name(self) -> str:
        ...

    @property
    def available(self) -> bool:
        ...

    @property
    def unavailable_reason(self) -> str | None:
        ...

    def ocr_page(self, pdf_path: Path, page_number: int) -> OCRResult:
        ...


class NoopOCRAdapter:
    """OCR adapter that does nothing. Always available; never produces text."""

    name: str = "noop"

    @property
    def available(self) -> bool:
        return False

    @property
    def unavailable_reason(self) -> str | None:
        return "OCR adapter disabled (noop)"

    def ocr_page(self, pdf_path: Path, page_number: int) -> OCRResult:  # noqa: ARG002
        return OCRResult(text="", applied=False, error=self.unavailable_reason)


class TesseractOCRAdapter:
    """OCR adapter backed by ``pytesseract`` + system ``tesseract`` binary.

    Construction is non-destructive: if either dependency is missing the
    adapter is constructed in an *unavailable* state and every ``ocr_page``
    call returns an ``OCRResult`` with ``applied=False`` and a structured
    error message. The package therefore runs cleanly without OCR installed.
    """

    name: str = "tesseract"

    def __init__(self, *, lang: str = "spa", dpi: int = 200) -> None:
        self._lang = lang
        self._dpi = dpi
        self._pytesseract = None
        self._fitz = None
        self._pil_image = None
        self._available = False
        self._unavailable_reason: str | None = None
        try:
            import pytesseract  # type: ignore[import-not-found]

            version = pytesseract.get_tesseract_version()
            self._pytesseract = pytesseract
            self._version = str(version)
        except ImportError:
            self._unavailable_reason = "pytesseract not installed"
            return
        except Exception as exc:  # noqa: BLE001
            self._unavailable_reason = f"tesseract binary not available: {exc}"
            return
        try:
            import fitz  # type: ignore[import-not-found]

            self._fitz = fitz
        except ImportError:
            self._unavailable_reason = "pymupdf (fitz) not installed"
            return
        try:
            from PIL import Image  # type: ignore[import-not-found]

            self._pil_image = Image
        except ImportError:
            self._unavailable_reason = "Pillow not installed"
            return
        self._available = True

    @property
    def available(self) -> bool:
        return self._available

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable_reason

    def ocr_page(self, pdf_path: Path, page_number: int) -> OCRResult:
        if not self._available:
            return OCRResult(text="", applied=False, error=self._unavailable_reason)
        try:
            import io

            with self._fitz.open(pdf_path) as doc:  # type: ignore[union-attr]
                if page_number < 1 or page_number > len(doc):
                    return OCRResult(
                        text="",
                        applied=False,
                        error=f"page {page_number} out of range",
                    )
                page = doc.load_page(page_number - 1)
                pix = page.get_pixmap(dpi=self._dpi)
                png_bytes = pix.tobytes("png")
            image = self._pil_image.open(io.BytesIO(png_bytes))  # type: ignore[union-attr]
            text = self._pytesseract.image_to_string(image, lang=self._lang)  # type: ignore[union-attr]
            text = (text or "").strip()
            return OCRResult(text=text, applied=True)
        except Exception as exc:  # noqa: BLE001 — surface structured error
            return OCRResult(text="", applied=False, error=str(exc))


def get_default_ocr_adapter() -> BaseOCRAdapter:
    """Return the canonical Tesseract adapter.

    The instance is always returned even when the binary or ``pytesseract``
    are missing — callers should inspect ``available`` and
    ``unavailable_reason`` instead of switching on the concrete class.
    Returning the failing Tesseract (rather than ``NoopOCRAdapter``) preserves
    the actionable error message (``tesseract is not installed or it's not in
    your PATH``) so operators know what to fix.

    Use ``NoopOCRAdapter()`` explicitly when you want to opt out of OCR
    altogether (e.g. in tests).
    """
    return TesseractOCRAdapter()
