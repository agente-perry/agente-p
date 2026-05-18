# SPEC-NNNN: <Título corto>

| Campo | Valor |
|-------|-------|
| **ID** | SPEC-NNNN |
| **Estado** | proposed \| approved \| in_progress \| completed \| archived |
| **Owner** | @github-handle |
| **Reviewers** | @reviewer1 @reviewer2 |
| **Sprint / Fase** | F1 \| F2 \| F3 \| F4 \| F5 \| post-MVP |
| **Creado** | YYYY-MM-DD |
| **Última actualización** | YYYY-MM-DD |
| **Issue relacionado** | #N (link al issue de propuesta) |
| **PR de implementación** | #N (cuando exista) |
| **Depende de** | SPEC-NNNN, SPEC-MMMM |
| **Bloquea** | SPEC-XXXX |

---

## 1. Problema

¿Qué problema concreto resuelve este spec? ¿Quién lo tiene? Sé específico — escenarios reales, no abstractos.

Mal: "Necesitamos mejorar la detección de riesgo."
Bien: "Hoy un contrato con 3 señales de riesgo no llega a `risk_cases`. El periodista debe descubrirlo manualmente. Queremos que el sistema lo promocione automáticamente a caso draft."

---

## 2. Objetivo

Una frase. Qué cambia después de implementar este spec.

> Después de este spec, X podrá Y.

---

## 3. Contexto y restricciones

- Qué partes del sistema toca
- Qué fuentes de datos
- Qué decisiones previas heredamos
- Qué cosas NO podemos cambiar (legal, performance, scope)

---

## 4. Criterios de aceptación

Checklist verificable. Cada ítem debe poder probarse con un comando o screenshot.

- [ ] Criterio 1 — verificable cómo
- [ ] Criterio 2 — verificable cómo
- [ ] Criterio 3 — verificable cómo

---

## 5. Out of scope

Lista de cosas que parecen incluidas pero NO lo están. Evitar scope creep.

- ❌ Cosa A — razón
- ❌ Cosa B — razón

---

## 6. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Ej. SUNAT cambia encoding | media | alta | Detectar via try/except en parser; fallback a chardet |

---

## 7. Métricas de éxito

Cómo sabremos que funcionó después de mergear.

- Métrica 1: valor antes → valor objetivo
- Métrica 2: ...

---

## 8. Decisiones rechazadas

Para evitar revisitar en el futuro.

- ❌ Opción A — rechazada porque...
- ❌ Opción B — rechazada porque...

---

## 9. Anexos

- Links a investigación previa (`hackl@latam/...`)
- Diagramas
- Referencias externas (papers, docs oficiales)
