# TASKS — SPEC-0005

## Original scope
- [x] Crear `GET /api/tdr/[id]`.
- [x] Agregar serializer legal-safe con risk_score, risk_level, questions.
- [x] Tests de payload (9 tests unitarios con tsx/node --test).
- [x] Documentar ejemplo de respuesta en types.ts.

## Extended (SPEC-0012 integration)
- [x] T-06 — Migration 0004: agregar dossier_path, graph_enrichment_status, graph_findings a tdr_documents.
- [x] T-07 — Python: upsert_tdr_document_v2 + update_tdr_graph_fields en loader.py.
- [x] T-08 — TypeScript: extender TdrDossierResponse con dossier_path, graph_findings, graph_enrichment_status.
- [x] T-09 — TypeScript: route.ts lee columnas nuevas y pasa graph_findings al serializer.
- [x] T-10 — TypeScript: GraphFindings interface + GraphSignal interface.
- [x] T-11 — Tests: agregar 14 tests para graph_findings, enrichment_status, dossier_path.
- [x] T-12 — Spec: actualizar spec.md con nuevo schema de respuesta.
- [x] T-13 — TypeScript: vitest + tsconfig alias config.
- [x] T-14 — Verify: tsc --noEmit limpio, vitest 23/23 passing.

Ruta: `apps/web/src/app/api/tdr/[id]/route.ts`
Serializer: `apps/web/src/lib/tdr-dossier.ts`
Tests: `apps/web/src/tests/tdr-dossier.test.ts`
Migration: `packages/db/migrations/0004_tdr_graph_enrichment.sql`