"""RiskAnalysisAgent: rule-based flag detection from retrieval results."""

from __future__ import annotations

from document_intelligence.agents.risk_analysis import RiskAnalysisAgent
from document_intelligence.doctrine import load_doctrine
from document_intelligence.embeddings import FakeEmbedder
from document_intelligence.schemas.plan import RetrievalHitRecord, RetrievalResult


def _make_result(
    flag_code: str,
    hits: list[tuple[str, int, int, str]],
    *,
    cluster_hint: str = "Entregables",
) -> RetrievalResult:
    return RetrievalResult(
        flag_code=flag_code,
        query_text=f"test query for {flag_code}",
        target_clusters=[],
        hits=[
            RetrievalHitRecord(
                chunk_id=chunk_id,
                page_start=ps,
                page_end=pe,
                text_excerpt=text,
                score=0.8,
                vector_score=0.7,
                bm25_score=0.6,
                cluster_hint=cluster_hint,
            )
            for chunk_id, ps, pe, text in hits
        ],
    )


def test_risk_analysis_detects_physical_format_flag() -> None:
    result = _make_result(
        "OBSOLETE_PHYSICAL_FORMAT",
        [
            (
                "chunk001",
                3,
                3,
                "El informe final debera presentarse en formato A3 "
                "y en dos ejemplares originales. No se requiere medio digital.",
            ),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates
    assert candidates[0].flag_code == "OBSOLETE_PHYSICAL_FORMAT"
    assert candidates[0].tdr_evidence.page_number == 3
    assert "A3" in candidates[0].tdr_evidence.quote or "formato" in candidates[0].tdr_evidence.quote.lower()


def test_risk_analysis_skips_when_no_pattern_matches() -> None:
    result = _make_result(
        "OBSOLETE_PHYSICAL_FORMAT",
        [
            ("chunk002", 5, 5, "El servicio se brindara en modalidad virtual."),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == []


def test_risk_analysis_detects_subjective_evaluation() -> None:
    result = _make_result(
        "SUBJECTIVE_EVALUATION_CRITERIA",
        [
            (
                "chunk003",
                8,
                8,
                "La propuesta sera evaluada conforme al juicio del comite tecnico. "
                "Se valorara la calidad general y la afinidad institucional.",
            ),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates
    assert candidates[0].flag_code == "SUBJECTIVE_EVALUATION_CRITERIA"


def test_risk_analysis_handles_unknown_flag_code() -> None:
    result = _make_result("UNKNOWN_FLAG_123", [("chunk004", 1, 1, "some text")])
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == []


def test_risk_analysis_with_doctrine_anchor() -> None:
    embedder = FakeEmbedder(dim=128)
    doctrine = load_doctrine(embedder=embedder)
    result = _make_result(
        "OBSOLETE_PHYSICAL_FORMAT",
        [
            (
                "chunk005",
                3,
                3,
                "El informe final debera presentarse exclusivamente en medio fisico.",
            ),
        ],
    )
    agent = RiskAnalysisAgent(doctrine_index=doctrine)
    candidates = agent.analyze([result])
    assert candidates
    assert candidates[0].doctrine_anchor is not None
    assert candidates[0].doctrine_anchor.source


def test_risk_analysis_dedups_identical_quotes() -> None:
    result = _make_result(
        "OBSOLETE_PHYSICAL_FORMAT",
        [
            ("chunk006", 3, 3, "presentar en formato impreso obligatorio"),
            ("chunk007", 4, 4, "presentar en formato impreso obligatorio"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1


# ─── PR #7 EXCESSIVE_DOCUMENT_REQUIREMENT regression tests ───────────────────

def test_excessive_doc_does_not_fire_on_bare_anexos() -> None:
    """anexo(s) alone is boilerplate header; must not emit flag."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk100", 5, 5, "ANEXO N 1: Formato de Presentacion de Oferta"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == [], f"bare anexos must not fire, got {candidates}"


def test_excessive_doc_does_not_fire_on_bare_formatos() -> None:
    """formatos alone is generic boilerplate; must not emit flag."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk101", 5, 5, "formatos o formularios previstos en las bases"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == [], f"bare formatos must not fire, got {candidates}"


def test_excessive_doc_does_not_fire_on_declaraciones_juradas() -> None:
    """declaraciones juradas appears in every Peruvian procurement doc."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk102", 5, 5, "Las declaraciones juradas, formatos o formularios "
             "previstos en las bases que conforman la oferta deben estar debida"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == [], f"declaraciones juradas must not fire, got {candidates}"


def test_excessive_doc_does_not_fire_on_generic_annex_header() -> None:
    """ANEXOS / N / Article section headers are not documentary burden."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk103", 72, 72, "ANEXOS\n39\nArticulo y norma que se vulnera"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert candidates == [], f"annex header must not fire, got {candidates}"


def test_excessive_doc_fires_on_copia_legalizada() -> None:
    """copia legalizada is a strong signal of notarial burden."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk104", 7, 7, "Se requiere tres copias legalizadas del contrato"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1
    assert candidates[0].flag_code == "EXCESSIVE_DOCUMENT_REQUIREMENT"


def test_excessive_doc_fires_on_foliado_visado() -> None:
    """foliado + visado indicates physical document certification burden."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk105", 12, 12, "El expediente debe estar foliado y visado "
             "por el notario titular"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1
    assert candidates[0].flag_code == "EXCESSIVE_DOCUMENT_REQUIREMENT"


def test_excessive_doc_fires_on_entrega_fisica_obligatoria() -> None:
    """entrega fisica obligatoria directly describes mandatory physical submission."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk106", 8, 8, "Se exige la entrega fisica obligatoria de tres "
             "juegos originales del expediente"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1
    assert candidates[0].flag_code == "EXCESSIVE_DOCUMENT_REQUIREMENT"


def test_excessive_doc_fires_on_lista_extensa_de_documentos() -> None:
    """lista extensa de documentos explicitly describes excessive burden."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk107", 15, 15, "Presentar una lista extensa de documentos "
             "para la habilitacion del postor"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1


def test_excessive_doc_fires_on_presentar_siguientes_n_documentos() -> None:
    """presentar los siguientes 15 documentos is a numeric documentary burden."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk108", 9, 9, "El postor debe presentar los siguientes 15 "
             "documentos habilitantes"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1


def test_excessive_doc_fires_on_tres_juegos() -> None:
    """tres juegos originales signals physical document redundancy."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk109", 11, 11, "Se requieren tres juegos originales del "
             "contrato y sus anexos"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1


def test_excessive_doc_fires_on_sobre_cerrado() -> None:
    """sobre cerrado signals physical sealed-envelope submission."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("chunk110", 6, 6, "La propuesta debe presentarse en sobre cerrado"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    assert len(candidates) == 1


# ─── Semantic dedup tests ────────────────────────────────────────────────────

def test_semantic_dedup_keeps_higher_confidence() -> None:
    """When two near-identical quotes appear in a single analyze() call, dedup keeps one."""
    # Both hits in the same analyze() call so dedup can operate across them
    r1 = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("dup1", 3, 3, "Se requiere tres copias legalizadas del contrato"),
            ("dup2", 4, 4, "Se requiere tres copias legalizadas del contrato"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([r1])
    from collections import Counter
    counts = Counter(c.flag_code for c in candidates)
    assert counts["EXCESSIVE_DOCUMENT_REQUIREMENT"] == 1


def test_semantic_dedup_keeps_different_flags() -> None:
    """Different flag codes are never deduped against each other."""
    r1 = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [("chunk200", 3, 3, "copia legalizada notarial del expediente")],
    )
    r2 = _make_result(
        "SUBJECTIVE_EVALUATION_CRITERIA",
        [("chunk201", 7, 7, "juicio del comite tecnico de evaluacion")],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([r1, r2])
    codes = [c.flag_code for c in candidates]
    assert "EXCESSIVE_DOCUMENT_REQUIREMENT" in codes
    assert "SUBJECTIVE_EVALUATION_CRITERIA" in codes


def test_semantic_dedup_merges_near_duplicate_pages() -> None:
    """Two hits with Jaccard >= 0.7 on the same flag_code are deduplicated."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            ("dup3", 10, 10, "Las declaraciones juradas, formatos o formularios "
             "previstos en las bases que conforman la oferta deben estar debida"),
            ("dup4", 11, 11, "Las declaraciones juradas, formatos o formularios "
             "previstos en las bases que conforman la oferta deben estar debida"),
        ],
    )
    agent = RiskAnalysisAgent()
    candidates = agent.analyze([result])
    codes = [c.flag_code for c in candidates]
    from collections import Counter
    counts = Counter(codes)
    assert counts["EXCESSIVE_DOCUMENT_REQUIREMENT"] <= 1

# ── PR #9 medium-strength patterns (evidence-backed) ──────────────────────────


def test_over_specified_fires_on_experiencia_establecida_en_bases() -> None:
    """Positive: medium pattern catches the p52 quote from tdr_ambiente_positive_001."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr9_01",
                52,
                52,
                "Los adjudicadores deben cumplir los requisitos establecidos en el "
                "articulo 329 del Reglamento y aquellos referidos a la experiencia "
                "especifica establecida en las bases del procedimiento de seleccion, "
                "de ser el caso.",
            ),
        ],
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].flag_code == "OVER_SPECIFIED_EXPERIENCE"
    assert candidates[0].tdr_evidence.page_number == 52
    assert "experiencia especifica" in candidates[0].tdr_evidence.quote.lower()


def test_over_specified_does_not_fire_on_bare_experiencia_especifica() -> None:
    """Negative: bare 'experiencia especifica' without anchor must not match."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr9_02",
                1,
                1,
                "El postor debe contar con experiencia especifica para el rubro.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_over_specified_does_not_fire_on_anchor_without_experiencia() -> None:
    """Negative: 'establecida en las bases' alone is meaningless."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr9_03",
                1,
                1,
                "Las condiciones establecidas en las bases regiran el contrato.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_over_specified_fires_on_servicios_similares_al_objeto() -> None:
    """Positive: catches narrow-scope qualification clause from tdr_salud_pliego_001 p206."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr9_04",
                206,
                206,
                "El postor debe acreditar prestacion de servicios iguales o similares "
                "al objeto de convocatoria de los ultimos ocho (08) anios.",
            ),
        ],
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].flag_code == "OVER_SPECIFIED_EXPERIENCE"
    assert "similares al objeto" in candidates[0].tdr_evidence.quote.lower()


def test_over_specified_does_not_fire_on_bare_similar_al_objeto() -> None:
    """Negative: 'similar al objeto' without contratos|servicios|experiencia prefix."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr9_05",
                1,
                1,
                "El alcance es similar al objeto del proyecto anterior del area.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_excessive_doc_fires_on_firmas_legalizadas_ante_notario() -> None:
    """Positive: catches the consortium notarial burden (tdr_ambiente_001 p13)."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            (
                "chunk_pr9_06",
                13,
                13,
                "Contrato de consorcio con firmas legalizadas ante Notario de cada "
                "uno de los integrantes, de ser el caso.",
            ),
        ],
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].flag_code == "EXCESSIVE_DOCUMENT_REQUIREMENT"
    assert "legalizadas ante notario" in candidates[0].tdr_evidence.quote.lower()


def test_excessive_doc_does_not_fire_on_firmas_digitales() -> None:
    """Negative: digital signatures must not trigger the notarial-burden pattern."""
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            (
                "chunk_pr9_07",
                1,
                1,
                "Las firmas digitales o electronicas son aceptadas conforme a ley.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


# ── PR #9 regression: PR #7 zero-FP baseline must hold ───────────────────────


def test_pr9_does_not_reintroduce_bare_anexos_fp() -> None:
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [("pr7_reg_01", 1, 1, "Veanse los anexos al final del documento.")],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_pr9_does_not_reintroduce_bare_formatos_fp() -> None:
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [("pr7_reg_02", 1, 1, "Los formatos aceptados son .pdf .docx .xlsx.")],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_pr9_does_not_reintroduce_declaraciones_juradas_fp() -> None:
    result = _make_result(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        [
            (
                "pr7_reg_03",
                1,
                1,
                "Las declaraciones juradas, formatos o formularios previstos en las "
                "bases que conforman la oferta deben estar debidamente firmadas.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


def test_pr9_does_not_reintroduce_modelo_referencial_costos_fp() -> None:
    """Negative regression: 'Modelo referencial de Estructura de Costos' (tdr_salud_pliego_001 p8)
    refers to a cost model template, not to equipment brand. SPECIFIC_EQUIPMENT_REQUIREMENT
    must not fire."""
    result = _make_result(
        "SPECIFIC_EQUIPMENT_REQUIREMENT",
        [
            (
                "pr7_reg_04",
                8,
                8,
                'Del Anexo N 4 "Modelo referencial de Estructura de Costos", de las '
                "bases del procedimiento.",
            ),
        ],
    )
    assert RiskAnalysisAgent().analyze([result]) == []


# ── PR #10: Severity tuning — weak-signal downgrade ──────────────────────────

def test_weak_signal_downgraded_to_low_severity() -> None:
    """Clause-pointer in neutral cluster ('Otros') with no narrowing anchor →
    severity must be downgraded to 'low' and confidence capped at 0.45."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr10_01",
                52,
                52,
                "Los adjudicadores deben cumplir la experiencia especifica establecida "
                "en las bases del procedimiento de seleccion, de ser el caso.",
            ),
        ],
        cluster_hint="Otros",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates, "pattern must still match and produce a candidate"
    assert candidates[0].severity == "low", (
        "template pointer in neutral cluster must be downgraded to low severity"
    )
    assert candidates[0].confidence <= 0.45


def test_year_anchor_prevents_downgrade() -> None:
    """A concrete year number is a narrowing anchor: severity must remain 'high'
    even when the cluster is neutral ('Otros')."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr10_02",
                206,
                206,
                "El postor debe acreditar servicios similares al objeto de convocatoria "
                "de los ultimos 8 (ocho) anios contados a la fecha del registro.",
            ),
        ],
        cluster_hint="Otros",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].severity == "high", (
        "year-anchored signal must keep original severity"
    )
    assert candidates[0].confidence >= 0.65


def test_non_neutral_cluster_never_downgraded() -> None:
    """Even without a narrowing anchor, a non-neutral cluster is NOT a weak signal."""
    result = _make_result(
        "OVER_SPECIFIED_EXPERIENCE",
        [
            (
                "chunk_pr10_03",
                52,
                52,
                "Los postores deben cumplir la experiencia especifica establecida "
                "en las bases del procedimiento de seleccion.",
            ),
        ],
        cluster_hint="Requisitos del servicio",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].severity == "high", (
        "non-neutral cluster must keep the original severity regardless of anchors"
    )


# ── PR #10: _is_weak_signal unit tests ───────────────────────────────────────

def test_is_weak_signal_true_neutral_cluster_no_anchor() -> None:
    """Unit: neutral cluster + no narrowing anchor → weak."""
    from document_intelligence.agents.risk_analysis import _is_weak_signal

    assert _is_weak_signal(
        "OVER_SPECIFIED_EXPERIENCE",
        "experiencia especifica establecida en las bases del procedimiento",
        "Otros",
    ) is True


def test_is_weak_signal_false_year_present() -> None:
    """Unit: neutral cluster BUT year number present → NOT weak."""
    from document_intelligence.agents.risk_analysis import _is_weak_signal

    assert _is_weak_signal(
        "OVER_SPECIFIED_EXPERIENCE",
        "servicios similares al objeto de convocatoria de los ultimos 8 anios",
        "Otros",
    ) is False


def test_is_weak_signal_false_non_neutral_cluster() -> None:
    """Unit: non-neutral cluster, no narrowing anchor → NOT weak."""
    from document_intelligence.agents.risk_analysis import _is_weak_signal

    assert _is_weak_signal(
        "OVER_SPECIFIED_EXPERIENCE",
        "experiencia especifica establecida en las bases del procedimiento",
        "Requisitos del servicio",
    ) is False


def test_is_weak_signal_false_empty_cluster() -> None:
    """Unit: empty-string cluster is neutral BUT flag has no anchors defined for
    'OBSOLETE_PHYSICAL_FORMAT' → no anchors to check → returns False."""
    from document_intelligence.agents.risk_analysis import _is_weak_signal

    # OBSOLETE_PHYSICAL_FORMAT has no entry in _NARROWING_ANCHORS_BY_FLAG
    assert _is_weak_signal(
        "OBSOLETE_PHYSICAL_FORMAT",
        "presentar en formato A3",
        "",
    ) is False


def test_is_weak_signal_false_monto_anchor() -> None:
    """Unit: 'monto acumulado minimo' is a narrowing anchor → NOT weak."""
    from document_intelligence.agents.risk_analysis import _is_weak_signal

    assert _is_weak_signal(
        "OVER_SPECIFIED_EXPERIENCE",
        "el postor debe acreditar monto acumulado minimo de S/ 500,000",
        "Otros",
    ) is False


# ── PR #10 severity tuning (weak-signal downgrade) ──────────────────────────


def _make_hit_with_cluster(
    flag_code: str,
    text: str,
    cluster: str | None,
    page: int = 1,
) -> RetrievalResult:
    return RetrievalResult(
        flag_code=flag_code,
        query_text=f"test {flag_code}",
        target_clusters=[],
        hits=[
            RetrievalHitRecord(
                chunk_id="pr10_weak",
                page_start=page,
                page_end=page,
                text_excerpt=text,
                score=0.5,
                vector_score=0.3,
                bm25_score=0.4,
                cluster_hint=cluster,
            )
        ],
    )


def test_pr10_template_quote_in_otros_is_downgraded_to_low() -> None:
    """A template phrase ('experiencia especifica establecida en las bases') in
    the 'Otros' cluster without numbers/monto/objeto-similar anchors must be
    severity=low and have reduced confidence."""
    result = _make_hit_with_cluster(
        "OVER_SPECIFIED_EXPERIENCE",
        (
            "Los adjudicadores referidos a la experiencia especifica establecida "
            "en las bases del procedimiento de seleccion, de ser el caso."
        ),
        cluster="Otros",
        page=52,
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates, "weak template quote should still surface as a low-severity pointer"
    cand = candidates[0]
    assert cand.flag_code == "OVER_SPECIFIED_EXPERIENCE"
    assert cand.severity == "low"
    assert cand.confidence <= 0.45


def test_pr10_quote_with_years_stays_high_severity() -> None:
    """Same pattern but with explicit '8 años' → severity stays at baseline."""
    result = _make_hit_with_cluster(
        "OVER_SPECIFIED_EXPERIENCE",
        (
            "Contratacion de servicios similares al objeto de convocatoria de "
            "los ultimos ocho (08) anios anteriores."
        ),
        cluster="Otros",
        page=206,
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    cand = candidates[0]
    assert cand.severity == "high"
    assert cand.confidence >= 0.6


def test_pr10_quote_with_monto_stays_strong() -> None:
    """Quote with 'monto acumulado minimo' is a strong narrowing anchor →
    severity stays at baseline even in Otros cluster."""
    result = _make_hit_with_cluster(
        "OVER_SPECIFIED_EXPERIENCE",
        "El postor debe acreditar monto acumulado minimo de S/ 5,000,000.",
        cluster="Otros",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    cand = candidates[0]
    assert cand.severity == "high"


def test_pr10_quote_in_meaningful_cluster_keeps_severity() -> None:
    """Same template phrase but in 'Experiencia del postor' cluster keeps
    baseline severity — the cluster itself is a structural anchor."""
    result = _make_hit_with_cluster(
        "OVER_SPECIFIED_EXPERIENCE",
        (
            "experiencia especifica establecida en las bases del procedimiento "
            "de seleccion."
        ),
        cluster="Experiencia del postor",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    cand = candidates[0]
    assert cand.severity == "high"
    assert cand.confidence >= 0.6


def test_pr10_excessive_doc_notarial_in_otros_with_anchor_stays_strong() -> None:
    """Notarial burden with 'obligatori' anchor stays at baseline severity even
    when cluster_hint is Otros."""
    result = _make_hit_with_cluster(
        "EXCESSIVE_DOCUMENT_REQUIREMENT",
        (
            "Contrato de consorcio con firmas legalizadas ante notario publico "
            "es obligatorio."
        ),
        cluster="Otros",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    cand = candidates[0]
    assert cand.severity == "medium"


def test_pr10_existing_strong_flags_unchanged() -> None:
    """Regression: PR #9 strong-anchor patterns still produce baseline severity."""
    result = _make_hit_with_cluster(
        "OVER_SPECIFIED_EXPERIENCE",
        "experiencia minima de 10 anios en el mismo sector restrictivo.",
        cluster="Experiencia del postor",
    )
    candidates = RiskAnalysisAgent().analyze([result])
    assert candidates
    assert candidates[0].severity == "high"
