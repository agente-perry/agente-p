# Conflictos De Interés Y Patrones De Riesgo

## Principio Legal-Safe

No acusamos corrupción. Detectamos **patrones atípicos** que **merecen revisión**.

## 8 Patrones De Detección (Adaptados Del Legacy)

### 1. El Socio Invisible

**Descripción:** Funcionario en comité de selección tiene familiar vinculado a empresa ganadora.

**Fuentes:** OCDS (contrato + comité) + SIDJI (familiares declarados) + SUNARP (representantes).

**Query SQL:**
```sql
SELECT
  c.external_id AS contrato,
  p.display_name AS funcionario,
  fam.display_name AS familiar,
  emp.display_name AS empresa,
  c.monto,
  c.fecha
FROM source_records c
JOIN source_relationships r_com ON r_com.properties->>'contract_id' = c.id::text AND r_com.rel_type = 'MIEMBRO_COMITE'
JOIN source_entities p ON p.id = r_com.source_id
JOIN source_relationships r_fam ON r_fam.source_id = p.id AND r_fam.rel_type = 'FAMILIAR_DE'
JOIN source_entities fam ON fam.id = r_fam.target_id
JOIN source_relationships r_repr ON r_repr.source_id = fam.id AND r_repr.rel_type = 'REPRESENTANTE_DE'
JOIN source_entities emp ON emp.id = r_repr.target_id
WHERE c.supplier_ruc = emp.canonical_id;
```

**Flag:** `CONFLICT_OF_INTEREST_FAMILY`

---

### 2. El Aportante Favorito

**Descripción:** Empresa aportó a campaña del partido que gobierna la entidad contratante, y luego ganó contratos con esa entidad.

**Fuentes:** ONPE Claridad (aportes) + JNE (partidos gobernantes) + OCDS (contratos).

**Query SQL:**
```sql
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
```

**Flag:** `ELECTORAL_INVESTMENT_RETURN`

---

### 3. La Empresa Fantasma

**Descripción:** Empresa registrada hace menos de 12 meses, con domicilio compartido, gana como único postor.

**Fuentes:** SUNAT (edad + domicilio) + OCDS (contratos).

**Query SQL:**
```sql
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
```

**Flag:** `GHOST_COMPANY`

---

### 4. El Monopolio Silencioso

**Descripción:** Misma empresa concentra >50% del gasto de una entidad en 3 años.

**Fuentes:** OCDS (contratos) + MEF (presupuesto).

**Query SQL:**
```sql
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
```

**Flag:** `MARKET_CONCENTRATION`

---

### 5. El Comité Cómplice

**Descripción:** Mismo funcionario preside múltiples comités y gana siempre la misma empresa.

**Fuentes:** SEACE/OECE (comités) + OCDS (adjudicaciones).

**Flag:** `COMMITTEE_BIAS`

---

### 6. El Sancionado Activo

**Descripción:** Representante legal de empresa ganadora tiene sanción vigente de la Contraloría.

**Fuentes:** Contraloría Sanciones + SUNAT (representantes) + OCDS.

**Flag:** `SANCTIONED_REPRESENTATIVE`

---

### 7. La Ventana Corta

**Descripción:** Plazo de convocatoria < 5 días hábiles con único postor.

**Fuentes:** OCDS (tenderPeriod).

**Flag:** `SHORT_WINDOW`

---

### 8. El Conflicto Declarado

**Descripción:** Funcionario declaró en DJI participación en empresa que ganó contrato en su entidad.

**Fuentes:** SIDJI + OCDS.

**Flag:** `DECLARED_CONFLICT_IGNORED`

## Metadata Obligatoria Por Flag

Cada flag debe incluir:

```text
flag_code, severity, score_contribution,
evidence_quote, page_number, explanation,
detection_method='rule', pattern_id,
source_url, data_sources[]
```

## Lenguaje Legal-Safe

- Si: "presenta señales de riesgo", "merece revisión", "patrón atípico".
- No: "corrupto", "robo", "delincuente", "culpable".
