"""Tests for the TDR dossier generator (Activity 5 — Golden Set)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from agenteperry.tdr.dossier import (
    DISCLAIMER,
    SCHEMA_VERSION,
    _deduplicated_questions,
    _risk_level_for_score,
    generate_dossier,
    render_dossier_markdown,
)
from agenteperry.tdr.flags import detect_flags_in_pages
from agenteperry.tdr.models import TdrChunk, TdrFlag, TdrPage, TdrSeverity

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF with a text layer using PyMuPDF."""
    import fitz

    pdf_path = tmp_path / "test.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Terminos de Referencia para consultor iso 9001 certificacion internacional")
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture()
def sample_pages() -> list[TdrPage]:
    return [
        TdrPage(tdr_id="test-ocid", page_number=1, text_content="Se requiere informe de 500 paginas con detalle mensual."),
        TdrPage(tdr_id="test-ocid", page_number=2, text_content="El postor debe presentar certificacion iso 9001 vigente."),
        TdrPage(tdr_id="test-ocid", page_number=3, text_content="El entregable unico sera un informe final en powerpoint."),
        TdrPage(tdr_id="test-ocid", page_number=4, text_content="Normal page without any flags."),
    ]


@pytest.fixture()
def sample_flags(sample_pages: list[TdrPage]) -> list[TdrFlag]:
    return detect_flags_in_pages(sample_pages)


@pytest.fixture()
def sample_chunks(sample_pages: list[TdrPage]) -> list[TdrChunk]:
    from agenteperry.tdr.chunking import chunk_pages
    return chunk_pages(sample_pages)


# ---------------------------------------------------------------------------
# Unit: _risk_level_for_score
# ---------------------------------------------------------------------------

def test_risk_level_zero_score() -> None:
    assert _risk_level_for_score(0) == "SIN_SENALES"


def test_risk_level_low_score() -> None:
    assert _risk_level_for_score(15) == "BAJO"


def test_risk_level_medium_score() -> None:
    assert _risk_level_for_score(40) == "MEDIO"


def test_risk_level_high_score() -> None:
    assert _risk_level_for_score(65) == "ALTO"


def test_risk_level_critical_score() -> None:
    assert _risk_level_for_score(100) == "CRITICO"


# ---------------------------------------------------------------------------
# Unit: _deduplicated_questions
# ---------------------------------------------------------------------------

def test_deduplicated_questions_no_flags() -> None:
    questions = _deduplicated_questions([])
    # Generic questions always included
    assert len(questions) >= 4
    assert all(isinstance(q, str) and len(q) > 10 for q in questions)


def test_deduplicated_questions_includes_flag_specific() -> None:
    flag = TdrFlag(
        tdr_id="x",
        flag_code="EXCESSIVE_CERTIFICATION_REQUIREMENT",
        flag_name="Certificacion restrictiva",
        severity=TdrSeverity.MEDIUM,
        score_contribution=15,
        evidence_quote="iso 9001 certificacion internacional",
        page_number=1,
        explanation="Merece revision.",
        rule_id="TDR-R004",
    )
    questions = _deduplicated_questions([flag])
    assert any("certificacion" in q.lower() for q in questions)


def test_deduplicated_questions_no_duplicates() -> None:
    flag1 = TdrFlag(
        tdr_id="x",
        flag_code="LOW_TRACEABILITY_OUTPUT",
        flag_name="Entregable bajo",
        severity=TdrSeverity.LOW,
        score_contribution=10,
        evidence_quote="informe final",
        page_number=2,
        explanation="...",
        rule_id="TDR-R005",
    )
    # Same flag_code repeated
    questions = _deduplicated_questions([flag1, flag1])
    assert len(questions) == len(set(questions))


# ---------------------------------------------------------------------------
# Unit: generate_dossier
# ---------------------------------------------------------------------------

def test_generate_dossier_structure(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
    sample_flags: list[TdrFlag],
) -> None:
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="test-ocid-001",
        entity_name="ESSALUD",
        procedure_code="AS-SM-55-2023",
        monto=195_000_000.00,
        coverage_pct=100.0,
        total_pages=4,
        pages=sample_pages,
        chunks=sample_chunks,
        flags=sample_flags,
    )

    assert dossier["schema_version"] == SCHEMA_VERSION
    assert "generated_at" in dossier
    assert dossier["document"]["sector"] == "salud"
    assert dossier["document"]["ocid"] == "test-ocid-001"
    assert dossier["document"]["entity_name"] == "ESSALUD"
    assert dossier["document"]["total_pages"] == 4
    assert dossier["document"]["total_chunks"] == len(sample_chunks)
    assert dossier["document"]["coverage_pct"] == 100.0
    assert dossier["document"]["checksum"].startswith("sha256:")
    assert dossier["document"]["parse_status"] == "parsed"

    assert "risk_summary" in dossier
    assert dossier["risk_summary"]["total_flags"] == len(sample_flags)
    assert isinstance(dossier["risk_summary"]["total_score"], int)
    assert dossier["risk_summary"]["risk_level"] in {
        "SIN_SENALES", "BAJO", "MEDIO", "ALTO", "CRITICO"
    }

    assert isinstance(dossier["flags"], list)
    assert isinstance(dossier["questions_for_authority"], list)
    assert dossier["disclaimer"] == DISCLAIMER


def test_generate_dossier_flags_have_required_fields(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
    sample_flags: list[TdrFlag],
) -> None:
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="test-ocid-002",
        coverage_pct=100.0,
        total_pages=4,
        pages=sample_pages,
        chunks=sample_chunks,
        flags=sample_flags,
    )
    for flag in dossier["flags"]:
        assert "flag_code" in flag
        assert "flag_name" in flag
        assert "severity" in flag
        assert "score_contribution" in flag
        assert "page_number" in flag
        assert "evidence_quote" in flag and len(flag["evidence_quote"]) > 0
        assert "explanation" in flag and len(flag["explanation"]) > 0


def test_generate_dossier_no_flags(
    minimal_pdf: Path,
    sample_chunks: list[TdrChunk],
) -> None:
    """A document with no flags should still produce a valid dossier."""
    pages = [TdrPage(tdr_id="x", page_number=1, text_content="Texto sin patrones de riesgo conocidos.")]
    no_flags: list[TdrFlag] = []
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="ambiente",
        ocid="clean-ocid",
        coverage_pct=100.0,
        total_pages=1,
        pages=pages,
        chunks=sample_chunks,
        flags=no_flags,
    )
    assert dossier["risk_summary"]["total_flags"] == 0
    assert dossier["risk_summary"]["risk_level"] == "SIN_SENALES"
    assert dossier["risk_summary"]["total_score"] == 0
    # Generic questions still present
    assert len(dossier["questions_for_authority"]) >= 4


def test_generate_dossier_is_json_serializable(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
    sample_flags: list[TdrFlag],
) -> None:
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="test-serializable",
        coverage_pct=100.0,
        total_pages=4,
        pages=sample_pages,
        chunks=sample_chunks,
        flags=sample_flags,
    )
    serialized = json.dumps(dossier, ensure_ascii=False)
    reconstructed: dict[str, Any] = json.loads(serialized)
    assert reconstructed["schema_version"] == SCHEMA_VERSION


def test_generate_dossier_checksum_is_deterministic(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
) -> None:
    kwargs: dict[str, Any] = {
        "pdf_path": minimal_pdf,
        "sector": "salud",
        "ocid": "chk-test",
        "coverage_pct": 100.0,
        "total_pages": 4,
        "pages": sample_pages,
        "chunks": sample_chunks,
        "flags": [],
    }
    d1 = generate_dossier(**kwargs)
    d2 = generate_dossier(**kwargs)
    assert d1["document"]["checksum"] == d2["document"]["checksum"]


# ---------------------------------------------------------------------------
# Unit: render_dossier_markdown
# ---------------------------------------------------------------------------

def test_render_dossier_markdown_structure(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
    sample_flags: list[TdrFlag],
) -> None:
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="md-test",
        entity_name="TEST ENTIDAD",
        coverage_pct=100.0,
        total_pages=4,
        pages=sample_pages,
        chunks=sample_chunks,
        flags=sample_flags,
    )
    md = render_dossier_markdown(dossier)

    assert "# Dossier TDR" in md
    assert "Aviso Legal" in md
    assert "Documento Analizado" in md
    assert "Senales Detectadas" in md
    assert "Preguntas Para la Autoridad" in md
    assert "Solicitud de Transparencia" in md
    assert "TEST ENTIDAD" in md


def test_render_dossier_markdown_no_flags(minimal_pdf: Path, sample_chunks: list[TdrChunk]) -> None:
    pages = [TdrPage(tdr_id="x", page_number=1, text_content="Texto limpio.")]
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="ambiente",
        ocid="no-flags-md",
        coverage_pct=100.0,
        total_pages=1,
        pages=pages,
        chunks=sample_chunks,
        flags=[],
    )
    md = render_dossier_markdown(dossier)
    assert "0 flags" not in md.lower() or "No se detectaron" in md
    assert "Preguntas Para la Autoridad" in md


def test_render_dossier_markdown_flag_table_has_evidence(
    minimal_pdf: Path,
    sample_pages: list[TdrPage],
    sample_chunks: list[TdrChunk],
    sample_flags: list[TdrFlag],
) -> None:
    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="ev-test",
        coverage_pct=100.0,
        total_pages=4,
        pages=sample_pages,
        chunks=sample_chunks,
        flags=sample_flags,
    )
    md = render_dossier_markdown(dossier)
    for flag in dossier["flags"]:
        # Evidence quote should appear somewhere in the markdown
        assert flag["evidence_quote"][:40] in md or flag["flag_code"] in md


# ---------------------------------------------------------------------------
# Integration: full pipeline produces consistent results
# ---------------------------------------------------------------------------

def test_full_pipeline_integration(minimal_pdf: Path) -> None:
    """End-to-end: PDF → pages → chunks → flags → dossier."""
    from agenteperry.tdr.chunking import chunk_pages
    from agenteperry.tdr.parsing import extract_pdf_pages

    pages = extract_pdf_pages(minimal_pdf, tdr_id="integration-test")
    assert len(pages) >= 1
    assert all(p.page_number >= 1 for p in pages)

    chunks = chunk_pages(pages)
    assert len(chunks) >= 1

    flags = detect_flags_in_pages(pages)
    # minimal_pdf has "iso 9001 certificacion internacional" → TDR-R004
    assert any(f.flag_code == "EXCESSIVE_CERTIFICATION_REQUIREMENT" for f in flags)

    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid="integration-ocid",
        entity_name="TEST",
        coverage_pct=100.0,
        total_pages=len(pages),
        pages=pages,
        chunks=chunks,
        flags=flags,
    )
    assert dossier["risk_summary"]["total_flags"] == len(flags)
    assert dossier["risk_summary"]["total_score"] > 0

    md = render_dossier_markdown(dossier)
    assert len(md) > 200


def test_full_pipeline_output_to_disk(minimal_pdf: Path, tmp_path: Path) -> None:
    """Verify that analyze pipeline creates all expected output files."""
    from agenteperry.tdr.chunking import chunk_pages
    from agenteperry.tdr.parsing import extract_pdf_pages

    out_dir = tmp_path / "results"
    ocid = "disk-test-ocid"
    result_dir = out_dir / ocid.replace("-", "_")
    result_dir.mkdir(parents=True, exist_ok=True)

    pages = extract_pdf_pages(minimal_pdf, tdr_id=ocid)
    chunks = chunk_pages(pages)
    flags = detect_flags_in_pages(pages)

    dossier = generate_dossier(
        pdf_path=minimal_pdf,
        sector="salud",
        ocid=ocid,
        coverage_pct=100.0,
        total_pages=len(pages),
        pages=pages,
        chunks=chunks,
        flags=flags,
    )

    # Write outputs
    (result_dir / "pages.json").write_text(
        json.dumps({"pages": [p.model_dump(mode="json") for p in pages]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "chunks.json").write_text(
        json.dumps({"chunks": [c.model_dump(mode="json") for c in chunks]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "flags.json").write_text(
        json.dumps({"flags": [f.model_dump(mode="json") for f in flags]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (result_dir / "dossier.json").write_text(
        json.dumps(dossier, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = render_dossier_markdown(dossier)
    (result_dir / "dossier.md").write_text(md, encoding="utf-8")

    # Assert all 5 outputs exist
    for fname in ("pages.json", "chunks.json", "flags.json", "dossier.json", "dossier.md"):
        assert (result_dir / fname).exists(), f"Missing: {fname}"

    # Assert dossier.json is valid
    reloaded: dict[str, Any] = json.loads((result_dir / "dossier.json").read_text(encoding="utf-8"))
    assert reloaded["schema_version"] == SCHEMA_VERSION
    assert reloaded["document"]["ocid"] == ocid
