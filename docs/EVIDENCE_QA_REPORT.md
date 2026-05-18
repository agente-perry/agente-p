# Evidence QA Report — Activity 6

> **Fecha:** 2026-05-17
> **Rol:** Investigador Periodístico Senior + Data QA Lead
> **Propósito:** Auditoría editorial de los 3 dossiers producidos en Activity 5.
> **Metodología:** Lectura directa de flags.json, dossier.json y páginas fuente por número exacto.

---

## 1. Resumen Ejecutivo

Se auditaron **12 flags** en total distribuidas entre 3 documentos.

| Caso | Flags | Genuinos | Falso positivo | Débil / Context-dependent |
|---|---:|---:|---:|---:|
| Salud / ESSALUD | 6 | 0 | 5 | 1 |
| Ambiente / ANA | 4 | 0 | 4 | 0 |
| Ambiente / MINAM | 2 | 0 | 2 | 0 |
| **Total** | **12** | **0** | **11** | **1** |

**Veredicto editorial:** Ningún flag pasa el estándar de evidencia periodística sin reservas.
La causa raíz no es falta de señales en la realidad peruana — es sobre-activación de dos patrones de detección (ver sección 5).

---

## 2. Contexto Crítico: Tipo de Documento

Antes de evaluar cada flag, es indispensable señalar que los 3 PDFs procesados **no son TDRs puros**:

| Caso | Documento analizado | ¿Es el TDR real? |
|---|---|---|
| Salud / ESSALUD | Pliego de Absolución de Consultas y Observaciones (212 pp) | NO — es el documento de respuestas a preguntas de postores |
| Ambiente / ANA | Pliego de Absolución de Consultas y Observaciones (181 pp) | NO — mismo tipo |
| Ambiente / MINAM | Bases Administrativas (23 pp) | PARCIALMENTE — más cercano al documento fuente |

El **Pliego de Absolución** responde preguntas que bidders enviaron sobre el proceso. El lenguaje es inherentemente procesal y administrativo. El **TDR real** (requisitos técnicos, experiencia, entregables) está en las **Bases Integradas**, que en el caso de ESSALUD y ANA se encuentran en archivos RAR/ZIP aún no accesibles.

Esta observación explica la mayoría de los falsos positivos: las reglas actuales detectan palabras que son normales en documentos procesales pero no en TDRs reales.

---

## 3. Auditoría Flag por Flag

### 3.1 Caso Salud / ESSALUD — AS-SM-55-2023-ESSALUD/GCL-1

**Documento:** Pliego de Absolución de Consultas y Observaciones
**Contrato:** Servicio de Seguridad y Vigilancia en Instalaciones ESSALUD a Nivel Nacional, 1095 días (3 años)
**Monto:** S/ 195,383,235.96
**Ganador (OCDS):** VIPROSEG S.A.C. (RUC: 20605681281)
**Postores que hicieron consultas:** H&A ONE SOLUTION S.A.C., SERVIGENVIG S.A.C., JL SEGURIDAD S.R.L., BOINAS DORADAS S.A.C., VIPROSEG S.A.C.

---

#### Flag 1 — OBSOLETE_PHYSICAL_FORMAT · Página 2 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí — texto extraído de la página |
| Cita sostiene la señal | **NO** |
| Página verificada | Sí — pág. 2 |
| Legal-safe | Sí |
| Comprensible para ciudadano | No — requiere contexto técnico |
| Potencia de pitch | Muy baja |
| Riesgo de falso positivo | **5/5 — FALSO POSITIVO CONFIRMADO** |

**Contexto real:** La página 2 contiene la pregunta #2 del postor H&A ONE SOLUTION S.A.C. sobre la obligación de actualizar el Registro Nacional de Proveedores (RNP). La regla TDR-R002 activó por la presencia de la palabra "impreso" dentro de la cita de la Directiva N° 001-2020-OSCE/CD. El texto no exige entrega en papel — cita una norma regulatoria que menciona la palabra "impreso" de forma incidental.

**Causa raíz del falso positivo:** El patrón `r"\bimpreso\b"` captura referencias legales que citan documentos donde aparece esa palabra, no requisitos de entrega física.

---

#### Flag 2 — OBSOLETE_PHYSICAL_FORMAT · Página 3 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí |
| Cita sostiene la señal | **NO** |
| Riesgo de falso positivo | **5/5 — FALSO POSITIVO CONFIRMADO** |

**Contexto real:** Pregunta #3 de H&A ONE SOLUTION sobre la empresa BOINAS DORADAS S.A.C. Misma causa que flag 1: referencia a Directiva OSCE que contiene "impreso" de forma incidental.

---

#### Flag 3 — LOW_TRACEABILITY_OUTPUT · Página 6 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí |
| Cita sostiene la señal | **NO** |
| Riesgo de falso positivo | **5/5 — FALSO POSITIVO CONFIRMADO** |

**Contexto real:** Pregunta #5 sobre si las facultades del representante legal deben estar notariadas. La cita menciona "la presentación de la oferta, sea expresada de forma directa por el proveedor o por medio de un representante" — lenguaje completamente estándar de cualquier proceso de contratación. La regla TDR-R005 activó por el token `presentacion` que aparece en esta frase común.

**Causa raíz:** El patrón `r"\b(?:powerpoint|ppt|presentacion)\b"` es demasiado amplio. "presentación" es la palabra más común en documentos de contratación pública peruana.

---

#### Flag 4 — OBSOLETE_PHYSICAL_FORMAT · Página 13 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí |
| Cita sostiene la señal | **NO** |
| Riesgo de falso positivo | **4/5 — FALSO POSITIVO PROBABLE** |

**Contexto real:** Pregunta #12 sobre si las comunicaciones de apertura de sucursales deben corresponder a la provincia donde se prestará el servicio. ESSALUD responde citando la Directiva N° 001-2019-OSCE/CD para contratos de Vigilancia Privada ("Bases Estándar"). La regla detectó "impreso" dentro de esta cita normativa.

**Observación editorial:** El requisito de documentar sucursales en las provincias donde se prestará el servicio de vigilancia tiene lógica operacional. No es una señal de riesgo per se.

---

#### Flag 5 — LOW_TRACEABILITY_OUTPUT · Página 13 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí |
| Cita sostiene la señal | **NO directo, contexto relevante marginal** |
| Riesgo de falso positivo | **3/5 — DÉBIL / CONTEXT-DEPENDENT** |

**Contexto real:** Información sobre el requisito de "comunicación de apertura de sucursales" en lugares de prestación del servicio para empresas de Intermediación Laboral. La cita menciona "presentación de copia simple de apertura de sucursales, oficinas, centros de trabajo". La regla TDR-R005 activó en "presentación".

**Por qué es context-dependent:** Para un contrato nacional de vigilancia (1095 días, S/ 195M), exigir que el proveedor tenga oficinas registradas en cada provincia de operación es un requisito potencialmente restrictivo. Sin embargo, es un requisito estándar del sector de seguridad privada en Perú. Merece análisis pero no es señal inequívoca de riesgo.

---

#### Flag 6 — LOW_TRACEABILITY_OUTPUT · Página 17 · Score +10

| Criterio | Evaluación |
|---|---|
| Cita textual real | Sí |
| Cita sostiene la señal | **PARCIALMENTE** |
| Página verificada | Sí — pág. 17 |
| Legal-safe | Sí |
| Comprensible para ciudadano | Sí — con explicación |
| Potencia de pitch | **3/5 — La más fuerte del conjunto** |
| Riesgo de falso positivo | **2/5 — SEÑAL REAL, CONTEXTO DISCUTIBLE** |

**Contexto real verificado (página 17, pregunta #16):**

Un postor preguntó: *"La documentación para el perfeccionamiento del contrato ¿Podrá ser presentado por mesa de partes virtual?"*

ESSALUD respondió: *"Para dicho efecto el postor ganador de la buena pro, dentro del plazo previsto en el artículo 141 del Reglamento, debe presentar la documentación requerida en el en Jr. Domingo Cueto N° 120, Primer Piso, Jesús María - Lima"* y aclaró que *"la Mesa de Partes de la Entidad se encuentra ate[ndiendo de forma presencial]."*

**Evaluación periodística:** Para un contrato de **S/ 195 millones** de alcance **nacional** (todas las instalaciones ESSALUD del país), la exigencia de que el ganador se presente **físicamente** en Lima para el perfeccionamiento del contrato es una condición que:
- Podría crear una barrera geográfica para proveedores de regiones
- Es verificable: la restricción está en la página 17, pregunta #16
- Es discutible: en 2023-2024, la "Mesa de Partes Virtual" existe en Perú y muchas entidades la usan

**Sin embargo:** Esta es una decisión institucional que puede tener fundamento en normas de seguridad o en la naturaleza del contrato. **No es prueba de irregularidad.** Es una señal que merece pregunta pública, no una acusación.

---

### 3.2 Caso Ambiente / ANA — AS-SM-6-2024-ANA-1

**Documento:** Pliego de Absolución de Consultas y Observaciones
**Monto:** S/ 2,995,887.60

#### Flags 1-3 — LOW_TRACEABILITY_OUTPUT · Páginas 4, 5, 8

| Criterio | Evaluación |
|---|---|
| Cita sostiene la señal | **NO — todos falsos positivos** |
| Causa | "presentación" en contextos de tipo de cambio y garantías |
| Riesgo FP | 5/5 |

**Contexto:** Los tres flags se activan porque las páginas mencionan "presentación de ofertas" (contexto de tipo de cambio SBS) o "presentación de la Garantía de fiel cumplimiento en formato digital". El flag de página 5 es especialmente clarificador: la cita indica que la garantía SÍ puede presentarse en formato digital, lo que es lo opuesto de lo que el flag sugiere.

---

#### Flag 4 — OBSOLETE_PHYSICAL_FORMAT · Página 79

| Criterio | Evaluación |
|---|---|
| Cita sostiene la señal | **NO** |
| Causa | Cita de Directiva OSCE con "impreso" incidental |
| Riesgo FP | 5/5 |

---

### 3.3 Caso Ambiente / MINAM — AS-SM-16-2024-MINAM/OGA-1

**Documento:** Bases Administrativas
**Monto:** S/ 393,330.00

#### Flags 1-2 — LOW_TRACEABILITY_OUTPUT · Páginas 11, 14

| Criterio | Evaluación |
|---|---|
| Cita sostiene la señal | **NO** |
| Página 11 | "presentación de los siguientes documentos" en cláusula de pago con desglose (Reporte de Orden de Trabajo) — lenguaje de pago con entregables, no de bajo trazabilidad |
| Página 14 | "previa presentación de una carta fianza o póliza de caución" para adelanto directo — garantía financiera estándar |
| Riesgo FP | 5/5 / 5/5 |

---

## 4. Diagnóstico de Causas Raíz

### 4.1 Problema principal: sobre-sensibilidad de TDR-R005

La regla `LOW_TRACEABILITY_OUTPUT` activa con el patrón `r"\b(?:powerpoint|ppt|presentacion)\b"`.

**El problema:** "presentación" es la palabra más frecuente en la prosa contractual peruana. Aparece en:
- "presentación de la oferta"
- "presentación de documentos"
- "presentación de garantías"
- "presentación de consultas"
- "presentación del informe"

El patrón original fue diseñado para capturar "PowerPoint" y "PPT" como entregables de baja trazabilidad. La adición de "presentación" fue demasiado amplia.

**Fix recomendado:**
```python
# En lugar de:
re.compile(r"\b(?:powerpoint|ppt|presentacion)\b")
# Usar:
re.compile(r"\b(?:powerpoint|presentaci[oó]n\s+en\s+powerpoint|formato\s+ppt)\b")
```

### 4.2 Problema secundario: TDR-R002 captura citas normativas

El patrón `r"\bimpreso\b"` captura la palabra "impreso" dentro de citas de Directivas OSCE que usan ese término en contextos regulatorios. Los documentos verificados citan la Directiva N° 001-2020-OSCE/CD y N° 001-2019-OSCE/CD, que contienen "impreso" como parte de su redacción normativa.

**Fix recomendado:** Excluir contextos donde "impreso" aparece dentro de citas de Directivas OSCE (p.ej., usar una exclusión de ventana: si la página ya contiene "OSCE/CD" y "Directiva", no activar).

### 4.3 Problema estructural: tipo de documento incorrecto

Los PDFs con texto digital disponibles son **Pliegos de Absolución** (respuestas a preguntas), no **Bases Integradas** (TDRs reales con requisitos técnicos). Las señales de riesgo genuinas — experiencia excesiva, marcas específicas, certificaciones ISO, equipamiento particular — están en las Bases Integradas, que en los casos de ESSALUD y ANA están en archivos RAR no procesados.

---

## 5. Tabla de Riesgo por Flag (Score Ajustado Post-QA)

| Case | Flag | Página | Score Automático | Score Post-QA | Veredicto |
|---|---|---:|---:|---:|---|
| Salud/ESSALUD | OBSOLETE_PHYSICAL_FORMAT | 2 | 10 | 0 | Falso positivo |
| Salud/ESSALUD | OBSOLETE_PHYSICAL_FORMAT | 3 | 10 | 0 | Falso positivo |
| Salud/ESSALUD | LOW_TRACEABILITY_OUTPUT | 6 | 10 | 0 | Falso positivo |
| Salud/ESSALUD | OBSOLETE_PHYSICAL_FORMAT | 13 | 10 | 0 | Falso positivo |
| Salud/ESSALUD | LOW_TRACEABILITY_OUTPUT | 13 | 10 | 3 | Débil / context-dependent |
| Salud/ESSALUD | LOW_TRACEABILITY_OUTPUT | 17 | 10 | **8** | **Señal real — entregable físico** |
| Ambiente/ANA | LOW_TRACEABILITY_OUTPUT | 4 | 10 | 0 | Falso positivo |
| Ambiente/ANA | LOW_TRACEABILITY_OUTPUT | 5 | 10 | 0 | Falso positivo (opuesto) |
| Ambiente/ANA | LOW_TRACEABILITY_OUTPUT | 8 | 10 | 0 | Falso positivo |
| Ambiente/ANA | OBSOLETE_PHYSICAL_FORMAT | 79 | 10 | 0 | Falso positivo |
| Ambiente/MINAM | LOW_TRACEABILITY_OUTPUT | 11 | 10 | 0 | Falso positivo |
| Ambiente/MINAM | LOW_TRACEABILITY_OUTPUT | 14 | 10 | 0 | Falso positivo |

**Score post-QA: ESSALUD = 11/60 | ANA = 0/40 | MINAM = 0/20**

---

## 6. Hallazgos Editoriales No Generados por Flags

Estos hallazgos emergen del análisis del contexto documental, no de los flags automáticos:

### 6.1 Cinco empresas de seguridad privada participaron en la etapa de consultas

El análisis de las páginas del Pliego de Absolución revela que al menos estas empresas presentaron consultas:

| Empresa | RUC | Páginas aprox. | ¿Ganó el contrato? |
|---|---|---|---|
| H & A ONE SOLUTION S.A.C. | 20604373787 | 2–17 | No |
| SERVIGENVIG S.A.C. | 20602088... | ~50+ | No |
| JL SEGURIDAD S.R.L. | 20601621828 | ~80–100 | No |
| BOINAS DORADAS S.A.C. | 20566047234 | ~140–180 | No |
| VIPROSEG S.A.C. | 20605681281 | ~210 | **Sí** |

Esta es información pública y auditablede valor: el ganador del contrato también participó en la etapa de consultas. No implica irregularidad — es práctica normal. Pero es un dato verificado.

### 6.2 La exigencia de presencialidad para perfeccionar el contrato

Hallazgo verificado en página 17: para un contrato de S/ 195 millones de alcance nacional,  el perfeccionamiento requiere presentación física en Lima (Jr. Domingo Cueto N° 120, Jesús María). Esta condición, en un contrato nacional, es un dato que merece análisis de política pública, aunque no es señal de corrupción.

---

## 7. Recomendaciones Técnicas para Activity 6B

Se recomienda **no publicar ninguno de los 3 dossiers actuales como evidencia periodística primaria** sin las correcciones siguientes:

### 7.1 Mejoras de reglas urgentes

```
TDR-R002 (OBSOLETE_PHYSICAL_FORMAT):
  - Excluir coincidencias dentro de 150 chars de "Directiva N°" o "OSCE/CD"
  - Agregar: r"\bentrega\s+(?:física|fisica|en\s+físico)\b"
  - Agregar: r"\bsolo\s+(?:físico|fisico|presencial)\b"

TDR-R005 (LOW_TRACEABILITY_OUTPUT):
  - Eliminar: r"\b(?:powerpoint|ppt|presentacion)\b"
  - Reemplazar: r"\b(?:presentacion\s+en\s+powerpoint|en\s+formato\s+ppt|powerpoint)\b"
  - Agregar: r"\binforme\s+final\s+(?:en\s+)?powerpoint\b"
  - Agregar: r"\bun\s+solo\s+(?:informe|entregable|producto)\b"
  - Agregar: r"\bentregable\s+(?:es\s+)?un\b"
```

### 7.2 Targets para próxima descarga TDR

Para obtener señales genuinas, priorizar descarga de:
- Bases Integradas de ESSALUD (los RAR pendientes)
- Contratos con certificaciones ISO explícitas (buscar `iso.*\d{4,5}` en metadata)
- Contratos con "experiencia de 10 años" o similar en objeto
- Contratos con plazos de convocatoria < 7 días

### 7.3 Mejores categorías de documentos para detección

Priorizar análisis de **Bases Integradas** sobre **Pliegos de Absolución**. Las Bases Integradas contienen:
- Especificaciones técnicas del servicio
- Requisitos de experiencia del postor
- Estructura de evaluación y puntajes
- Entregables con detalle

---

## 8. Conclusión

La pipeline de AgentePerry **funciona correctamente** en términos de extracción de texto, chunking y aplicación de reglas. El problema es editorial-técnico: las reglas actuales fueron calibradas para documentos TDR técnicos, pero los PDFs disponibles con texto digital son Pliegos de Absolución (documentos procesales).

**Para la demo del hackathon, la recomendación es:**

1. Usar el caso ESSALUD por el contexto narrativo (S/ 195M, 3 años, vigilancia nacional) y el hallazgo de página 17, siendo explícitos sobre que es una señal preliminar que el sistema detectó, no una prueba de irregularidad.

2. Explicar honestamente que el sistema continúa mejorando sus reglas de detección.

3. El valor demostrativo es la **capacidad de la pipeline**: leer un PDF real de 212 páginas, extraer 445 chunks, detectar patrones y generar una solicitud de transparencia lista para enviar.

**El producto ya funciona. Las reglas necesitan ajuste. Esos son dos hechos diferentes y ambos deben decirse en la demo.**
