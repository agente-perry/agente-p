"""Base collector for all data sources."""

from __future__ import annotations

import hashlib
import urllib.request
from abc import ABC, abstractmethod
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import structlog

from agenteperry.sources.catalog import SourceCatalogEntry

logger = structlog.get_logger()


class CollectionResult:
    """Result of a collection operation with full traceability."""

    def __init__(
        self,
        source_code: str,
        external_id: str | None = None,
        raw_data: dict[str, Any] | None = None,
        parsed_data: dict[str, Any] | None = None,
        raw_path: Path | None = None,
        checksum: str | None = None,
        content_type: str | None = None,
        record_type: str = "unknown",
        period_year: int | None = None,
        region: str | None = None,
        entity_name: str | None = None,
        entity_ruc: str | None = None,
        supplier_name: str | None = None,
        supplier_ruc: str | None = None,
        monto: float | None = None,
        fecha: date | None = None,
        source_url: str | None = None,
        page_number: int | None = None,
        evidence_quote: str | None = None,
    ) -> None:
        self.source_code = source_code
        self.external_id = external_id
        self.raw_data = raw_data or {}
        self.parsed_data = parsed_data or {}
        self.raw_path = raw_path
        self.checksum = checksum
        self.content_type = content_type
        self.record_type = record_type
        self.fetched_at = datetime.now(UTC)
        self.period_year = period_year
        self.region = region
        self.entity_name = entity_name
        self.entity_ruc = entity_ruc
        self.supplier_name = supplier_name
        self.supplier_ruc = supplier_ruc
        self.monto = monto
        self.fecha = fecha
        self.source_url = source_url
        self.page_number = page_number
        self.evidence_quote = evidence_quote

    def to_record(self) -> dict[str, Any]:
        """Convert to a dict ready for source_records table."""
        return {
            "source_code": self.source_code,
            "external_id": self.external_id,
            "raw_data": self.raw_data,
            "parsed_data": self.parsed_data,
            "raw_path": str(self.raw_path) if self.raw_path else None,
            "checksum": self.checksum,
            "content_type": self.content_type,
            "record_type": self.record_type,
            "fetched_at": self.fetched_at.isoformat(),
            "period_year": self.period_year,
            "region": self.region,
            "entity_name": self.entity_name,
            "entity_ruc": self.entity_ruc,
            "supplier_name": self.supplier_name,
            "supplier_ruc": self.supplier_ruc,
            "monto": self.monto,
            "fecha": self.fecha.isoformat() if self.fecha else None,
            "source_url": self.source_url,
            "page_number": self.page_number,
            "evidence_quote": self.evidence_quote,
        }


class BaseCollector(ABC):
    """Base class for all data collectors."""

    def __init__(self, source: SourceCatalogEntry) -> None:
        self.source = source
        self.logger = logger.bind(source_code=source.source_code)

    @abstractmethod
    def collect(self, *args: Any, **kwargs: Any) -> list[CollectionResult]:
        """Collect data from the source. Implement in subclasses."""
        ...

    @staticmethod
    def calculate_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def save_raw(data: bytes, directory: Path, filename: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        path.write_bytes(data)
        return path

    def download(self, url: str, download_dir: Path, filename: str | None = None) -> Path:
        """Download a public file using stdlib only and keep checksum traceability."""
        target_name = filename or url.rstrip("/").rsplit("/", 1)[-1] or "download.bin"
        target_path = download_dir / target_name
        download_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info("downloading_source_file", url=url, path=str(target_path))
        with urllib.request.urlopen(url, timeout=120) as response:
            target_path.write_bytes(response.read())
        return target_path


class BulkDownloadCollector(BaseCollector):
    """Collector for direct download sources (ZIP, JSONL.gz, CSV)."""

    def collect(self, *args: Any, **kwargs: Any) -> list[CollectionResult]:
        """Download bulk data. Override for specific source."""
        self.logger.info("starting_bulk_download", url=str(self.source.source_url))
        # Override in subclasses
        return []


class PlaywrightCollector(BaseCollector):
    """Collector for Playwright-based sources (SPA, XHR intercept)."""

    def collect(self, *args: Any, **kwargs: Any) -> list[CollectionResult]:
        """Scrape with Playwright. Override for specific source."""
        self.logger.info("starting_playwright_collection", url=str(self.source.source_url))
        # Override in subclasses
        return []


class CKANCollector(BaseCollector):
    """Collector for CKAN API sources."""

    def collect(self, *args: Any, **kwargs: Any) -> list[CollectionResult]:
        """Query CKAN API. Override for specific source."""
        self.logger.info("starting_ckan_collection", url=str(self.source.source_url))
        # Override in subclasses
        return []


class FormScrapingCollector(BaseCollector):
    """Collector for form-based scraping (ASP.NET, etc.)."""

    def collect(self, *args: Any, **kwargs: Any) -> list[CollectionResult]:
        """Scrape forms. Override for specific source."""
        self.logger.info("starting_form_scraping", url=str(self.source.source_url))
        # Override in subclasses
        return []
