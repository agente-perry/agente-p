"""Schemas serialize to JSON and reject unknown fields."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from document_intelligence.schemas import (
    AnalysisResult,
    DoctrineAnchor,
    DocumentChunk,
    DocumentCluster,
    DocumentPage,
    EvidenceItem,
    EvidencePack,
    FlagRecord,
)


def test_document_page_roundtrip() -> None:
    page = DocumentPage(
        document_id="d1", page_number=1, text="hola", char_count=4, needs_ocr=False
    )
    blob = page.model_dump_json()
    restored = DocumentPage.model_validate_json(blob)
    assert restored == page
    assert json.loads(blob)["page_number"] == 1


def test_document_chunk_requires_positive_page() -> None:
    with pytest.raises(ValidationError):
        DocumentChunk(
            chunk_id="d::00000",
            document_id="d",
            source_file="/x.pdf",
            chunk_index=0,
            page_start=0,
            page_end=1,
            text="x",
            char_start=0,
            char_end=1,
        )


def test_cluster_defaults() -> None:
    cluster = DocumentCluster(cluster_id="c1", label="Entregables")
    assert cluster.chunk_ids == []
    assert cluster.summary == ""


def test_evidence_pack_dual_citation() -> None:
    pack = EvidencePack(
        tdr_evidence=EvidenceItem(chunk_id="d::00007", page_number=91, quote="Formato A3."),
        doctrine_anchor=DoctrineAnchor(source="OCP Guide 2024", quote="Lack of structured outputs..."),
    )
    assert pack.tdr_evidence.page_number == 91
    assert pack.doctrine_anchor.source.startswith("OCP")


def test_analysis_result_serializes_with_flag() -> None:
    flag = FlagRecord(
        flag_code="OBSOLETE_PHYSICAL_FORMAT",
        flag_name="Entregable solo fisico",
        severity="medium",
        tdr_evidence=EvidenceItem(chunk_id="d::00007", page_number=91, quote="Formato A3."),
        doctrine_anchor=DoctrineAnchor(source="OCP Guide 2024", quote="Weak traceability..."),
        explanation="senal de baja trazabilidad digital.",
        confidence=0.78,
    )
    result = AnalysisResult(
        document="base.pdf",
        question="Trazabilidad",
        flags=[flag],
        confidence="medium",
    )
    payload = result.model_dump()
    assert payload["flags"][0]["flag_code"] == "OBSOLETE_PHYSICAL_FORMAT"
    assert "disclaimer" in payload


def test_analysis_result_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(
            {"document": "x", "question": "y", "unexpected": 1}
        )
