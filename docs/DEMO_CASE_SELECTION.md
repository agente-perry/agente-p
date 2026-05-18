# Demo Case Selection — Activity 6

> **Fecha:** 2026-05-17
> **Rol:** Investigador Periodístico Senior + Editor de Evidencia
> **Input:** 3 dossiers + QA completa de EVIDENCE_QA_REPORT.md
> **Output:** Caso seleccionado para demo del hackathon

---

## 1. Tabla Comparativa

| Criterio | ESSALUD (Salud) | ANA (Ambiente/Min) | MINAM (Ambiente) |
|---|---|---|---|
| **Entidad** | Seguro Social de Salud | Autoridad Nacional del Agua | Ministerio del Ambiente |
| **Sector** | Salud | Ambiente/Minería | Ambiente |
| **Objeto del contrato** | Vigilancia privada nacional (1095 días) | Adjudicación simplificada (servicios) | Servicios de mantenimiento |
| **Monto** | **S/ 195,383,235.96** | S/ 2,995,887.60 | S/ 393,330.00 |
| **Tipo de documento analizado** | Pliego de Absolución (Q&A) | Pliego de Absolución (Q&A) | Bases Administrativas |
| **Páginas** | **212** | 181 | 23 |
| **Chunks** | **445** | 365 | 49 |
| **Flags automáticos** | 6 | 4 | 2 |
| **Score automático** | 60 (ALTO) | 40 (MEDIO) | 20 (BAJO) |
| **Score post-QA** | **11** | 0 | 0 |
| **Flags genuinos** | 1 (débil) | 0 | 0 |
| **Mejor evidencia textual** | Pág. 17: exigencia presencial Lima para S/ 195M nacional | — | — |
| **Empresas en proceso** | ≥ 5 identificadas (incl. ganador) | No analizado | No analizado |
| **Ganador conocido** | VIPROSEG S.A.C. (RUC: 20605681281) | No visible | No visible |
| **Impacto ciudadano** | **5/5** — salud pública, S/ 195M | 2/5 | 1/5 |
| **Fuerza periodística flags** | 2/5 | 1/5 | 1/5 |
| **Fuerza narrativa del contexto** | **5/5** | 2/5 | 1/5 |
| **Riesgo de falso positivo** | 4/5 (banderas técnicas) | 5/5 | 5/5 |
| **Facilidad de explicar en 60 seg** | **4/5** | 2/5 | 1/5 |
| **Recomendación** | **SELECCIONADO** | Descartar por ahora | Descartar por ahora |

---

## 2. Decisión

### Caso seleccionado: ESSALUD — AS-SM-55-2023-ESSALUD/GCL-1

**Producto:** Servicio de Seguridad y Vigilancia en las Instalaciones de ESSALUD a Nivel Nacional, 1095 días
**Monto:** S/ 195,383,235.96
**OCID:** `ocds-dgv273-seacev3-988512`
**Ganador:** VIPROSEG S.A.C.

---

## 3. Por Qué Fue Elegido

### Razón 1: El monto habla solo

S/ 195 millones en un solo contrato de seguridad privada para una entidad de salud pública. Cualquier ciudadano entiende la escala. No requiere explicación técnica.

### Razón 2: El documento revela participación real

El análisis identificó que al menos **5 empresas de seguridad privada** presentaron consultas durante el proceso. El ganador (VIPROSEG S.A.C.) fue una de ellas. Este es un hecho verificable en páginas numeradas del documento oficial, no una inferencia.

### Razón 3: La señal de página 17 es verificable

La pregunta #16 del proceso pregunta explícitamente si el contrato puede perfeccionarse de forma digital. ESSALUD respondió que NO: debe ser en persona en Lima. Esta respuesta está en página 17, es textual, es verificable, y es la base para una pregunta ciudadana legítima:

> *¿Por qué un contrato de S/ 195 millones de alcance nacional requiere que el ganador se presente físicamente en Lima para firmar el contrato, en una época en que la Mesa de Partes Virtual está disponible?*

Esta no es una acusación. Es una pregunta pública de política institucional.

### Razón 4: La pipeline demostró capacidad real

AgentePerry procesó **212 páginas reales** de un proceso de contratación pública y produjo:
- 445 chunks indexables
- 6 señales candidatas (con sus limitaciones)
- Una solicitud de transparencia lista para enviar
- Un informe reproducible con SHA256 verificable

**Eso es el producto.** La demo debe mostrar eso.

### Razón 5: La historia es contable en 60 segundos

> "Escaneamos un contrato de S/ 195 millones del Seguro Social de Salud. El sistema leyó 212 páginas automáticamente, detectó que una empresa de seguridad privada ganó este contrato después de haber participado en las rondas de preguntas, y encontró que el proceso requería presencia física en Lima para firmar. Generamos una solicitud de transparencia lista para enviar. Eso es AgentePerry."

---

## 4. Qué Decimos Sobre las Limitaciones

La demo debe ser honesta. Las limitaciones son parte de la historia:

1. **Los flags actuales tienen alta tasa de falso positivo.** Esto es esperado en un MVP con 6 reglas. El sistema es mejorable y el equipo ya sabe qué debe cambiar.

2. **El documento analizado es el Pliego de Absolución, no las Bases Integradas.** Las Bases Integradas (con los requisitos técnicos reales) están en RAR sin procesar. La pipeline tiene acceso a ellos en el futuro.

3. **La señal de pág. 17 no es prueba de irregularidad.** Es una pregunta de política pública válida. El sistema no acusa. Detecta y pregunta.

**Esta honestidad no debilita la demo. La fortalece.** Muestra que el equipo sabe lo que hace y no exagera sus hallazgos.

---

## 5. Por Qué ANA y MINAM Quedan Fuera (Por Ahora)

| Caso | Razón de exclusión |
|---|---|
| ANA (S/ 3M) | Todos los flags son falsos positivos con 5/5 de riesgo. Sin hallazgo editorial rescatable. Monto modesto para la demo. |
| MINAM (S/ 393K) | Mismo problema. Monto muy pequeño. Bases Administrativas no contienen señales accionables con las reglas actuales. |

**Futuro posible de estos casos:** Si se procesan las Bases Integradas (con requisitos técnicos reales) de ANA o si se mejoran las reglas de detección, estos casos pueden volver al análisis.

---

## 6. Flag a Usar en la Demo

**Flag válido para narrativa:**
- **Documento:** Pliego de Absolución — AS-SM-55-2023-ESSALUD/GCL-1
- **Página:** 17
- **Pregunta del postor:** "La documentación para el perfeccionamiento del contrato ¿Podrá ser presentado por mesa de partes virtual?"
- **Respuesta ESSALUD:** Debe presentarse en persona en "Jr. Domingo Cueto N° 120, Primer Piso, Jesús María - Lima"
- **Señal:** Contrato de alcance nacional con exigencia de presencialidad en Lima para su perfeccionamiento

**Framing legal-safe correcto:**
> *"El proceso requirió que el ganador de un contrato de S/ 195 millones con cobertura nacional se presentara físicamente en Lima para firmar. En una entidad que opera en todo el Perú, esta condición merece explicación pública sobre si fue evaluada su potencial impacto en la competencia."*

---

## 7. Checklist de Aceptación

| Criterio | Estado |
|---|---|
| ¿Hay un caso ganador claro? | ✅ ESSALUD — AS-SM-55-2023 |
| ¿La cita textual es fuerte? | ⚠️ Moderada — pág. 17 es verificable pero no espectacular |
| ¿La página está indicada? | ✅ Página 17, pregunta #16 |
| ¿La narrativa se entiende en 60 segundos? | ✅ Sí — S/ 195M, seguridad privada, ESSALUD nacional |
| ¿El lenguaje es legal-safe? | ✅ En todo el dossier |
| ¿Hay preguntas concretas para la autoridad? | ✅ 10 preguntas generadas automáticamente |
| ¿El caso sirve para pitch? | ✅ Con las caveats correctas, sí |
| ¿La demo puede mostrarse sin vergüenza? | ✅ Si se presenta honestamente |

---

## 8. Decisión Final

**Activity 6 sale POSITIVA con reservas.**

El sistema funciona. El caso ESSALUD tiene suficiente contexto y escala para una demo efectiva. Los flags actuales son débiles pero el hallazgo de página 17 y el contexto de participación de 5 empresas (incluido el ganador) son hechos verificados y periodísticamente relevantes.

**La demo debe narrar la herramienta, no el crimen.** La historia es: "Esto es lo que AgentePerry puede hacer hoy. Esto es lo que detectó. Esto es la solicitud de transparencia que generó automáticamente."

**Pasamos a Activity 7 — Demo Narrative Pack**, usando el caso ESSALUD con las caveats documentadas.

**Condición para Activity 7:** El demo_case.md debe comunicar honestamente que:
1. Se analizó el Pliego de Absolución, no el TDR técnico completo
2. Los flags son preliminares y el sistema es mejorable
3. La señal de pág. 17 merece revisión, no es prueba de nada
