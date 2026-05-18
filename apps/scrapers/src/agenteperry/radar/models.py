"""Data models for the incremental scraping radar."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ChangeType(StrEnum):
    """CDC classification for one source record."""

    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True)
class ChangedRecord:
    """A source record classified by generic CDC."""

    source_code: str
    external_id: str | None
    change_type: ChangeType
    record: dict[str, Any]
    previous_hash: str | None
    current_hash: str | None
    detected_at: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChangeSet:
    """CDC summary for a radar run."""

    source_code: str
    run_id: str
    records_seen: int = 0
    records_new: int = 0
    records_changed: int = 0
    records_unchanged: int = 0
    records_failed: int = 0
    changed_records: list[ChangedRecord] = field(default_factory=lambda: [])
    failed_records: list[ChangedRecord] = field(default_factory=lambda: [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_code": self.source_code,
            "run_id": self.run_id,
            "records_seen": self.records_seen,
            "records_new": self.records_new,
            "records_changed": self.records_changed,
            "records_unchanged": self.records_unchanged,
            "records_failed": self.records_failed,
            "changed_records": [record.to_dict() for record in self.changed_records],
            "failed_records": [record.to_dict() for record in self.failed_records],
        }


@dataclass
class SourceRun:
    """Auditable metadata for one source radar run."""

    run_id: str
    source_code: str
    mode: str
    status: str
    started_at: str
    finished_at: str | None = None
    records_seen: int = 0
    records_new: int = 0
    records_changed: int = 0
    records_unchanged: int = 0
    records_failed: int = 0
    documents_discovered: int = 0
    documents_downloaded: int = 0
    pdf_available: int = 0
    pdf_needs_ocr: int = 0
    dossiers_generated: int = 0
    errors: list[str] = field(default_factory=lambda: [])
    warnings: list[str] = field(default_factory=lambda: [])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RadarRunResult:
    """Return value for radar orchestration."""

    source_run: SourceRun
    changes: ChangeSet
    audit_path: Path
    changed_records_path: Path
    hashes_path: Path


@dataclass(frozen=True)
class SourceHealthCheck:
    """Lightweight source health report."""

    source_code: str
    checked_at: str
    status: str
    url_reachable: bool | None
    local_data_exists: bool | None
    schema_valid: bool | None
    last_audit_exists: bool | None
    error: str | None = None
    details: dict[str, Any] = field(default_factory=lambda: {})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
