from pathlib import Path

from agenteperry.tdr.ingestion import load_manual_manifest


def test_load_manual_manifest_validates_required_columns(tmp_path: Path):
    manifest = tmp_path / "metadata.csv"
    manifest.write_text("title\nTDR demo\n", encoding="utf-8")

    try:
        load_manual_manifest(manifest)
    except ValueError as exc:
        assert "external_id" in str(exc)
        assert "entity_name" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_load_manual_manifest_reads_metadata(tmp_path: Path):
    manifest = tmp_path / "metadata.csv"
    manifest.write_text(
        "external_id,title,entity_name,source_url,file_url,publication_date,estimated_value\n"
        "tdr-1,TDR Demo,Municipalidad Demo,https://source.test,https://file.test/doc.pdf,2026-05-14,1200.50\n",
        encoding="utf-8",
    )

    records = load_manual_manifest(manifest)

    assert len(records) == 1
    assert records[0].external_id == "tdr-1"
    assert records[0].entity_name == "Municipalidad Demo"
    assert records[0].estimated_value == 1200.50
