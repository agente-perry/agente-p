# PLAN — SPEC-0004 Civic Amplifier MVP

## Arquitectura

```
[apps/web admin UI]
      │ click "Generar kit"
      ▼
[Server Action: generateKit(caseId)]
      │
      ├─→ fetch case from Supabase (RLS check: editor/admin only)
      │
      ├─→ build RiskCaseInput from case + flags + entities
      │
      ├─→ AI SDK v6: generateText({
      │       model: gateway('anthropic/claude-opus-4.7'),
      │       experimental_output: Output.object({ schema: KitOutputSchema }),
      │       system: SYSTEM_PROMPT,
      │       prompt: TITLES_PROMPT(input) + DOSSIER_PROMPT(input),
      │   })
      │
      ├─→ For each generated string → legalSafe(text)
      │     if !ok: replace with suggestion, mark requires_review
      │
      ├─→ Persist:
      │     - case_narratives rows (one per audience)
      │     - distribution_assets rows (one per channel)
      │
      └─→ Return KitOutput to client
              │
              ▼
[Client UI: tabs por audiencia + preview + botón copiar]
```

## Componentes

| Path | Cambio |
|------|--------|
| `packages/amplifier/src/index.ts` | export nueva función `generateKit()` |
| `packages/amplifier/src/kit_generator.ts` | NUEVO — orquesta AI SDK + legal filter + persist |
| `packages/amplifier/src/schemas/kit.ts` | NUEVO — zod schema de KitOutput |
| `apps/web/app/(admin)/editorial/caso/[slug]/actions.ts` | NUEVO — Server Action `generateKit` |
| `apps/web/app/(admin)/editorial/caso/[slug]/page.tsx` | NUEVO — UI con botón + tabs |
| `apps/web/components/amplifier/KitPreview.tsx` | NUEVO — render por canal |
| `apps/web/lib/ai/provider.ts` | NUEVO — wrapper AI SDK con provider + gateway |
| `packages/amplifier/tests/legal_filter.test.ts` | NUEVO — 20+ casos |
| `packages/amplifier/tests/kit_generator.test.ts` | NUEVO — snapshot con mock provider |

## Schemas

### KitOutput (zod)

```typescript
// packages/amplifier/src/schemas/kit.ts
import { z } from 'zod';

const titleVariantSchema = z.object({
  text: z.string().max(140),
  rationale: z.string(),
  legal_risk: z.enum(['bajo', 'medio', 'alto']),
  requires_review: z.boolean().optional(),
});

export const KitOutputSchema = z.object({
  titles: z.object({
    ciudadano: z.array(titleVariantSchema).length(5),
    periodistico: z.array(titleVariantSchema).length(5),
    redes: z.array(titleVariantSchema).length(5),
    sms: z.array(titleVariantSchema).max(3),
    institucional: z.array(titleVariantSchema).max(3),
    recomendado: z.object({
      audience: z.string(),
      text: z.string(),
    }),
  }),
  dossier: z.object({
    titular: z.string().max(90),
    subtitulo: z.string().max(160),
    resumen_ciudadano: z.string(),
    whatsapp: z.string().max(700),
    sms: z.string().max(140),
    x_thread: z.array(z.string()).length(5),
    linkedin: z.string(),
    ong_release: z.string(),
    preguntas_autoridad: z.array(z.string()).length(5),
    disclaimer: z.string(),
    nivel_riesgo_comunicacional: z.enum(['bajo', 'medio', 'alto']),
    razon_riesgo_comunicacional: z.string(),
  }),
});

export type KitOutput = z.infer<typeof KitOutputSchema>;
```

## Server Action

```typescript
// apps/web/app/(admin)/editorial/caso/[slug]/actions.ts
'use server';

import { createClient } from '@/lib/db/server';
import { generateKit } from '@contralatam/amplifier';
import { redirect } from 'next/navigation';

export async function regenerateKitAction(caseSlug: string) {
  const supabase = await createClient();

  // 1. Verify role
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/login');

  const { data: profile } = await supabase
    .from('profiles')
    .select('role')
    .eq('id', user.id)
    .single();

  if (!['editor', 'admin'].includes(profile?.role)) {
    throw new Error('Forbidden');
  }

  // 2. Fetch case + entities + flags
  const { data: caseData } = await supabase.rpc('get_case_full', { p_slug: caseSlug });
  if (!caseData) throw new Error('Case not found');

  // 3. Generate
  const kit = await generateKit(caseData);

  // 4. Persist narratives + assets
  await persistKit(supabase, caseData.id, kit);

  return kit;
}
```

## AI SDK integration

```typescript
// packages/amplifier/src/kit_generator.ts
import { generateText, Output } from 'ai';
import { gateway } from '@ai-sdk/gateway';
import { SYSTEM_PROMPT, TITLES_PROMPT, DOSSIER_PROMPT } from './prompts';
import { KitOutputSchema, type KitOutput } from './schemas/kit';
import { legalSafe } from './legal_filter';
import type { RiskCaseInput } from './types';

export async function generateKit(input: RiskCaseInput): Promise<KitOutput> {
  // AI SDK v6 structured output: generateText + experimental_output: Output.object().
  const { experimental_output: kit } = await generateText({
    model: gateway('anthropic/claude-opus-4.7'),
    experimental_output: Output.object({ schema: KitOutputSchema }),
    system: SYSTEM_PROMPT,
    prompt: `${TITLES_PROMPT(input)}\n\n${DOSSIER_PROMPT(input)}`,
    temperature: 0.4,
  });

  // Post-process: legal filter on every string
  return applyLegalFilter(kit);
}

function applyLegalFilter(kit: KitOutput): KitOutput {
  // Walk all titles + dossier strings; apply legalSafe; mutate as needed
  // ...
}
```

## Performance

- LLM call: 5–15s para Claude Opus con `generateText` + `Output.object`
- Legal filter: < 50ms para 20 strings
- DB persist: < 200ms
- Total target: < 20s p95

Si > 25s → migrar a `streamText` con `Output.object` para mejorar UX.

## Tests

- `legal_filter.test.ts`:
  - "Empresa corrupta" → suggestion "que presenta señales de riesgo"
  - "X robó dinero" → suggestion contiene "recibió un contrato"
  - "Patrón atípico merece revisión" → ok=true
  - Edge: tildes, mayúsculas mixtas, palabras dentro de palabras (corruptismo ≠ corrupto)
- `kit_generator.test.ts`:
  - Snapshot con mock provider que retorna fixture JSON
  - Verifica que toda string en output pasó por legalSafe
  - Verifica schema válido

## Rollout

- Branch: `feat/SPEC-0004-civic-amplifier-mvp`
- Feature flag: `NEXT_PUBLIC_AMPLIFIER_ENABLED=true` (env var)
- Solo accesible en `/editorial/*` (role editor/admin via RLS)
- No auto-publica nada — humano debe `editorial_reviews.approved_for_publication=true`
