export type RiskLevel = "BAJO" | "MEDIO" | "ALTO" | "CRITICO";

export type RiskCaseInput = {
  slug: string;
  district: string;
  region: string;
  entity_name: string;
  supplier_name: string;
  amount: number;
  currency: "PEN" | "USD";
  risk_score: number;
  risk_level: RiskLevel;
  risk_flags: string[];
  source_count: number;
  case_url: string;
  evidence_summary?: string;
};

export type TitleVariant = {
  text: string;
  rationale: string;
  legal_risk: "bajo" | "medio" | "alto";
  requires_review?: boolean;
};

export type GeneratedTitles = {
  ciudadano: TitleVariant[];
  periodistico: TitleVariant[];
  redes: TitleVariant[];
  sms: TitleVariant[];
  institucional: TitleVariant[];
  recomendado: { audience: string; text: string };
};

export type GeneratedDossier = {
  titular: string;
  subtitulo: string;
  resumen_ciudadano: string;
  whatsapp: string;
  sms: string;
  x_thread: string[];     // 5 posts
  linkedin: string;
  ong_release: string;
  preguntas_autoridad: string[];  // 5 items
  disclaimer: string;
  nivel_riesgo_comunicacional: "bajo" | "medio" | "alto";
  razon_riesgo_comunicacional: string;
};
