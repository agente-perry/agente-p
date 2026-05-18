# SPEC-0004: TDR Rule-Based Flags

## Objetivo

Detectar senales iniciales con evidencia textual y pagina.

## Flags MVP

- `EXCESSIVE_DOCUMENT_REQUIREMENT`
- `OBSOLETE_PHYSICAL_FORMAT`
- `SPECIFIC_EQUIPMENT_REQUIREMENT`
- `EXCESSIVE_CERTIFICATION_REQUIREMENT`
- `LOW_TRACEABILITY_OUTPUT`
- `SUBJECTIVE_EVALUATION_CRITERIA`

## Criterios de aceptacion

- [ ] Cada flag tiene `evidence_quote`.
- [ ] Cada flag tiene `page_number`.
- [ ] Lenguaje legal-safe.
- [ ] Tests por regla.
