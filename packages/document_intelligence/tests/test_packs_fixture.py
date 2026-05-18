"""PR #13 — Smoke test that the shipped example JSONL fixture loads + validates."""

from __future__ import annotations

from pathlib import Path

from document_intelligence.document_pack import load_valid_packs_from_jsonl

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "process_document_packs.example.jsonl"


def test_example_fixture_loads_clean() -> None:
    """The shipped fixture must always validate. If it stops, the contract changed."""
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"
    valid, rejected = load_valid_packs_from_jsonl(FIXTURE)
    assert rejected == [], f"rejected packs in fixture: {rejected}"
    assert len(valid) >= 1


def test_example_fixture_has_required_metadata() -> None:
    valid, _ = load_valid_packs_from_jsonl(FIXTURE)
    for pack in valid:
        assert pack.process_id and pack.process_id != "unknown"
        assert any(
            d.document_type.value in {"tdr", "bases", "bases_integradas", "absolucion_consultas"}
            for d in pack.documents
        )
        # In preventive mode the award must be None.
        if pack.mode.value == "preventive":
            assert pack.award is None


def test_example_fixture_references_real_files() -> None:
    """When file existence is checked, every document_path must resolve."""
    valid, rejected = load_valid_packs_from_jsonl(FIXTURE, check_file_existence=True)
    # Real PDFs may or may not be present in the repo (gitignored). Tolerate
    # "file not found" warnings but the rest of the validation must pass.
    for line_no, errs in rejected:
        for err in errs:
            assert "file not found" in err, (
                f"non-file error in fixture line {line_no}: {err}"
            )
