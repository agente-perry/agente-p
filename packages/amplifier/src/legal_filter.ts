/**
 * Legal-safe filter for civic communication.
 *
 * MUST be called on every LLM-generated string before it is shown to a user
 * or persisted as `published`. Returns suggestion when forbidden words found.
 *
 * See docs/METHODOLOGY.md § "Lenguaje legal-safe".
 */

export const FORBIDDEN_WORDS: readonly string[] = [
  "corrupto",
  "corrupta",
  "corruptos",
  "corruptas",
  "corrupción",
  "robó",
  "robaron",
  "robar",
  "ladrón",
  "ladrones",
  "mafioso",
  "mafia",
  "culpable",
  "criminal",
  "delito",
  "delincuente",
  "cómplice",
  "cómplices",
];

export const SOFT_REPLACEMENTS: Record<string, string> = {
  corrupto: "que presenta señales de riesgo",
  corrupta: "que presenta señales de riesgo",
  corrupción: "señales de riesgo",
  robó: "recibió un contrato que merece revisión",
  robaron: "recibieron contratos que merecen revisión",
  mafia: "red de relaciones cruzadas",
  cómplice: "vinculado",
  cómplices: "vinculados",
  delito: "patrón atípico",
  criminal: "atípico",
  delincuente: "involucrado en señales de riesgo",
};

export type LegalCheck = {
  ok: boolean;
  matches: string[];
  suggestion?: string;
  legalRisk: "bajo" | "medio" | "alto";
};

export function legalSafe(text: string): LegalCheck {
  const lower = text.toLowerCase();
  const matches = FORBIDDEN_WORDS.filter((w) => lower.includes(w));

  if (matches.length === 0) {
    return { ok: true, matches: [], legalRisk: "bajo" };
  }

  let suggestion = text;
  for (const [bad, good] of Object.entries(SOFT_REPLACEMENTS)) {
    suggestion = suggestion.replace(new RegExp(bad, "gi"), good);
  }

  const legalRisk = matches.length >= 3 ? "alto" : "medio";

  return { ok: false, matches, suggestion, legalRisk };
}
