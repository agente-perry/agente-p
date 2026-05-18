from __future__ import annotations

from pathlib import Path
from typing import Any

from agenteperry.radar.cdc import (
    build_changeset,
    compute_record_hash,
    detect_change,
    load_hash_index,
    save_hash_index,
)
from agenteperry.radar.models import ChangeType


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "source_code": "ocds_peru",
        "external_id": "ocds-1:A-1",
        "record_type": "contract",
        "parsed_data": {"ocid": "ocds-1", "award_id": "A-1"},
        "monto": 1000.0,
        "fecha": "2026-01-01",
        "supplier_ruc": "20987654321",
        "entity_ruc": "20123456789",
        "documents": [{"id": "doc-1", "url": "https://example.test/doc.pdf"}],
    }
    record.update(overrides)
    return record


def test_compute_record_hash_is_stable() -> None:
    assert compute_record_hash(_record()) == compute_record_hash(_record())


def test_compute_record_hash_changes_when_parsed_data_changes() -> None:
    before = compute_record_hash(_record())
    after = compute_record_hash(_record(parsed_data={"ocid": "ocds-1", "award_id": "A-2"}))
    assert before != after


def test_detect_change_new_changed_unchanged() -> None:
    assert detect_change(None, "abc") == ChangeType.NEW
    assert detect_change("abc", "def") == ChangeType.CHANGED
    assert detect_change("abc", "abc") == ChangeType.UNCHANGED


def test_build_changeset_counts_new_changed_unchanged() -> None:
    unchanged = _record(external_id="same")
    changed = _record(external_id="changed", monto=1200.0)
    new = _record(external_id="new")
    existing_index = {
        "ocds_peru:same": compute_record_hash(unchanged),
        "ocds_peru:changed": compute_record_hash(_record(external_id="changed", monto=1000.0)),
    }

    changes = build_changeset("ocds_peru", "run-1", [unchanged, changed, new], existing_index)

    assert changes.records_seen == 3
    assert changes.records_new == 1
    assert changes.records_changed == 1
    assert changes.records_unchanged == 1
    assert changes.records_failed == 0
    assert [record.external_id for record in changes.changed_records] == ["ocds_peru:changed", "ocds_peru:new"]


def test_build_changeset_marks_missing_external_id_and_checksum_as_failed() -> None:
    changes = build_changeset("ocds_peru", "run-1", [{"source_code": "ocds_peru"}], {})

    assert changes.records_seen == 1
    assert changes.records_failed == 1
    assert changes.failed_records[0].change_type == ChangeType.FAILED


def test_hash_index_round_trip(tmp_path: Path) -> None:
    saved_path = save_hash_index("ocds_peru", {"ocds_peru:1": "abc"}, base_dir=tmp_path)

    assert saved_path == tmp_path / "ocds_peru" / "hashes.json"
    assert load_hash_index("ocds_peru", base_dir=tmp_path) == {"ocds_peru:1": "abc"}
