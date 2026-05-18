export const AUDIENCES = {
  ciudadano: {
    label: "Ciudadano",
    goal: "Entender rápido qué pasa en su distrito.",
    defaultTone: "simple",
  },
  periodista: {
    label: "Periodista",
    goal: "Encontrar una historia investigable.",
    defaultTone: "periodistico",
  },
  activista: {
    label: "Activista",
    goal: "Convertir evidencia en presión social responsable.",
    defaultTone: "activista",
  },
  ong: {
    label: "ONG / auditor",
    goal: "Validar el caso para acción institucional.",
    defaultTone: "institucional",
  },
  sms: {
    label: "SMS",
    goal: "Alerta breve con link a evidencia.",
    defaultTone: "sms",
  },
} as const;

export type Audience = keyof typeof AUDIENCES;
