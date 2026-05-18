# Slide Outline — 6 Slides

> **Nota:** Este outline es para preparar slides de presentación. Cada slide incluye contenido sugerido, visual推荐 y notas para el presentador. No incluye diseño visual todavía (eso es para Activity 8).

---

## Slide 1 — El Problema

**Título:** Miles de documentos. Nadie que lea.

**Contenido:**
- El Estado publica miles de procesos de contratación cada año.
- Documentos públicos por ley. Pero en la práctica: inaccesibles.
- 200 páginas de pliegos, bases, consultas, resoluciones.
- Un periodista no puede leerlos todos. Un ciudadano, ninguno.
- Las señales de riesgo están en los detalles.
- Sin herramientas, la revisión es selectiva y no escala.

**Visual sugerida:** Pilas de documentos físicos vs. una pantalla conPDFs abiertos — contraste de overwhelm informativo.

**Quote:** "La fiscalización pública está enterrada en PDFs de 200 páginas."

**Notas presentador:**
- No entrar en tecnicismos. Hablar desde la frustración del periodista o ciudadano.
- Ejemplo concreto: "¿Cuántos de ustedes han intentado leer un contrato de ESSALUD completo?"

---

## Slide 2 — La Solución

**Título:** AgentePerry: leer por la ciudadanía

**Contenido:**
- Herramienta de código abierto que lee expedientes públicos de contratación.
- Convierte PDFs de cientos de páginas en evidencia estructurada y preguntas ciudadanas verificables.
- No accus. No audits. Pregunta.
- Pipeline: descarga → evalúa texto → procesa → detecta señales → genera dossier.
- Open source. Reproducible. Auditabable.

**Visual sugerida:** Diagrama simple del pipeline (minimal, no técnico):
`JSONL → Detector → Pipeline → Dossier`

**Quote:** "AgentePerry no accus. Lee, conecta evidencia y pregunta."

**Notas presentador:**
- Explicar el nombre: "Perry" como el detective que hace preguntas, no que accusations.
- Enfatizar: es una herramienta para ciudadanos y periodistas, no un sustituto de auditorías.

---

## Slide 3 — El Caso Real

**Título:** ESSALUD: S/ 195 millones, 3 años, una pregunta

**Contenido:**
- Entidad: Seguro Social de Salud
- Proceso: AS-SM-55-2023-ESSALUD/GCL-1
- Objeto: Seguridad y vigilancia en instalaciones de ESSALUD a nivel nacional
- Monto: S/ 195,383,235.96
- Duración: 1,095 días (3 años)
- Ganador: VIPROSEG S.A.C.
- Documento: 212 páginas procesadas, 100% texto digital

**La pregunta de la página 17:**
- Empresa preguntó: "¿Documentación por mesa de partes virtual?"
- ESSALUD respondió: "No. Jr. Domingo Cueto 120, Lima."
- Repetido en páginas 28 y 121 → 3 señales MEDIUM sobre el mismo tema.

**Métricas actualizadas:**
- 9 flags detectados (3 MEDIUM, 6 LOW)
- Score: 105/100 → CRITICO
- 3 señales MEDIUM todas sobre PHYSICAL_PRESENTATION_REQUIRED

**Visual sugerida:** Screenshot del dossier (páginas 1 y 17). Tabla de flags con 3 MEDIUM en página 17. Quote highlighted con respuesta de ESSALUD sobre Jr. Domingo Cueto.

**Notas presentador:**
- Leer la cita de la página 17 en voz alta.
- Explicar: el documento es el pliego procesal. Las 3 señales MEDIUM son todas sobre el requisito de presentación física — el hallazgo es cohérente.
- Enfatizar: el sistema ahora tiene reglas específicas para pliegos procesales (TDR-R007).

---

## Slide 4 — Cómo Funciona

**Título:** El pipeline técnico

**Contenido:**
- Paso 1: OCDS JSONL → datos abiertos del SEACE
- Paso 2: SEACE Change Detector → detecta contratos nuevos/modificados por sector
- Paso 3: PDF Quality Gate → evalúa si el documento tiene texto o es escaneado
- Paso 4: Page extraction → una página por vez
- Paso 5: Chunks + Embeddings → fragmentos procesables
- Paso 6: Flag detection → 12 reglas con evidencia citation
- Paso 7: Dossier → Markdown con cita, página, fuente

**Comandos reales:**
```bash
agenteperry tdr download --ocid ocds-dgv273-seacev3-988512
agenteperry tdr audit-pdfs --input data/results/<ocid>/
agenteperry tdr analyze --ocid ocds-dgv273-seacev3-988512 --sector salud
```

**Visual sugerida:** Diagrama de flujo del pipeline (más detallado que el slide 2). Screenshot del CLI en acción.

**Notas presentador:**
- Mostrar el CLI corriendo en vivo si hay tiempo.
- Enfatizar el PDF Quality Gate: "No procesamos escaneados sin texto — eso evita falsos positivos por OCR deficiente."

---

## Slide 5 — Impacto Ciudadano

**Título:** De documentos a preguntas públicas

**Contenido:**
- Antes: periodista tarda días en leer un contrato.
- Después: recibe un dossier con evidencia y citas en minutos.
- AgentePerry no reemplazpa al periodista. Lo acelera.
- Periodista hace preguntas verificables, no conclusiones apresuradas.
- Comunidad open source puede auditar, mejorar y extender.
- Escalable: hoy salud, mañana educación e infraestructura.

**Casos de uso:**
- Periodista de investigación → acelera revisión de contratos.
- Ciudadano informado → puede hacer preguntas sin ser experto.
- ONG de transparencia → monitoreo sistemático a escala.
- Academia → investigación sobre patrones de contratación pública.

**Quote:** "No reemplazamos a los periodistas. Les damos tiempo para hacer más preguntas."

**Notas presentador:**
- Hablar desde el valor, no desde la tecnología.
- "¿Cuántos contratos podría revisar un periodista en un día? ¿Y con AgentePerry?"

---

## Slide 6 — Roadmap

**Título:** Siguientes pasos

**Contenido:**

**Ya funciona (MVP):**
- Pipeline completo: detección → descarga → parse → flags → dossier
- CLI funcional
- Dossiers en Markdown con evidencia citation
- 126 tests pasando, 0 errors

**En desarrollo:**
- OCR para PDFs escaneados
- Dashboard minimal para ciudadanos y periodistas
- Soporte sectores: educación, infraestructura, ambiente
- API REST para consumo por terceros

**Exploración futura:**
- Integración con datos SUNAT (RUC, representantes legales)
- Entrega de evidencia a Contraloria General de la República
- Alertas automáticas para contratos prioritarios
- Búsqueda semántica cruzable entre contratos similares

**Call to action:**
- Código: github.com/.../agenteperry
- Documentación: docs/
- Contribuir: Issues abiertos, PRs bienvenidos

**Quote cierre:**
> "La fiscalización pública está enterrada en PDFs de 200 páginas. AgentePerry los lee por la ciudadanía."

---

## Notas de producción para slides

**Reglas de diseño:**
- Legal-safe en todo momento.
- No usar "corrupción", "fraude", "delito", "robo", "culpable".
- Usar: "señal de riesgo", "merece revisión", "pregunta pública", "evidencia documental".
- Ser honesto sobre falsos positivos.
- Enfatizar: el sistema genera preguntas, no sentencias.

**Tono visual:**
- Profesional pero accesible.
- No debe verse como herramienta de vigilancia.
- Debe verse como herramienta de empoderamiento ciudadano.
- Paleta: azul oscuro + blanco + gris — seriousness pero no aggression.

**Tiempo por slide:**
- Slide 1 (Problema): 30 segundos
- Slide 2 (Solución): 30 segundos
- Slide 3 (Caso real): 60 segundos ⭐ (el caso ESSALUD)
- Slide 4 (Cómo funciona): 45 segundos
- Slide 5 (Impacto): 30 segundos
- Slide 6 (Roadmap): 30 segundos

**Total estimado: 3 minutos 45 segundos** (incluyendo transiciones)

---

*Fuentes: Portal SEACE, OCDS, proceso AS-SM-55-2023-ESSALUD/GCL-1.*