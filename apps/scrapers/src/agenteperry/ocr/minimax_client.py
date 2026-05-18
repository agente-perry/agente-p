# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""MiniMax OCR client with mockable API boundary."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Any

import fitz

from agenteperry.ocr.models import OcrPageResult, OcrPageStatus


class MinimaxOCRClient:
    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.api_key = (api_key or os.environ.get("MINIMAX_API_KEY") or "").strip()
        self.api_base = (api_base or os.environ.get("MINIMAX_API_BASE") or "https://api.minimax.chat/v1").strip()
        self.model = (model or os.environ.get("MINIMAX_OCR_MODEL") or "MiniCPM-v2").strip()
        self.timeout = timeout
        self.provider = "minimax"

    def _ensure_api_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("MINIMAX_API_KEY not configured. Set environment variable before OCR run.")

    @staticmethod
    def _pdf_page_to_image(pdf_path: Path, page_number: int, dpi: int = 150) -> bytes:
        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_number - 1)
            matrix = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            return pix.tobytes("png")

    async def _call_api(self, image_bytes: bytes) -> str:
        self._ensure_api_key()
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}"},
                        },
                        {
                            "type": "text",
                            "text": "Extract all visible text from this page. Preserve line breaks.",
                        },
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": 4096,
        }

        def _request() -> str:
            req = urllib.request.Request(
                f"{self.api_base.rstrip('/')}/v1/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "AgentePerry-OCR/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
            decoded: dict[str, Any] = json.loads(raw)
            choices = decoded.get("choices") or []
            if not choices:
                return ""
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if isinstance(content, list):
                text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
                return "\n".join(text_parts).strip()
            return str(content).strip()

        return await asyncio.to_thread(_request)

    async def ocr_page_image(self, image_bytes: bytes, page_number: int) -> OcrPageResult:
        start = time.perf_counter()
        try:
            text = await self._call_api(image_bytes)
            latency = int((time.perf_counter() - start) * 1000)
            return OcrPageResult(
                page_number=page_number,
                status=OcrPageStatus.OK,
                text=text,
                text_length=len(text),
                provider=self.provider,
                model=self.model,
                latency_ms=latency,
                error=None,
            )
        except Exception as exc:
            latency = int((time.perf_counter() - start) * 1000)
            return OcrPageResult(
                page_number=page_number,
                status=OcrPageStatus.FAILED,
                text="",
                text_length=0,
                provider=self.provider,
                model=self.model,
                latency_ms=latency,
                error=str(exc),
            )

    async def ocr_pdf_pages(
        self,
        pdf_path: Path,
        pages: list[int] | None = None,
        workers: int = 5,
    ) -> list[OcrPageResult]:
        path = pdf_path.resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        self._ensure_api_key()

        with fitz.open(path) as doc:
            total = len(doc)
        target_pages = pages[:] if pages else list(range(1, total + 1))
        target_pages = sorted({p for p in target_pages if 1 <= p <= total})
        sem = asyncio.Semaphore(max(workers, 1))

        async def _ocr_page(page_number: int) -> OcrPageResult:
            async with sem:
                try:
                    image_bytes = await asyncio.to_thread(self._pdf_page_to_image, path, page_number)
                except Exception as exc:
                    return OcrPageResult(
                        page_number=page_number,
                        status=OcrPageStatus.FAILED,
                        text="",
                        text_length=0,
                        provider=self.provider,
                        model=self.model,
                        latency_ms=None,
                        error=f"render_failed: {exc}",
                    )
                return await self.ocr_page_image(image_bytes, page_number)

        tasks = [asyncio.create_task(_ocr_page(page_number)) for page_number in target_pages]
        results = await asyncio.gather(*tasks)
        return sorted(results, key=lambda item: item.page_number)
