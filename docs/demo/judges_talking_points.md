# Judges Talking Points — AgentePerry TDR Scanner

> **Nota:** Estos bullets están diseñados para que el presentador pueda responder preguntas de jueces de hackathon de forma estructurada, concisa y sin tecnicismos excesivos. Cada bullet incluye el mensaje clave y, cuando aplica, el por qué importa.

---

## 1. Impacto social

**Mensaje clave:** AgentePerry democratiza el acceso a la información pública de contratación.

- En el Perú, miles de contratos públicos se publican cada año. Casi nadie los lee.
- Periodistas, sociedad civil y ciudadanos no tienen tiempo ni herramientas para revisar contratos extensos.
- AgentePerry les da evidencia verificable en minutos, no en días.
- El caso ESSALUD demuestra que con evidencia pública se pueden formular preguntas ciudadanas verificables.

**Respira:** "No acusamos. Preguntamos."

---

## 2. Innovación técnica

**Mensaje clave:** Combinamos estándares abiertos, NLP y reglas de detección en un pipeline reproducible y auditabable.

- OCDS (Open Contracting Data Standard) — estándar internacional de datos abiertos.
- PyMuPDF para parsing de PDFs con evaluación de capa de texto.
- Embeddings vectoriales para búsqueda semántica.
- 12 reglas de detección de señales de riesgo, cada una con evidencia citation.
- Pipeline completo en Python, CLI funcional, reproducible.

**Respira:** "El código está en GitHub. Pueden auditarlo."

---

## 3. Uso de datos públicos

**Mensaje clave:** Solo usamos fuentes públicas y documentos oficiales.

- SEACE (Sistema Electrónico de Contrataciones del Estado) — portal público.
- OCDS JSONL — datos abiertos del SEACE.
- Los PDFs son documentos oficiales publicados por entidades públicas.
- No usamos datos sensibles ni personales.
- No hacemos scraping agresivo. Usamos datos ya públicos y estructurados.

**Respira:** "Todo lo que mostramos está en portales públicos. Pueden verificarlo."

---

## 4. Legal-safe by design

**Mensaje clave:** El sistema está diseñado para no acusar y para ser honesto sobre sus limitaciones.

- No usamos las palabras "corrupción", "fraude", "delito", "robo", "culpable".
- Usamos: "señal de riesgo", "merece revisión", "pregunta pública", "evidencia documental".
- El sistema genera preguntas, no sentencias.
- El caso ESSALUD incluye nota de limitaciones: 11 de 12 flags fueron falsos positivos.
- Nunca decimos que el caso prueba algo. Decimos que genera una pregunta.

**Respira:** "Legal-safe no es marketing. Es arquitectura."

---

## 5. Escalabilidad

**Mensaje clave:** El pipeline escala de 1 contrato a miles sin intervención humana.

- Cambio Detector: detecta contratos nuevos/modificados automáticamente.
- Sector Filter: filtra por salud, ambiente u otros.
- PDF Gate: evita analizar escaneados sin texto.
- El mismo pipeline sirve para ESSALUD, para un hospital regional o para un contrato de infraestructura.
- Próximo paso: expandir a sectores educación e infraestructura.

**Respira:** "Hoy procesa 1 contrato. Puede procesar 10,000."

---

## 6. Open source

**Mensaje clave:** El proyecto es de código abierto y está diseñado para que otros lo usen y lo mejoren.

- Repositorio público en GitHub.
- CLI documentado.
- Migraciones de base de datos incluidas.
- Tests con 100% pass rate.
- Documentación técnica completa.
- Diseñado para ser extensible: más reglas, más sectores, más fuentes.

**Respira:** "La licencia es abierta. Pueden construir sobre esto."

---

## 7. Utilidad para periodistas y ciudadanos

**Mensaje clave:** AgentePerry no reemplaza al periodista. Lo acelera.

- Un periodista que quiere verificar un contrato hoy: pide documentos, los lee, busca patrones.
- Con AgentePerry: recibe un dossier con evidencia y citas en minutos.
- El periodista sigue haciendo el trabajo de verificación y contextualización.
- El sistema le da tiempo para hacer más contratos, más preguntas, más investigación.
- Además: el ciudadano común puede usar el CLI si quiere.

**Respira:** "No reemplazamos a los periodistas. Les damos tiempo para hacer más preguntas."

---

## Frase resumen para judges

> "AgentePerry convierte expedientes públicos imposibles de leer a mano en preguntas ciudadanas verificables. No accus: lee, conecta evidencia y muestra qué merece revisión."

---

*Fuentes: Portal SEACE, OCDS, proceso AS-SM-55-2023-ESSALUD/GCL-1.*
*El sistema no constituye una denuncia ni una auditoría.*