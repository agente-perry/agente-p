"""Intent-driven query expansion: PR #8 recall improvement."""

from __future__ import annotations

from document_intelligence.agents._canonical import (
    expand_intents_to_flags,
    load_intent_map,
    match_intents,
)


def test_intent_map_loads() -> None:
    intents = load_intent_map()
    names = {i.name for i in intents}
    assert "risk_scan" in names
    risk = next(i for i in intents if i.name == "risk_scan")
    assert risk.expands_to
    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in risk.expands_to


def test_general_question_matches_risk_scan() -> None:
    question = "Detecta señales de baja trazabilidad y requisitos restrictivos"
    matched = [i.name for i in match_intents(question)]
    assert "risk_scan" in matched


def test_accent_fold_irrelevant_for_trigger_match() -> None:
    # Both forms must trigger.
    for q in [
        "buscar señales de riesgo",
        "buscar SENALES de riesgo",
        "buscar senales de RIESGO",
    ]:
        assert any(i.name == "risk_scan" for i in match_intents(q))


def test_expansion_returns_multiple_flag_codes() -> None:
    flags = expand_intents_to_flags("Detecta señales de baja trazabilidad y requisitos restrictivos")
    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in flags
    assert "SUBJECTIVE_EVALUATION_CRITERIA" in flags
    assert "SPECIFIC_EQUIPMENT_REQUIREMENT" in flags
    # No duplicates.
    assert len(flags) == len(set(flags))


def test_unrelated_question_returns_nothing() -> None:
    matched = match_intents("Cual es la capital del Peru?")
    assert matched == ()
    assert expand_intents_to_flags("Cual es la capital del Peru?") == ()


def test_documentary_intent_triggers_on_notarial() -> None:
    flags = expand_intents_to_flags("documentos con copia legalizada notarial")
    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in flags
