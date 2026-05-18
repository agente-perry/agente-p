import type { RiskCaseInput } from "../types";

export const TITLES_PROMPT = (input: RiskCaseInput): string => `Dado el caso siguiente, genera títulos para 5 audiencias.

DATOS DEL CASO:
${JSON.stringify(input, null, 2)}

GENERA JSON con la estructura exacta:
{
  "ciudadano": [
    { "text": "...", "rationale": "...", "legal_risk": "bajo|medio|alto" }
    // 5 títulos
  ],
  "periodistico": [...5 títulos],
  "redes": [...5 títulos],
  "sms": [...3 títulos de máximo 130 caracteres],
  "institucional": [...3 títulos],
  "recomendado": { "audience": "ciudadano|periodistico|redes|sms|institucional", "text": "..." }
}

REGLAS POR AUDIENCIA:

CIUDADANO — claro, simple, directo.
  Ejemplo: "Contrato de S/ 1.2M en Ancón presenta señales que merecen revisión"

PERIODÍSTICO — más preciso, con dato fuerte.
  Ejemplo: "Municipalidad adjudicó S/ 1.2M a proveedor con patrón recurrente de contratación"

REDES — compartible, gancho emocional pero responsable.
  Ejemplo: "🚨 Tres señales de riesgo en este contrato de tu distrito"

SMS — máximo 130 chars, con CTA breve.
  Ejemplo: "Alerta Contralatam: contrato de S/1.2M en Ancón requiere revisión. Ver evidencia: [link]"

INSTITUCIONAL — formal, dirigido a ONG/auditores.
  Ejemplo: "Se identificaron señales de riesgo que justifican una revisión documentaria"

Para cada título indica el riesgo legal (bajo/medio/alto) y por qué funciona.`;
