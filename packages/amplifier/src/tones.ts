export const TONES = {
  simple: "Lenguaje cotidiano. Frases cortas. Cero jerga.",
  periodistico: "Preciso. Dato fuerte primero. Sin adjetivos cargados.",
  institucional: "Formal. Tercera persona. Citar metodología y fuente.",
  activista: "Movilizador pero responsable. Verbos de acción cívica.",
  sms: "Máximo impacto en 140 chars. URL acortada.",
  educativo: "Explicar el concepto. Cómo verificar el dato.",
} as const;

export type Tone = keyof typeof TONES;
