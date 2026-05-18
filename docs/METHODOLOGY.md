# Methodology — TDR Risk Signals

## Legal-Safe Principle

AgentePerry does not accuse corruption. It detects clauses that present signals of risk or deserve review.

Use:

- presenta senales de riesgo
- merece revision
- requiere explicacion
- patron atipico

Do not use:

- robo
- corrupto
- mafioso
- culpable
- delincuente
- delito

## MVP Flags

| Code | Meaning | Evidence Required |
|------|---------|-------------------|
| `EXCESSIVE_DOCUMENT_REQUIREMENT` | High-volume document requirement | Quote + page |
| `OBSOLETE_PHYSICAL_FORMAT` | Physical/obsolete delivery format | Quote + page |
| `SPECIFIC_EQUIPMENT_REQUIREMENT` | Specific equipment requirement | Quote + page |
| `EXCESSIVE_CERTIFICATION_REQUIREMENT` | Potentially restrictive certification | Quote + page |
| `LOW_TRACEABILITY_OUTPUT` | Weak or unstructured deliverable | Quote + page |
| `SUBJECTIVE_EVALUATION_CRITERIA` | Evaluation criteria without clear rubric | Quote + page |

## Scoring Rule

The MVP score is rule-based. Embeddings are used for search, not for deciding risk.

Every flag must include:

- `flag_code`
- `severity`
- `score_contribution`
- `evidence_quote`
- `page_number`
- `explanation`
- `detection_method = rule`

## Disclaimer

Todo dossier debe incluir: "Este analisis identifica senales de riesgo en documentos publicos. No constituye una acusacion ni determina responsabilidad. Requiere revision humana y contraste con la fuente oficial."
