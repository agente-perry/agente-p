"""Generic hash-based CDC for any AgentePerry source record."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from agenteperry.radar.models import ChangedRecord, ChangeSet, ChangeType


def canonical_json(value: Any) -> str:
    """Return a stable JSON representation for hashing and audit output."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def compute_record_hash(record: dict[str, Any]) -> str:
    """Compute a stable normalized hash for CDC.

    Avoid hashing all ``raw_data`` because source payloads often contain
    publication timestamps and large nested structures. The selected fields are
    enough to catch operational changes while keeping daily runs stable.
    """
    documents: Any = record.get("documents")
    raw_data = record.get("raw_data")
    if documents is None and isinstance(raw_data, dict):
        raw_dict = cast(dict[str, Any], raw_data)
        tender = raw_dict.get("tender")
        contracts = raw_dict.get("contracts")
        tender_documents: list[Any] = []
        if isinstance(tender, dict):
            tender_dict = cast(dict[str, Any], tender)
            tender_docs = tender_dict.get("documents")
            if isinstance(tender_docs, list):
                tender_documents = cast(list[Any], tender_docs)
        contract_documents: list[Any] = []
        if isinstance(contracts, list):
            for contract_item in cast(list[Any], contracts):
                if isinstance(contract_item, dict):
                    contract = cast(dict[str, Any], contract_item)
                    contract_docs = contract.get("documents")
                    if isinstance(contract_docs, list):
                        contract_documents.extend(cast(list[Any], contract_docs))
        documents = cast(dict[str, Any], {
            "tender": tender_documents or [],
            "contracts": contract_documents,
        })

    hash_payload: dict[str, Any] = {
        "external_id": record.get("external_id"),
        "record_type": record.get("record_type"),
        "parsed_data": record.get("parsed_data") or {},
        "monto": record.get("monto"),
        "fecha": record.get("fecha"),
        "supplier_ruc": record.get("supplier_ruc") or record.get("proveedor_ruc"),
        "entity_ruc": record.get("entity_ruc"),
        "documents": documents or [],
    }
    return hashlib.sha256(canonical_json(hash_payload).encode("utf-8")).hexdigest()


def detect_change(existing_hash: str | None, new_hash: str) -> ChangeType:
    """Classify a record by comparing old and new normalized hashes."""
    if existing_hash is None:
        return ChangeType.NEW
    if existing_hash != new_hash:
        return ChangeType.CHANGED
    return ChangeType.UNCHANGED


def build_changeset(
    source_code: str,
    run_id: str,
    records: Iterable[dict[str, Any]],
    existing_index: dict[str, str],
) -> ChangeSet:
    """Build a CDC changeset using ``source_code + external_id`` as key."""
    changes = ChangeSet(source_code=source_code, run_id=run_id)
    detected_at = datetime.now(UTC).isoformat()

    for record in records:
        changes.records_seen += 1
        external_id = _record_external_id(record)
        if not external_id:
            failed = ChangedRecord(
                source_code=source_code,
                external_id=None,
                change_type=ChangeType.FAILED,
                record=record,
                previous_hash=None,
                current_hash=None,
                detected_at=detected_at,
                error="Missing external_id and checksum",
            )
            changes.records_failed += 1
            changes.failed_records.append(failed)
            continue

        current_hash = compute_record_hash(record)
        previous_hash = existing_index.get(external_id)
        change_type = detect_change(previous_hash, current_hash)
        changed_record = ChangedRecord(
            source_code=source_code,
            external_id=external_id,
            change_type=change_type,
            record=record,
            previous_hash=previous_hash,
            current_hash=current_hash,
            detected_at=detected_at,
        )

        if change_type == ChangeType.NEW:
            changes.records_new += 1
            changes.changed_records.append(changed_record)
        elif change_type == ChangeType.CHANGED:
            changes.records_changed += 1
            changes.changed_records.append(changed_record)
        else:
            changes.records_unchanged += 1

    return changes


def load_hash_index(source_code: str, base_dir: Path = Path("data/runs")) -> dict[str, str]:
    """Load the persisted CDC hash index for one source."""
    path = _hash_index_path(source_code, base_dir)
    if not path.exists():
        return {}
    try:
        payload = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    payload_dict = cast(dict[Any, Any], payload)
    return {str(key): str(value) for key, value in payload_dict.items()}


def save_hash_index(source_code: str, hashes: dict[str, str], base_dir: Path = Path("data/runs")) -> Path:
    """Persist the CDC hash index for one source and return its path."""
    path = _hash_index_path(source_code, base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def updated_hash_index(existing_index: dict[str, str], changes: ChangeSet) -> dict[str, str]:
    """Return a new index including all successful changed/new records."""
    updated = dict(existing_index)
    for record in changes.changed_records:
        if record.external_id and record.current_hash:
            updated[record.external_id] = record.current_hash
    return updated


def _record_external_id(record: dict[str, Any]) -> str | None:
    external_id = record.get("external_id")
    if external_id:
        return f"{record.get('source_code') or ''}:{external_id}"
    checksum = record.get("checksum")
    if checksum:
        return f"{record.get('source_code') or ''}:checksum:{checksum}"
    return None


def _hash_index_path(source_code: str, base_dir: Path) -> Path:
    return base_dir / source_code / "hashes.json"
