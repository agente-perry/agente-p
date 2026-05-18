# SPEC-0004: Civic Amplifier MVP — Generador de títulos + WhatsApp + SMS + preguntas

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-0004 |
| **Estado** | approved |
| **Owner** | @TBD-4 (AI / Editorial) |
| **Reviewers** | @TBD-3 (Frontend), @MiguelAAR10 |
| **Sprint / Fase** | F4 — Civic Amplifier |
| **Creado** | 2026-05-14 |
| **Depende de** | SPEC-0003 (casos existen) |

---

## 1. Problema

Tenemos casos detectados en `risk_cases` pero son crudos: solo score + flags + entidades. No hay forma de transformarlos en mensaje ciudadano. Un periodista o ciudadano no entiende "ratio_p95 > 1.0, num_postores=1, condicion_domicilio=NO HABIDO" sin contexto narrativo.

## 2. Objetivo

> Después de este spec, cada caso en `risk_cases` puede generar (vía Server Action en Next.js) un kit de difusión: 5 títulos ciudadanos + WhatsApp + SMS + hilo X + 5 preguntas para autoridad, todo filtrado por `legalSafe()`.

## 3. Contexto

- Stub completo de `packages/amplifier/` ya scaffolded en commit f7a1141.
- Prompts en `packages/amplifier/src/prompts/{system,titles,dossier}.ts`.
- Legal filter en `packages/amplifier/src/legal_filter.ts`.
- Schema DB: `case_narratives`, `distribution_assets`, `editorial_reviews` (migración 0005).
- Doc: [`docs/AMPLIFIER.md`](../../../docs/AMPLIFIER.md).

## 4. Criterios de aceptación

- [ ] Server Action `generateKit(caseId, audience?)` retorna `{titles, whatsapp, sms, x_thread, questions, dossier}` en < 30s
- [ ] Toda string generada pasa por `legalSafe()` antes de retornar al cliente
- [ ] Si `legalSafe.ok=false`, el campo `requires_review=true` y se persiste `legal_risk='medio'` o `'alto'`
- [ ] Output persiste en `case_narratives` con `status='draft'` (NO `published` automático)
- [ ] Tests unitarios `test_legal_filter.test.ts` con 20+ casos pasan
- [ ] Snapshot test con caso fixture: output JSON estable entre runs (mismo model + temperature)
- [ ] Integración en `apps/web/app/(admin)/editorial/caso/[slug]/page.tsx` con botón "Generar kit"

## 5. Out of scope

- ❌ OG card generator (`next/og`) — SPEC futuro
- ❌ Envío SMS via Zavu — SPEC-0009
- ❌ Editor manual del dossier — SPEC-0008
- ❌ Métricas de impacto (clicks, shares) — F5
- ❌ Versiones por tono (institutional/educativo) — solo "ciudadano" en MVP

## 6. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| LLM ignora palabras prohibidas y emite "corrupto" | `legalSafe()` BLOQUEANTE post-LLM, no solo prompt engineering |
| Cost overrun en producción | Cache por `case_id` + invalidación manual; rate limit en Server Action |
| Latencia > 30s (timeout Vercel) | Streaming con AI SDK + Suspense en cliente |
| Output JSON malformado | `generateObject` con schema zod estricto |

## 7. Métricas de éxito

- 20 casos de testing manual → 100% pasan legal filter en primer intento (o suggestion aceptable)
- Tiempo p50 generación: < 15s
- 0 outputs publicados con palabra prohibida en producción

## 8. Decisiones rechazadas

- ❌ Generar al detectar caso (background job) — preferimos on-demand por humano para evitar contenido nunca usado
- ❌ Mostrar copy a usuarios anónimos sin revisión editorial — viola constitución cap. V
- ❌ Provider único (Anthropic only) — usar AI Gateway con fallback
