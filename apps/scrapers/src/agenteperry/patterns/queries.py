"""Detection patterns for conflict of interest and risk signals."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DetectionPattern(BaseModel):
    """A reusable detection pattern with SQL query."""

    pattern_id: str = Field(pattern=r"^pattern_\d+$")
    name: str
    subtitle: str
    description: str
    severity: str = Field(pattern=r"^(LOW|MEDIUM|HIGH|CRITICAL)$")
    score_max: float = Field(ge=0.0, le=1.0)
    sources_required: list[str] = Field(default_factory=list)
    sql_query: str
    flag_code: str
    narrative: str


PATTERNS: list[DetectionPattern] = [
    DetectionPattern(
        pattern_id="pattern_1",
        name="El Socio Invisible",
        subtitle="Conflicto de interes por familiar",
        description="Funcionario en comite de seleccion tiene familiar vinculado a empresa ganadora",
        severity="HIGH",
        score_max=0.45,
        sources_required=["OCDS", "SIDJI", "SUNARP"],
        flag_code="CONFLICT_OF_INTEREST_FAMILY",
        narrative="El funcionario que evaluo o firmo el contrato tiene un familiar directo que es representante legal o socio de la empresa ganadora.",
        sql_query="""
SELECT
    c.external_id AS contrato,
    p.display_name AS funcionario,
    fam.display_name AS familiar,
    emp.display_name AS empresa,
    c.monto,
    c.fecha
FROM source_records c
JOIN source_relationships r_com ON r_com.properties->>'contract_id' = c.id::text
    AND r_com.rel_type = 'MIEMBRO_COMITE'
JOIN source_entities p ON p.id = r_com.source_id
JOIN source_relationships r_fam ON r_fam.source_id = p.id AND r_fam.rel_type = 'FAMILIAR_DE'
JOIN source_entities fam ON fam.id = r_fam.target_id
JOIN source_relationships r_repr ON r_repr.source_id = fam.id AND r_repr.rel_type = 'REPRESENTANTE_DE'
JOIN source_entities emp ON emp.id = r_repr.target_id
WHERE c.supplier_ruc = emp.canonical_id;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_2",
        name="El Aportante Favorito",
        subtitle="Retorno de inversion electoral",
        description="Empresa aporto a campana del partido que gobierna la entidad contratante",
        severity="HIGH",
        score_max=0.40,
        sources_required=["ONPE_CLARIDAD", "JNE", "OCDS"],
        flag_code="ELECTORAL_INVESTMENT_RETURN",
        narrative="Una empresa aporto dinero a la campana del partido que actualmente gobierna la entidad contratante. Despues de las elecciones, esa misma empresa gano contratos con esa entidad.",
        sql_query="""
SELECT
    emp.display_name AS empresa,
    po.display_name AS partido,
    pe.display_name AS entidad,
    SUM(c.monto) AS total_contratos_post,
    COUNT(*) AS num_contratos
FROM source_entities emp
JOIN source_relationships r_ap ON r_ap.source_id = emp.id AND r_ap.rel_type = 'APORTO_A'
JOIN source_entities po ON po.id = r_ap.target_id
JOIN source_relationships r_gov ON r_gov.source_id = po.id AND r_gov.rel_type = 'GOVERNS'
JOIN source_entities pe ON pe.id = r_gov.target_id
JOIN source_records c ON c.entity_ruc = pe.canonical_id AND c.supplier_ruc = emp.canonical_id
    AND c.fecha > (r_ap.properties->>'fecha_aporte')::date
GROUP BY emp.display_name, po.display_name, pe.display_name
HAVING SUM(c.monto) > 0;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_3",
        name="La Empresa Fantasma",
        subtitle="Creada para ganar",
        description="Empresa registrada hace menos de 12 meses con domicilio compartido gana como unico postor",
        severity="HIGH",
        score_max=0.35,
        sources_required=["SUNAT_PADRON", "OCDS"],
        flag_code="GHOST_COMPANY",
        narrative="La empresa ganadora fue registrada hace menos de 12 meses, comparte domicilio fiscal con 5+ empresas, y gano como unico postor.",
        sql_query="""
SELECT
    c.external_id,
    emp.canonical_id AS ruc,
    emp.display_name AS empresa,
    (emp.metadata->>'fecha_inicio_act')::date AS fecha_fundacion,
    c.monto,
    c.supplier_ruc
FROM source_records c
JOIN source_entities emp ON emp.canonical_id = c.supplier_ruc
WHERE c.record_type = 'contract'
    AND (emp.metadata->>'empresas_mismo_domicilio')::int > 5
    AND (emp.metadata->>'fecha_inicio_act')::date > c.fecha - INTERVAL '12 months';
""",
    ),
    DetectionPattern(
        pattern_id="pattern_4",
        name="El Monopolio Silencioso",
        subtitle="Proveedor recurrente",
        description="Misma empresa concentra >50% del gasto de una entidad en 3 anos",
        severity="MEDIUM",
        score_max=0.30,
        sources_required=["OCDS", "MEF"],
        flag_code="MARKET_CONCENTRATION",
        narrative="La misma empresa concentra mas del 50% del presupuesto ejecutado de la entidad en los ultimos 3 anos.",
        sql_query="""
WITH empresa_stats AS (
    SELECT
        entity_ruc,
        supplier_ruc,
        COUNT(*) AS num_contratos,
        SUM(monto) AS total_monto,
        SUM(monto) / SUM(SUM(monto)) OVER (PARTITION BY entity_ruc) AS pct_presupuesto
    FROM source_records
    WHERE record_type = 'contract'
        AND fecha >= CURRENT_DATE - INTERVAL '3 years'
    GROUP BY entity_ruc, supplier_ruc
)
SELECT
    pe.display_name AS entidad,
    emp.display_name AS empresa,
    es.num_contratos,
    es.total_monto,
    ROUND(es.pct_presupuesto * 100, 1) AS pct_presupuesto
FROM empresa_stats es
JOIN source_entities pe ON pe.canonical_id = es.entity_ruc
JOIN source_entities emp ON emp.canonical_id = es.supplier_ruc
WHERE es.pct_presupuesto > 0.50
    AND es.num_contratos >= 3
ORDER BY es.pct_presupuesto DESC;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_5",
        name="El Comite Complice",
        subtitle="Mismo evaluador, mismo ganador",
        description="Mismo funcionario preside multiples comites y gana siempre la misma empresa",
        severity="HIGH",
        score_max=0.35,
        sources_required=["SEACE", "OCDS"],
        flag_code="COMMITTEE_BIAS",
        narrative="El mismo funcionario presidio multiples comites de seleccion y en la mayoria de ellos gano siempre la misma empresa.",
        sql_query="""
WITH comite_stats AS (
    SELECT
        r_com.source_id AS funcionario_id,
        r_gan.source_id AS empresa_id,
        COUNT(*) AS contratos_juntos
    FROM source_relationships r_com
    JOIN source_records c ON c.id::uuid = r_com.target_id
    JOIN source_relationships r_gan ON r_gan.target_id = c.id::uuid
        AND r_gan.rel_type = 'GANO_CONTRATO'
    WHERE r_com.rel_type = 'MIEMBRO_COMITE'
    GROUP BY r_com.source_id, r_gan.source_id
    HAVING COUNT(*) >= 3
)
SELECT
    p.display_name AS funcionario,
    emp.display_name AS empresa_favorita,
    cs.contratos_juntos
FROM comite_stats cs
JOIN source_entities p ON p.id = cs.funcionario_id
JOIN source_entities emp ON emp.id = cs.empresa_id;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_6",
        name="El Sancionado Activo",
        subtitle="Inhabilitado contratando",
        description="Representante legal de empresa ganadora tiene sancion vigente",
        severity="CRITICAL",
        score_max=0.50,
        sources_required=["CONTRALORIA_SANCIONES", "SUNAT_PADRON", "OCDS"],
        flag_code="SANCTIONED_REPRESENTATIVE",
        narrative="El representante legal de la empresa ganadora tiene una inhabilitacion vigente de la Contraloria al momento de la firma del contrato.",
        sql_query="""
SELECT
    c.external_id,
    c.fecha,
    c.monto,
    emp.canonical_id AS empresa_ruc,
    emp.display_name AS empresa,
    p.canonical_id AS representante_dni,
    p.display_name AS representante_nombre
FROM source_records c
JOIN source_relationships r_gan ON r_gan.target_id = c.id::uuid
    AND r_gan.rel_type = 'GANO_CONTRATO'
JOIN source_entities emp ON emp.id = r_gan.source_id
JOIN source_relationships r_repr ON r_repr.target_id = emp.id
    AND r_repr.rel_type = 'REPRESENTANTE_DE'
JOIN source_entities p ON p.id = r_repr.source_id
JOIN source_relationships r_sanc ON r_sanc.source_id = p.id
    AND r_sanc.rel_type = 'TIENE_SANCION'
WHERE c.record_type = 'contract'
    AND c.fecha >= CURRENT_DATE;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_7",
        name="La Ventana Corta",
        subtitle="Plazo disenado para excluir competidores",
        description="Plazo de convocatoria < 5 dias habiles con unico postor",
        severity="MEDIUM",
        score_max=0.25,
        sources_required=["OCDS"],
        flag_code="SHORT_WINDOW",
        narrative="El proceso de licitacion tuvo un plazo de convocatoria menor a 5 dias habiles, con unico postor y monto superior al percentil 90.",
        sql_query="""
SELECT
    c.external_id,
    pe.display_name AS entidad,
    emp.display_name AS empresa,
    c.supplier_ruc AS ruc,
    (c.fecha - (c.metadata->>'fecha_conv')::date) AS dias_plazo,
    c.monto
FROM source_records c
JOIN source_entities pe ON pe.canonical_id = c.entity_ruc
JOIN source_entities emp ON emp.canonical_id = c.supplier_ruc
WHERE c.record_type = 'contract'
    AND (c.fecha - (c.metadata->>'fecha_conv')::date) < 5;
""",
    ),
    DetectionPattern(
        pattern_id="pattern_8",
        name="El Conflicto Declarado",
        subtitle="DJI activa ignorada",
        description="Funcionario declaro en DJI participacion en empresa que gano contrato en su entidad",
        severity="CRITICAL",
        score_max=0.45,
        sources_required=["SIDJI", "OCDS"],
        flag_code="DECLARED_CONFLICT_IGNORED",
        narrative="El funcionario declaro en su DJI tener participacion en la empresa que gano un contrato en la entidad donde el trabaja durante ese periodo.",
        sql_query="""
SELECT
    c.external_id,
    c.monto,
    p.canonical_id AS funcionario_dni,
    p.display_name AS funcionario_nombre,
    emp.canonical_id AS empresa_ruc,
    emp.display_name AS empresa
FROM source_records c
JOIN source_relationships r_gan ON r_gan.target_id = c.id::uuid
    AND r_gan.rel_type = 'GANO_CONTRATO'
JOIN source_entities emp ON emp.id = r_gan.source_id
JOIN source_relationships r_dji ON r_dji.target_id = emp.id
    AND r_dji.rel_type = 'VINCULO_DJI'
JOIN source_entities p ON p.id = r_dji.source_id
JOIN source_relationships r_func ON r_func.source_id = p.id
    AND r_func.rel_type = 'FUNCIONARIO_EN'
WHERE c.record_type = 'contract'
    AND c.entity_ruc = r_func.target_id::text;
""",
    ),
]


def get_pattern(pattern_id: str) -> DetectionPattern | None:
    """Get a pattern by ID."""
    for p in PATTERNS:
        if p.pattern_id == pattern_id:
            return p
    return None


def list_patterns() -> list[DetectionPattern]:
    """List all available patterns."""
    return PATTERNS.copy()


def patterns_by_severity(severity: str) -> list[DetectionPattern]:
    """Filter patterns by severity."""
    return [p for p in PATTERNS if p.severity == severity]
