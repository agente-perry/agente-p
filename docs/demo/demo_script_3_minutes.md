# Demo Script — 3 minutos

> **Nota:** Este script expande el de 90 segundos con más contexto técnico y narrativo. Diseñado para 3 minutos de presentación oral. Puede adaptarse según el tiempo disponible.

---

## El problema: miles de documentos, nadie que lea

Cada año, el Estado peruano publica miles de procesos de contratación en portales como SEACE y OSCE. Son documentos públicos por ley. Pero hay un problema práctico:

- Un contrato grande puede tener 20, 50, 200 páginas de pliegos, bases, consultas y resoluciones.
- Un periodista tiene tiempo de leer unos pocos. Un ciudadano, ninguno.
- Las señales más relevantes — una consulta respondido, una cláusula modificatoria, un requisito extraño — están en los detalles.
- Sin herramientas, la revisión es selectiva, lenta y no escala.

No es un problema de voluntad. Es un problema de escala.

---

## La solución: AgentePerry

AgentePerry es una herramienta de código abierto que lee expedientes públicos de contratación, extrae evidencia y la convierte en preguntas ciudadanas verificables.

No accus. No audits. No sentencie.

Lo que hace es esto:

1. Recibe un listado de contratos públicos en formato OCDS (estándar internacional de datos abiertos).
2. Detecta contratos nuevos o modificados.
3. Descarga los documentos PDF asociados.
4. Evalúa si el PDF tiene texto digital o si está escaneado (y por tanto requiere OCR).
5. Si tiene texto: lo procesa página por página, lo divide en fragmentos (chunks), genera embeddings.
6. Aplica reglas de detección de señales de riesgo: montos atípicos, único postor, modificaciones, requisitos extraños.
7. Genera un dossier: evidencia extraída, cita textual, página, fuente.

Todo esto corre desde la línea de comandos. Sin interfaz bonita todavía. Pero funciona.

---

## La arquitectura

```
JSONL (datos OCDS públicos del SEACE)
    │
    ▼
 SEACE Change Detector
    │  Filtra por sector: salud, ambiente, otros
    │  Compara hashes para detectar cambios
    ▼
 CDCPipeline
    │
    ├── Descarga PDFs del contrato
    ├── Evalúa calidad de texto (OCR gate)
    │      Si escaneado → se.skip
    │      Si texto disponible → se procesa
    │
    ├── Extrae páginas
    ├── Genera chunks + embeddings
    ├── Detecta flags de riesgo (12 reglas)
    │
    └── Genera dossier en Markdown
             │
             ▼
        Pregunta ciudadana verificable
```

---

## El caso real: ESSALUD

Probamos el sistema con un caso concreto.

**Entidad:** Seguro Social de Salud — ESSALUD
**Proceso:** AS-SM-55-2023-ESSALUD/GCL-1
**Objeto:** Servicio de Seguridad y Vigilancia en Instalaciones de ESSALUD a Nivel Nacional
**Monto:** S/ 195,383,235.96 — sobre los S/ 195 millones
**Ganador:** VIPROSEG S.A.C.
**Duración:** 1,095 días calendario, casi 3 años

El documento analizado es el Pliego de Absolución de Consultas y Observaciones. Tiene 212 páginas. AgentePerry lo leyó completo. Cobertura de texto: 100%. Sin OCR.

**Qué encontró en la página 17:**

Una empresa preguntó si podía presentar la documentación para el perfeccionamiento del contrato por mesa de partes virtual.

ESSALUD respondió: no. El ganador debía presentar la documentación requerida en Jr. Domingo Cueto N° 120, Primer Piso, Jesús María — Lima.

**Qué significa eso:**

Es una cláusula de presentación física. En un contrato de S/ 195 millones para seguridad nacional, eso genera una pregunta legítima: ¿qué empresas de regiones participaron? ¿El requisito presencial limitó la competencia?

**Qué no significa:**

Esto no es una denuncia. No prueba corrupción. No sustituye una auditoría. Pero genera una pregunta verificable con evidencia documental pública.

---

## El resultado

El sistema generó un dossier con:

- Metadata del contrato
- 445 chunks procesados
- 1 flag de evidencia real (y 11 falsos positivos — el documento era procesal, no técnico)
- Quote extraída de la página 17
- Nota de transparencia sobre las limitaciones del análisis

Lo importante no es que encontró una señal. Lo importante es que **puede hacerlo a escala** — sobre miles de contratos, sin intervención humana.

---

## Impacto ciudadano

Hoy, si un periodista o ciudadano quiere cuestionar un contrato público:

- Necesita pedir los documentos físicos o digitales.
- Necesita leerlos completos.
- Necesita comparar con otros contratos similares.
- Necesita encontrar el contexto.

AgentePerry hace eso automaticamente. Devuelve evidencia y preguntas, no sentencias.

---

## Limitaciones (ser honestos)

- 11 de 12 flags fueron falsos positivos. Las reglas están calibradas para contratos técnicos. El documento procesado era procesal. El sistema necesita mejora, y lo sabemos.
- No usa OCR todavía. Los PDFs escaneados se excluyen.
- No sustituye a la Contraloría ni a los jueces.
- No accus. Formula preguntas.

---

## Próximos pasos

**Ya funciona:**
- Pipeline de detección, descarga, parsing, flags, dossier.
- CLI completo.
- Dossiers en Markdown con evidencia citation.

**En desarrollo:**
- OCR para PDFs escaneados.
- Soporte para más sectores: ambiente, educación, infraestructura.
- API REST para consumo por terceros.
- Dashboard minimal paraActivity 8.

**Fuera del MVP actual:**
- Integración con SUNAT.
- Integración con Contraloria.
- Integración con JNE.
- Detección automática de corrupción.

---

## Frase de cierre

> "La fiscalización pública está enterrada en PDFs de 200 páginas. AgentePerry los lee por la ciudadanía."

> "AgentePerry no accus. Lee, conecta evidencia y pregunta."

---

*Fuentes: Portal SEACE (seace.gob.pe), estándar OCDS, proceso AS-SM-55-2023-ESSALUD/GCL-1.*
*El sistema no constituye una denuncia ni una auditoría. Toda evidencia debe verificarse con las fuentes originales.*