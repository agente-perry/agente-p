# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Hash-based Change Data Capture detector for SEACE/OCDS records.

Detects NEW and MODIFIED contracts without scraping SEACE.
Works entirely from local JSONL files + a persistent hash registry.
No database connection required.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Priority configuration
# ---------------------------------------------------------------------------

PRIORITY_KEYWORDS_SALUD = (
    "MINSA", "MINISTERIO DE SALUD", "DIRESA", "RED DE SALUD",
    "HOSPITAL", "CENTRO DE SALUD", "ESSALUD", "SEGURO SOCIAL",
    "CENARES", "INSTITUTO NACIONAL DE SALUD", "INSN", "INS",
)

PRIORITY_KEYWORDS_AMBIENTE = (
    "MINAM", "MINISTERIO DEL AMBIENTE", "OEFA", "ANA",
    "AUTORIDAD NACIONAL DEL AGUA", "SERNANP", "SENACE",
    "INGEMMET", "REGIONAL AMBIENTAL", "GERENCIA AMBIENTAL",
)

SECTOR_KEYWORDS: dict[str, tuple[str, ...]] = {
    "salud": PRIORITY_KEYWORDS_SALUD,
    "ambiente": PRIORITY_KEYWORDS_AMBIENTE,
}

ALL_PRIORITY_KEYWORDS: tuple[str, ...] = PRIORITY_KEYWORDS_SALUD + PRIORITY_KEYWORDS_AMBIENTE


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChangeEvent:
    """A detected new or modified contract record."""

    ocid: str
    change_type: str           # "new" | "modified"
    is_priority: bool
    sector: str                # "salud" | "ambiente" | "otros"
    record: Mapping[str, Any]
    previous_hash: str | None
    current_hash: str
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------

def compute_record_hash(record: Mapping[str, Any]) -> str:
    """Deterministic SHA-256 hash of key contract fields.

    If any of these fields change in a subsequent OCDS snapshot
    (amount, date, supplier, modality, status), we detect a modification.
    """
    key_fields: dict[str, str] = {
        "ocid": str(record.get("ocid") or ""),
        "monto": str(record.get("monto") or record.get("amount") or ""),
        "fecha": str(record.get("fecha") or record.get("contract_date") or "")[:10],
        "proveedor_ruc": str(
            record.get("proveedor_ruc")
            or record.get("supplier_ruc")
            or ""
        ),
        "modalidad": str(
            record.get("modalidad")
            or record.get("procedure_type")
            or (record.get("parsed_data") or {}).get("procedure_type")
            or ""
        ),
    }
    canonical = json.dumps(key_fields, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Sector / priority helpers
# ---------------------------------------------------------------------------

def detect_sector(record: Mapping[str, Any]) -> str:
    """Classify a record into sector: salud | ambiente | otros."""
    name = _buyer_name(record)
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            return sector
    return "otros"


def is_priority(record: Mapping[str, Any]) -> bool:
    """True if the record belongs to a priority sector."""
    name = _buyer_name(record)
    return any(kw in name for kw in ALL_PRIORITY_KEYWORDS)


def _buyer_name(record: Mapping[str, Any]) -> str:
    """Extract and normalise the buyer name from any record shape."""
    raw = (
        record.get("entity")
        or record.get("entity_name")
        or record.get("buyer_name")
        or ""
    )
    return str(raw).upper()


# ---------------------------------------------------------------------------
# Hash registry (local JSON file — no DB required)
# ---------------------------------------------------------------------------

def load_known_hashes(hash_file: Path) -> dict[str, str]:
    """Load {ocid: hash} registry from a local JSON file."""
    if not hash_file.exists():
        return {}
    try:
        data = json.loads(hash_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return {}
def save_known_hashes(hashes: dict[str, str], hash_file: Path) -> None:
    """Persist {ocid: hash} registry to a local JSON file."""
    hash_file.parent.mkdir(parents=True, exist_ok=True)
    hash_file.write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Detector
# ---------------------------------------------------------------------------

class SEACEChangeDetector:
    """Hash-based incremental change detector for OCDS contract records.

    On first run — all records are ``new``.
    On subsequent runs — only records whose key fields changed are emitted
    as ``modified``; unchanged records are skipped silently.

    The hash registry lives in a local JSON file so no database is needed.

    Usage::

        detector = SEACEChangeDetector(hash_file=Path("data/cdc/hashes.json"))
        for change in detector.detect_changes(records):
            print(change.ocid, change.change_type)
        detector.commit()  # persist updated hashes
    """

    def __init__(self, hash_file: Path) -> None:
        self._hash_file = hash_file
        self._known: dict[str, str] = load_known_hashes(hash_file)
        self._updated: dict[str, str] = dict(self._known)

    # ------------------------------------------------------------------
    # Core algorithm
    # ------------------------------------------------------------------

    def detect_changes(
        self,
        records: list[Mapping[str, Any]],
        *,
        sector_filter: str | None = None,
        priority_only: bool = False,
    ) -> Iterator[ChangeEvent]:
        """Yield ChangeEvent for every new or modified record.

        Args:
            records: OCDS-compatible records from JSONL or DB.
            sector_filter: if set, only yield events for this sector
                           ("salud" | "ambiente" | "otros").
            priority_only: if True, only yield priority-sector contracts.
        """
        for record in records:
            ocid = str(record.get("ocid") or record.get("external_id") or "").strip()
            if not ocid:
                continue

            current_hash = compute_record_hash(record)
            previous_hash = self._known.get(ocid)

            if previous_hash is None:
                change_type = "new"
            elif previous_hash != current_hash:
                change_type = "modified"
            else:
                continue  # No change — skip

            sector = detect_sector(record)
            priority = is_priority(record)

            # Apply filters
            if sector_filter and sector != sector_filter:
                continue
            if priority_only and not priority:
                continue

            # Stage update (not committed yet)
            self._updated[ocid] = current_hash

            yield ChangeEvent(
                ocid=ocid,
                change_type=change_type,
                is_priority=priority,
                sector=sector,
                record=record,
                previous_hash=previous_hash,
                current_hash=current_hash,
            )

    def commit(self) -> None:
        """Persist all detected changes to the hash registry file."""
        save_known_hashes(self._updated, self._hash_file)
        # Sync _known so total_known reflects the persisted state
        self._known = dict(self._updated)

    def reset(self) -> None:
        """Clear the hash registry (next run will treat all as new)."""
        self._known = {}
        self._updated = {}
        save_known_hashes({}, self._hash_file)

    # ------------------------------------------------------------------
    # Metrics helpers
    # ------------------------------------------------------------------

    @property
    def total_known(self) -> int:
        """Number of contracts currently in the hash registry."""
        return len(self._known)

    @property
    def total_updated(self) -> int:
        """Number of contracts that will be in the registry after commit."""
        return len(self._updated)

    def get_known_hash(self, ocid: str) -> str | None:
        """Return the stored hash for an OCID, or None if not seen before."""
        return self._known.get(ocid)
