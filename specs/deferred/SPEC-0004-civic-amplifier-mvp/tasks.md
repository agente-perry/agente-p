# TASKS — SPEC-0004 Civic Amplifier MVP

## Pre

- [ ] T-01 — Spec aprobado [@MiguelAAR10] [0.5h]
- [ ] T-02 — Branch `feat/SPEC-0004-civic-amplifier-mvp` [@TBD-4] [0.1h]
- [ ] T-03 — Pre-req: SPEC-0003 completado con casos en DB [@MiguelAAR10] [PRE-REQ]
- [ ] T-04 — `apps/web` inicializado con Next.js 15 (puede ser separado en SPEC-0005) [@TBD-3] [PRE-REQ]

## Schema + AI SDK

- [ ] T-10 — `packages/amplifier/src/schemas/kit.ts` con zod KitOutputSchema [@TBD-4] [1h]
- [ ] T-11 — `packages/amplifier/src/kit_generator.ts` con AI SDK `generateObject` [@TBD-4] [2h]
- [ ] T-12 — `applyLegalFilter(kit)` walker que muta strings + marca requires_review [@TBD-4] [1.5h]
- [ ] T-13 — Wrapper `lib/ai/provider.ts` en apps/web con configurable provider [@TBD-4] [0.5h]

## Legal filter robustness

- [ ] T-20 — Refinar `legal_filter.ts`: case-insensitive, evitar match dentro de palabra ("corruptismo") [@TBD-4] [1h]
- [ ] T-21 — Agregar más SOFT_REPLACEMENTS basados en review de prompts reales [@TBD-4] [0.5h]
- [ ] T-22 — Test suite `legal_filter.test.ts` con 20+ casos [@TBD-4] [2h]

## DB layer (TS side)

- [ ] T-30 — `packages/db/queries/get_case_full.sql` que devuelve case+flags+entities como JSONB [@MiguelAAR10] [1h]
- [ ] T-31 — Migración helper RPC `get_case_full(p_slug VARCHAR) RETURNS JSONB` [@MiguelAAR10] [0.5h]
- [ ] T-32 — Helper `persistKit(supabase, caseId, kit)` que crea narratives + assets [@TBD-4] [1.5h]

## UI (apps/web)

- [ ] T-40 — Server Action `regenerateKitAction(slug)` con auth check + persist [@TBD-3 + @TBD-4] [2h]
- [ ] T-41 — Página `/editorial/caso/[slug]/page.tsx` con load de case + button [@TBD-3] [2h]
- [ ] T-42 — `<KitPreview>` component con tabs por audiencia [@TBD-3] [3h]
- [ ] T-43 — Estados de loading + error (Suspense + streaming opcional) [@TBD-3] [1h]
- [ ] T-44 — Botón "copiar a clipboard" por canal [@TBD-3] [0.5h]
- [ ] T-45 — Badge "requires_review" visible cuando legal filter triggered [@TBD-3] [0.5h]

## Tests

- [ ] T-50 — `kit_generator.test.ts` con mock provider + snapshot [@TBD-4] [1.5h]
- [ ] T-51 — Integration test con caso fixture: end-to-end action [@TBD-4] [2h]
- [ ] T-52 — Smoke test manual con 5 casos reales de prod [@TBD-4] [1h]

## Documentación

- [ ] T-60 — Actualizar `docs/AMPLIFIER.md` con detalles MVP shipped [@TBD-4] [0.5h]
- [ ] T-61 — README `packages/amplifier/README.md` con API [@TBD-4] [0.5h]
- [ ] T-62 — Capturar latencias p50/p95 en metrics doc [@TBD-4] [0.3h]

## Cierre

- [ ] T-70 — Self-review [@TBD-4] [0.5h]
- [ ] T-71 — Demo a equipo (15 min) [@TBD-4] [0.25h]
- [ ] T-72 — PR `feat: Civic Amplifier MVP con kit generator + legal filter (SPEC-0004)` [@TBD-4] [0.2h]
- [ ] T-73 — Aprobación @TBD-3 + @MiguelAAR10 [@reviewers]
- [ ] T-74 — Squash + merge [@TBD-4]
- [ ] T-75 — Mover spec a `specs/completed/` [@TBD-4] [0.2h]

---

## Estimación

| Sección | Horas |
|---------|-------|
| Schema + AI SDK | 5.0 |
| Legal filter | 3.5 |
| DB layer | 3.0 |
| UI | 9.0 |
| Tests | 4.5 |
| Docs | 1.3 |
| Cierre | 1.4 |
| **Total** | **~28h** |

3.5 días en colaboración entre @TBD-4 (AI) y @TBD-3 (Frontend).
