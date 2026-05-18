"""LegalSafetyFilter: blocks or sanitises banned vocabulary with anti-bypass measures."""

from __future__ import annotations

import pytest

from document_intelligence.safety.legal_filter import BannedTermFoundError, LegalSafetyFilter


class TestRejectMode:
    def test_blocks_corrupto(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Este funcionario es corrupto")

    def test_blocks_robo(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Se detecto robo de fondos publicos")

    def test_blocks_fraude(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Se ha detectado fraude en el proceso")

    def test_blocks_criminal(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("comportamiento criminal detectado")

    def test_blocks_mixto(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("El proceso es corrupto y hay indicios de fraude")

    def test_blocks_colusion(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Colusion comprobada entre los postores")

    def test_blocks_ladron(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("El ladron de identity este proceso")


class TestPluralVariations:
    def test_blocks_corruptos(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Los funcionarios corruptos fueron identificados")

    def test_blocks_fraudes(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Se detectaron fraudes sistemicos")

    def test_blocks_delincuentes(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Los delincuentes operan impunemente")

    def test_blocks_criminales(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("grupos criminales organizados")

    def test_blocks_culpables(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("Los culpables seran procesados")


class TestAccentVariations:
    def test_blocks_corrupcion(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("El caso de corrupcion fue documentado")

    def test_blocks_fraude_uppercase(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("CASO DE FRAUDE en licitacion")

    def test_blocks_delincuencia(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        with pytest.raises(BannedTermFoundError):
            filt.check("delincuencia economica en el pais")


class TestCheckAnalysisFieldCoverage:
    def test_flag_name_with_banned_term_raises(self) -> None:
        from document_intelligence.schemas.analysis import AnalysisResult, FlagRecord
        from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

        filt = LegalSafetyFilter(mode="reject")
        result = AnalysisResult(
            document="test",
            question="test",
            flags=[
                FlagRecord(
                    flag_code="TEST",
                    flag_name="Fraude electoral",
                    severity="high",
                    tdr_evidence=EvidenceItem(
                        chunk_id="c1",
                        page_number=1,
                        quote="texto limpio",
                    ),
                    doctrine_anchor=DoctrineAnchor(
                        source="Test",
                        quote="test",
                    ),
                    explanation="Explicacion limpia.",
                    confidence=0.7,
                )
            ],
        )
        with pytest.raises(BannedTermFoundError):
            filt.check_analysis(result)

    def test_flag_explanation_with_banned_term_raises(self) -> None:
        from document_intelligence.schemas.analysis import AnalysisResult, FlagRecord
        from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

        filt = LegalSafetyFilter(mode="reject")
        result = AnalysisResult(
            document="test",
            question="test",
            flags=[
                FlagRecord(
                    flag_code="TEST",
                    flag_name="Flag de prueba",
                    severity="high",
                    tdr_evidence=EvidenceItem(
                        chunk_id="c1",
                        page_number=1,
                        quote="texto limpio",
                    ),
                    doctrine_anchor=DoctrineAnchor(
                        source="Test",
                        quote="test",
                    ),
                    explanation="Esto indica corrupcion sistemica.",
                    confidence=0.7,
                )
            ],
        )
        with pytest.raises(BannedTermFoundError):
            filt.check_analysis(result)

    def test_flag_quote_with_banned_term_raises(self) -> None:
        from document_intelligence.schemas.analysis import AnalysisResult, FlagRecord
        from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

        filt = LegalSafetyFilter(mode="reject")
        result = AnalysisResult(
            document="test",
            question="test",
            flags=[
                FlagRecord(
                    flag_code="TEST",
                    flag_name="Flag de prueba",
                    severity="high",
                    tdr_evidence=EvidenceItem(
                        chunk_id="c1",
                        page_number=1,
                        quote="El fraude electoral fue evidenciado",
                    ),
                    doctrine_anchor=DoctrineAnchor(
                        source="Test",
                        quote="test",
                    ),
                    explanation="Explicacion limpia.",
                    confidence=0.7,
                )
            ],
        )
        with pytest.raises(BannedTermFoundError):
            filt.check_analysis(result)

    def test_clean_flag_passes(self) -> None:
        from document_intelligence.schemas.analysis import AnalysisResult, FlagRecord
        from document_intelligence.schemas.evidence import DoctrineAnchor, EvidenceItem

        filt = LegalSafetyFilter(mode="reject")
        result = AnalysisResult(
            document="test",
            question="test",
            summary="Se identificaron senales de riesgo que merecen revision humana.",
            flags=[
                FlagRecord(
                    flag_code="TEST",
                    flag_name="Flag de prueba",
                    severity="high",
                    tdr_evidence=EvidenceItem(
                        chunk_id="c1",
                        page_number=1,
                        quote="Se requiere formato digital.",
                    ),
                    doctrine_anchor=DoctrineAnchor(
                        source="Test",
                        quote="test",
                    ),
                    explanation="Esta clausula merece revision.",
                    confidence=0.7,
                )
            ],
        )
        checked = filt.check_analysis(result)
        assert checked is result


class TestSanitizeMode:
    def test_sanitize_replaces_banned_term(self) -> None:
        filt = LegalSafetyFilter(mode="sanitize")
        report = filt.check("el proceso es fraudulento")
        assert report.passed
        assert "FRAUDULENTO" in report.blocked_terms

    def test_sanitize_multiple_terms(self) -> None:
        filt = LegalSafetyFilter(mode="sanitize")
        report = filt.check("corrupto y fraude en el mismo proceso")
        assert report.passed
        assert len(report.blocked_terms) >= 2

    def test_sanitize_safe_text_unchanged(self) -> None:
        filt = LegalSafetyFilter(mode="sanitize")
        text = "El documento presenta senales de riesgo."
        report = filt.check(text)
        assert report.passed
        assert report.sanitized_text == text


class TestFlagMode:
    def test_flag_mode_does_not_raise(self) -> None:
        filt = LegalSafetyFilter(mode="flag")
        report = filt.check("Esto es un fraude")
        assert report.passed is False
        assert len(report.blocked_terms) > 0

    def test_multiple_banned_terms_detected(self) -> None:
        filt = LegalSafetyFilter(mode="flag")
        report = filt.check("El corrupto es un ladron")
        assert len(report.blocked_terms) >= 2


class TestEdgeCases:
    def test_empty_text_passes(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        report = filt.check("")
        assert report.passed

    def test_clean_text_passes(self) -> None:
        filt = LegalSafetyFilter(mode="reject")
        report = filt.check("Todo parece conforme a las normas establecidas.")
        assert report.passed
        assert report.blocked_terms == []
