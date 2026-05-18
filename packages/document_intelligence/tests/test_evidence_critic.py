"""EvidenceCriticAgent: validates evidence quotes, pages, and dual evidence."""

from __future__ import annotations

from document_intelligence.agents.evidence_critic import CriticConfig, EvidenceCriticAgent
from document_intelligence.schemas.analysis import FlagCandidate
from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

_SENTINEL = object()


def _candidate(
    flag_code: str = "OBSOLETE_PHYSICAL_FORMAT",
    flag_name: str = "Entregable exclusivamente fisico",
    severity: str = "medium",
    chunk_id: str = "chunk001",
    page_number: int = 3,
    quote: str = "debera presentarse impreso en formato A3",
    doctrine_anchor: DoctrineAnchor | None | object = _SENTINEL,
    confidence: float = 0.6,
) -> FlagCandidate:
    anchor: DoctrineAnchor | None = None
    if doctrine_anchor is not _SENTINEL:
        anchor = doctrine_anchor
    else:
        anchor = DoctrineAnchor(
            source="OCP Red Flags Guide (stub paraphrase)",
            section="Implementation phase / Output traceability",
            page=48,
            quote="Outputs required exclusively in printed or physical form "
            "without a digital counterpart reduce traceability.",
            flag_code="OBSOLETE_PHYSICAL_FORMAT",
        )
    return FlagCandidate(
        flag_code=flag_code,
        flag_name=flag_name,
        severity=severity,
        tdr_evidence=EvidenceItem(
            chunk_id=chunk_id,
            page_number=page_number,
            quote=quote,
            cluster="Entregables",
        ),
        doctrine_anchor=anchor,
        explanation="Test explanation.",
        confidence=confidence,
    )


def test_critic_accepts_valid_flag() -> None:
    cand = _candidate()
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.accepted) == 1
    assert len(critique.rejected) == 0
    assert critique.summary


def test_critic_rejects_flag_with_empty_quote() -> None:
    cand = _candidate(quote="   ")
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1
    assert critique.rejected[0] is cand


def test_critic_rejects_flag_without_chunk_id() -> None:
    cand = _candidate(chunk_id="")
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1
    assert critique.rejected[0] is cand


def test_critic_rejects_flag_without_doctrine_anchor() -> None:
    cand = _candidate(doctrine_anchor=None)
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1
    assert critique.rejected[0] is cand


def test_critic_accepts_flag_without_doctrine_when_dual_disabled() -> None:
    cand = _candidate(doctrine_anchor=None)
    agent = EvidenceCriticAgent(config=CriticConfig(require_dual_evidence=False))
    critique = agent.critique([cand])
    assert len(critique.accepted) == 1
    assert len(critique.rejected) == 0


def test_critic_rejects_flag_with_low_confidence() -> None:
    cand = _candidate(confidence=0.1)
    agent = EvidenceCriticAgent(config=CriticConfig(min_confidence=0.3))
    critique = agent.critique([cand])
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1


def test_critic_rejects_flag_with_empty_doctrine_quote() -> None:
    cand = _candidate(
        doctrine_anchor=DoctrineAnchor(
            source="Test",
            quote="   ",
            flag_code="OBSOLETE_PHYSICAL_FORMAT",
        )
    )
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1


def test_critic_mixed_accepted_and_rejected() -> None:
    good = _candidate()
    bad = _candidate(quote="   ")
    agent = EvidenceCriticAgent()
    critique = agent.critique([good, bad])
    assert len(critique.accepted) == 1
    assert len(critique.rejected) == 1
    assert critique.summary


def test_critic_rejected_flags_are_candidates_not_records() -> None:
    cand = _candidate(doctrine_anchor=None)
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert len(critique.rejected) == 1
    assert isinstance(critique.rejected[0], FlagCandidate)


def test_critic_needs_replan_when_all_rejected() -> None:
    cand = _candidate(doctrine_anchor=None)
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand])
    assert critique.needs_replan is True


def test_critic_no_replan_when_some_accepted() -> None:
    good = _candidate()
    bad = _candidate(quote="   ")
    agent = EvidenceCriticAgent()
    critique = agent.critique([good, bad])
    assert critique.needs_replan is False


def test_critic_no_replan_when_empty() -> None:
    agent = EvidenceCriticAgent()
    critique = agent.critique([])
    assert critique.needs_replan is False


def test_critic_validates_quote_literal_in_chunk() -> None:
    cand = _candidate(
        chunk_id="chunk001",
        quote="debera presentarse impreso en formato A3",
    )
    tdr_chunks = {
        "chunk001": "4.2 El informe final debera presentarse impreso en formato A3 "
        "y en dos ejemplares originales para la entidad.",
    }
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand], tdr_chunks=tdr_chunks)
    assert len(critique.accepted) == 1
    assert len(critique.rejected) == 0


def test_critic_rejects_quote_not_in_chunk() -> None:
    cand = _candidate(
        chunk_id="chunk001",
        quote="debera presentarse impreso en formato A3",
    )
    tdr_chunks = {
        "chunk001": "4.2 El informe final debe presentarse en formato digital.",
    }
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand], tdr_chunks=tdr_chunks)
    assert len(critique.accepted) == 0
    assert len(critique.rejected) == 1
    assert critique.needs_replan is True


def test_critic_skips_literal_check_when_chunk_not_found() -> None:
    cand = _candidate(chunk_id="chunk001", quote="debera presentarse impreso en formato A3")
    tdr_chunks: dict[str, str] = {}
    agent = EvidenceCriticAgent()
    critique = agent.critique([cand], tdr_chunks=tdr_chunks)
    assert len(critique.accepted) == 1
    assert len(critique.rejected) == 0


# ── PR #10: reject_reasons tests ─────────────────────────────────────────────

def test_critic_reject_reasons_populated_on_rejection() -> None:
    """reject_reasons[0] must contain FLAG_CODE and the rejection cause."""
    cand = _candidate(quote="   ")  # empty quote → "evidence_quote vacio"
    critique = EvidenceCriticAgent().critique([cand])
    assert len(critique.reject_reasons) == 1
    assert "OBSOLETE_PHYSICAL_FORMAT" in critique.reject_reasons[0]
    assert "vacio" in critique.reject_reasons[0]


def test_critic_reject_reasons_parallel_to_rejected() -> None:
    """len(reject_reasons) must equal len(rejected) at all times."""
    good = _candidate()
    bad1 = _candidate(quote="   ")
    bad2 = _candidate(chunk_id="")
    critique = EvidenceCriticAgent().critique([good, bad1, bad2])
    assert len(critique.reject_reasons) == len(critique.rejected) == 2


def test_critic_reject_reasons_empty_when_all_accepted() -> None:
    """No rejections → reject_reasons must be an empty list."""
    cand = _candidate()
    critique = EvidenceCriticAgent().critique([cand])
    assert critique.reject_reasons == []


def test_critic_reject_reasons_empty_on_empty_input() -> None:
    """Zero candidates → reject_reasons must be an empty list."""
    critique = EvidenceCriticAgent().critique([])
    assert critique.reject_reasons == []
