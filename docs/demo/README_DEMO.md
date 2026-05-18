# Demo Narrative Pack — AgentePerry TDR Scanner

**Caso demo principal:** ESSALUD — AS-SM-55-2023-ESSALUD/GCL-1
**OCID:** `ocds-dgv273-seacev3-988512`
**Monto:** S/ 195,383,235.96
**Fecha de documento procesado:** Activity 6

---

## 1. ¿Qué es AgentePerry?

AgentePerry es un sistema de código abierto que lee expedientes de contratación pública publicados en formato PDF por el Estado peruano, los convierte en evidencia estructurada y genera preguntas ciudadanas verificables.

No accusing: genera preguntas. No sustituye a la Contraloría ni a los jueces.

## 2. ¿Qué problema resuelve?

El Estado publica miles de contratos, pliegos y resoluciones en portales como SEACE y OSCE. En la práctica:

- Un periodista o ciudadano no puede leer 200 páginas de un solo documento.
- Los contratos de mayor monto suelen tener documentos complejos de dozens de páginas.
- Las señales de riesgo más relevantes están en notas, respuestas a consultas y cláusulas.
- Sin herramientas, la revisión manual es lenta, incompleta y no escala.

AgentePerry automatiza la lectura de esos documentos a escala.

## 3. ¿Qué caso analizamos?

**Entidad:** Seguro Social de Salud (ESSALUD)
**Proceso:** AS-SM-55-2023-ESSALUD/GCL-1
**Objeto:** Servicio de Seguridad y Vigilancia en las Instalaciones de ESSALUD a Nivel Nacional
**Monto:** S/ 195,383,235.96 (S/ 195 millones)
**Duración del servicio:** 1,095 días calendario (3 años)
**Ganador:** VIPROSEG S.A.C. — RUC 20605681281
**Documento analizado:** Pliego de Absolución de Consultas y Observaciones
**Páginas procesadas:** 212
**Cobertura de texto:** 100%
**Flags detectados:** 9 (3 MEDIUM, 6 LOW) — Score: 105/100 → CRITICO

## 4. ¿Qué encontró?

El sistema detectó **9 señales** en el pliego procesal:

**3 señales MEDIUM (TDR-R007 `PHYSICAL_PRESENTATION_REQUIRED`):**

- **Página 17:** Una empresa preguntó si podía presentar la documentación por mesa de partes virtual. ESSALUD respondió que el ganador debía presentar la documentación requerida **en Jr. Domingo Cueto N° 120, Primer Piso, Jesús María — Lima**, de forma presencial.
- **Página 28:** Otro postor hizo la misma consulta sobre mesa de partes virtual para la suscripción del contrato. ESSALUD dio la misma respuesta.
- **Página 121:** Consulta adicional sobre la oportunidad de presentación presencial del manual de actividades.

**6 señales LOW (TDR-R002/TDR-R005):** Menciones a formato físico y documentos de baja trazabilidad digital.

La señal más relevante es la **página 17**: en un contrato de S/ 195 millones para seguridad nacional durante 3 años, el requisito de presentación presencial en Lima para el perfeccionamiento del contrato puede haber generado barreras para empresas de regiones.

Además, al menos 5 empresas de seguridad privada participaron en las consultas del proceso, incluido el ganador VIPROSEG.

## 5. ¿Qué NO afirma AgentePerry?

- **No afirma** que ESSALUD actuó de manera irregular.
- **No afirma** que el ganador se benefició ilícitamente.
- **No utiliza** la palabra "corrupción" ni "delito" ni "fraude".
- **No sustituye** una auditoría de la Contraloría General de la República.
- **No analiza** el TDR técnico completo (el documento procesado es el pliego procesal, no las especificaciones técnicas del servicio).

Lo que sí hace es **extraer evidencia verificable y formular una pregunta pública responsable**.

## 6. ¿Por qué importa este caso?

El contrato representa S/ 195 millones de fondos públicos. El requisito de presentación física en Lima durante el perfeccionamiento del contrato puede haber generado barreras de entrada para empresas de regiones. Eso merece una pregunta pública, no una conclusión.

## 7. ¿Cómo se ejecuta la demo?

### Paso 1 — Descargar el contrato
```bash
agenteperry tdr download \
  --ocid ocds-dgv273-seacev3-988512 \
  --out-dir data/results/
```

### Paso 2 — Auditar PDFs del contrato
```bash
agenteperry tdr audit-pdfs \
  --input data/results/ocds-dgv273-seacev3-988512/ \
  --sector salud
```

Resultado esperado:
- 12 PDFs detectados
- 11 con capa de texto → se procesan
- 1 escaneado → se marca `needs_ocr`

### Paso 3 — Analizar el documento
```bash
agenteperry tdr analyze \
  --ocid ocds-dgv273-seacev3-988512 \
  --sector salud \
  --out-dir data/results/
```

Resultado esperado:
- 212 páginas procesadas
- 445 chunks con embeddings
- 1 flag de evidencia
- Dossier generado en `data/results/ocds-dgv273-seacev3-988512/dossier.md`

### Dossier generado
El dossier contiene:
- Metadata del contrato
- Page-by-page flags with evidence
- Resumen del riesgo
- Quote extraída de la página 17
- Nota sobre limitaciones del análisis

## 8. Arquitectura del pipeline

```
JSONL (OCDS contracts)
   │
   ▼
 SEACE Change Detector
   │  Detecta contratos nuevos/modificados
   │  Sector filter: salud / ambiente / otros
   ▼
 CDCPipeline
   │
   ├── select_tdr_documents()   ← elige mejores PDFs
   ├── download_document()      ← descarga PDF
   ├── inspect_pdf_text_layer() ← evalúa si tiene texto o es escaneado
   │                              needs_ocr → se.skip
   │                              available → se procesa
   ├── extract_pdf_pages()     ← una página por vez
   ├── chunk_pages()            ← divide en chunks
   ├── compute_embeddings()     ← embedding por chunk
   ├── detect_flags_in_pages()  ← reglas sobre texto
   │                              12 rules: monto atipico,
   │                              единственный proveedor,
   │                              modificatorias, etc.
   └── generate_dossier()        ← markdown con evidencia
                                    + cita textual
                                    + página + fuente
```

## 9. Limitaciones conocidas (honestidad)

- **11 de 12 flags fueron falsos positivos** en este documento porque el documento analizado es un pliego procesal, no el TDR técnico completo. Las reglas de detección están calibradas para contratos con especificaciones técnicas.
- El sistema **no usa OCR** por ahora. Los PDFs escaneados sin capa de texto se marcan `needs_ocr` y se excluyen del análisis. En una próxima iteración se可以考虑ía OCR.
- AgentePerry **no accused**. Genera preguntas ciudadanas verificables.

## 10. Ready para siguientes pasos

El Narrative Pack está completo. El siguiente paso natural es:

**Activity 8 — Demo Visual Mínima**
- Landing estática con el caso ESSALUD
- Flujo técnico visual
- Botón "Ver evidencia"
- Dossier renderizado

**No listo para:**
- Slides de presentación (primero cerrar Activity 8)
- Demo UI completa (requiere Activity 8)
- Integración con SUNAT, Contraloría, JNE (fuera de scope MVP)