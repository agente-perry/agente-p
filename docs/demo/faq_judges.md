# FAQ — Preguntas difíciles de jueces

> **Propósito:** Anticipar las preguntas más difíciles que pueden hacer los jueces y preparar respuestas sólidas, honestas y legal-safe. Cada respuesta incluye el mensaje clave y, cuando aplica, un "qué decir si presionan".

---

## 1. ¿Están acusando a ESSALUD?

**Respuesta corta:** No. Absolutamente no.

**Respuesta completa:**
No. AgentePerry no accus. No sentencie. No audits.

Lo que hacemos es extraer evidencia de documentos públicos y convertirla en preguntas ciudadanas verificables. El caso ESSALUD no demuestra una irregularidad. Demuestra que el sistema puede leer documentos extensos y generar preguntas públicas con evidencia citation.

La pregunta del caso ESSALUD es: ¿el requisito presencial de presentación en Lima para el perfeccionamiento de un contrato de S/ 195 millones generó barreras de entrada para empresas de regiones? Es una pregunta legítima, no una acusación.

**Qué decir si presionan:** "Si ESSALUD quisiera responder a esa pregunta, los documentos están disponibles en el SEACE. Ese es exactamente el punto: dar herramientas para que la ciudadanía pueda preguntar."

---

## 2. ¿Cómo evitan los falsos positivos?

**Respuesta corta:** Los aceptamos, los documentamos y los usamos para mejorar. En el caso ESSALUD, las 3 señales MEDIUM son reales y directas.

**Respuesta completa:**
El caso ESSALUD generó 9 señales: 6 LOW y 3 MEDIUM. Las 3 MEDIUM son todas sobre el mismo tema: el requisito de presentación física en Jr. Domingo Cueto para el perfeccionamiento del contrato. Eso no es un falso positivo — es el hallazgo central del caso.

Las 6 LOW son menciones genéricas a formato físico y entregables de baja trazabilidad, que son secundarias pero válidas.

El documento procesado es un pliego procesal (Absolución de Consultas), no un TDR técnico completo. Las reglas antiguas no detectaban bien este tipo de documento. Por eso añadimos la regla TDR-R007 (`PHYSICAL_PRESENTATION_REQUIRED`) específicamente para detectar requisitos de presentación física en pliegos procesales.

**Qué decir si presionan:** "El sistema ahora detecta señales reales en pliegos procesales. Las 3 señales MEDIUM del caso ESSALUD son todas sobre el mismo hallazgo: el requisito presencial. Eso es evidencia verificable con cita textual y número de página."

---

## 3. ¿Qué pasa con los PDFs escaneados?

**Respuesta corta:** Los detectamos y los excluimos. No procesamos escaneados sin texto.

**Respuesta completa:**
El sistema inspecciona cada PDF antes de procesarlo. Evalúa si tiene capa de texto o si es un escaneo puro. Si es escaneado, lo marca como `needs_ocr` y lo excluye del análisis.

¿Por qué? Porque el texto OCRizado sin revisión humana contiene errores que pueden generar falsos positivos graves. Preferimos decir "no podemos leer esto todavía" a entregar evidencia incorrecta.

**Qué decir si presionan:** "Hoy excluimos escaneados. En el roadmap está OCR con revisión posterior. Por ahora, la calidad de la evidencia es más importante que la cantidad de documentos procesados."

---

## 4. ¿Por qué no usaron OCR?

**Respuesta corta:** Porque sin revisión humana, el OCR introduce errores que pueden ser peores que no leer el documento.

**Respuesta completa:**
PyMuPDF (el parser de PDFs que usamos) puede hacer OCR básico, pero no está habilitado por defecto. El OCR automático sin revisión humana puede alterar números, nombres y cifras — exactamente los datos que más importan en un contrato público.

No queríamos entregar evidencia con números potencialmente incorrectos. Entonces elegimos el camino de calidad: procesar solo documentos con capa de texto verificable.

**Qué decir si presionan:** "El día que habilitemos OCR, va a tener revisión humana posterior o validación cruzada. No vamos a enviar un número errado en un informe de S/ 195 millones sin que alguien lo revise."

---

## 5. ¿Cómo escala a otros sectores?

**Respuesta corta:** La misma arquitectura sirve para educación, infraestructura, ambiente. Solo requiere nuevos datos OCDS y recalibrar reglas.

**Respuesta completa:**
El pipeline de detección está diseñado para aceptar cualquier JSONL de contratos OCDS. Hoy funciona con datos del SEACE filtrados por sector (salud). El mismo código sirve para educación, infraestructura y ambiente — solo hay que conseguir los JSONL correspondientes.

Las reglas de flags son específicas por tipo de documento. Un contrato de obras públicas tiene señales diferentes a un contrato de servicios de salud. Pero el framework es el mismo.

**Qué decir si presionan:** "La expansión a otros sectores es principalmente un problema de datos y calibración de reglas, no de arquitectura. La infraestructura ya está lista."

---

## 6. ¿Qué fuentes usan?

**Respuesta completa:**
Solo fuentes públicas:

- **SEACE** (Sistema Electrónico de Contrataciones del Estado) — portal oficial donde las entidades publican procesos de contratación.
- **OCDS JSONL** — datos abiertos del SEACE en formato estándar internacional.
- **Portales de entidades** — cada entidad pública publica sus documentos en su propio portal o en SEACE.

No hacemos scraping de sitios que no quieran ser raspados. Usamos datos que ya son públicos y abiertos.

**Qué decir si presionan:** "Todo lo que muestra AgentePerry está en portales públicos. El periodista o ciudadano que quiera verificarlo puede ir al SEACE y leer el mismo documento."

---

## 7. ¿Qué harían con SUNAT y la Contraloría?

**Respuesta completa:**
SUNAT y la Contraloria son instituciones con potestades legales de auditoría que AgentePerry no tiene ni quiere tener.

Lo que podemos hacer es entregarles evidencia estructurada. Si AgentePerry detecta una señal en un contrato, la fórmula como pregunta verificable con cita textual, página y fuente. Eso es entrada útil para un auditor.

Pero el sistema no es un sustituto de la auditoría. Es un acelerador de revisión documental para ciudadanos y periodistas que no tienen acceso a auditorías formales.

**Qué decir si presionan:** "No pretendemos ser la Contraloría. Pretendemos darle a un periodista o ciudadano herramientas para hacer las preguntas correctas antes de que una auditoría sea necesaria."

---

## 8. ¿Cómo protegen los datos personales?

**Respuesta completa:**
AgentePerry procesa documentos públicos de contratación. Esos documentos ya son públicos por ley. No accedemos a sistemas internos ni a bases de datos personales.

El sistema extrae evidencia de documentos oficiales: montos, nombres de empresas ganadoras, requisitos de presentación, respuestas a consultas. Ninguno de esos datos es personal sensibles en el sentido de la Ley 29733 (protección de datos personales).

Los embeddings y chunks se almacenan localmente o en la base de datos del proyecto. No se comparten con terceros.

**Qué decir si presionan:** "Procesamos documentos públicos. Si un documento contiene datos personales sensibles, eso es un problema del documento público, no de nuestra herramienta."

---

## 9. ¿Qué hace diferente a AgentePerry de otras herramientas?

**Respuesta completa:**
Hay muchas herramientas de transparencia contractual en el mundo. Lo que hace diferente a AgentePerry es:

1. **Legal-safe by design:** No accusamos. No usamos palabras como "corrupción" o "fraude". Generamos preguntas verificables, no sentencias.

2. **Evidencia citation:** Cada flag incluye cita textual, página y fuente. El usuario puede verificar en el documento original.

3. **PDF quality gate:** No procesamos escaneados sin texto. Evitamos falsos positivos por OCR deficiente.

4. **Open source + extensible:** La licencia es abierta. Otros pueden construir sobre esto.

5. **Pensado para ciudadanos y periodistas:** No requiere acceso a bases de datos internas ni a auditorías formales. Funciona con documentos públicos.

**Qué decir si presionan:** "La combinación de evidence citation, legal-safe y código abierto es única. Otras herramientas pueden detectar anomalías, pero pocas generan dossiers verificables con citations."

---

## 10. ¿Qué harían con más tiempo?

**Respuesta completa:**
MVP ya funciona. Con más tiempo, en orden de prioridad:

1. **OCR para PDFs escaneados** — ampliar la cobertura de documentos procesables.
2. **Dashboard minimal** — para que periodistas y ciudadanos puedan buscar contratos sin CLI.
3. **Más sectores** — educación, infraestructura, ambiente.
4. **Embeddings cruzados** — comparar contratos similares para detectar patrones de precios.
5. **API REST** — para que terceros integren AgentePerry en sus herramientas.
6. **Integración con SUNAT/Contraloría** — entrega de evidencia estructurada a instituciones formales (requiere convenio).
7. **Notificaciones automáticas** — alertas cuando un contrato prioritario se publique o modifique.

**Qué decir si presionan:** "El MVP ya hace lo esencial: lee documentos públicos, extrae evidencia y formula preguntas. El resto es expansión."

---

## Frase de cierre para preguntas difíciles

> "AgentePerry no tiene la última palabra. Tiene la primera: la de hacer la pregunta."

---

*Fuentes: Portal SEACE, OCDS, proceso AS-SM-55-2023-ESSALUD/GCL-1, Ley 29733.*