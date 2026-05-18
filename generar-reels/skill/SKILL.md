---
name: radiografia
description: Genera el video diario de Radiografia del Gasto Publico leyendo el insight JSON mas reciente, seleccionando la plantilla HTML segun el patron detectado, llenando los placeholders Jinja2 con datos reales, y validando el resultado antes de renderizar con HyperFrames
---

# Radiografia del Gasto Publico

Usa este skill cuando el usuario pida procesar el insight diario de la serie "Radiografia del Gasto Publico" de Agente P.

**REGLAS OBLIGATORIAS**: leer `STYLE_GUIDE.md` antes de cada render. Las 7 reglas de ese documento son no negociables y el validador las verifica automáticamente.

## Flujo obligatorio

1. Leer el insight mas reciente dentro de `insights/` con nombre `insight_YYYY_MM_DD.json`.
2. Validar que existan los campos criticos:
   - `case.caso_titulo`, `case.patron_detectado`, `case.confidence`
   - `source.entidad_nombre`, `source.codigo_seace`, `source.fuente_oficial`
   - `script.voiceover_text_full`
   - `output.width`, `output.height`, `output.fps`
3. Abortar si `case.confidence < 0.8` o falta cualquier campo critico.
4. Mapear `case.patron_detectado` a plantilla:
   - `postor_unico_con_proceso_acelerado` → `templates/postor_unico.html`
   - `proveedor_recurrente` → `templates/proveedor_recurrente.html`
   - `fraccionamiento_contractual` → `templates/fraccionamiento.html`
   - `funcionario_sancionado_activo` → `templates/funcionario_sancionado.html`
   - default → `templates/postor_unico.html`
5. Copiar la plantilla a `index.html` y reemplazar todos los placeholders `{{ variable }}` con datos del insight.
6. Formatear montos como `S/ X,XXX,XXX`.
7. Censurar RUCs con el formato `20••••••XXX`, conservando solo los ultimos 3 digitos.
8. Leer `script.scene_times` del insight JSON. Inyectar los seis tiempos:
   - `t_intro`, `t_facts`, `t_context`, `t_compare`, `t_punch`, `t_cta`
   - Fallbacks si no existen: `0, 2, 5, 10, 14, 17`
   - `audio_duration` ← `output.duration_seconds`
   - `confidence_pct` ← `round(case.confidence * 100)`
8.5. Leer `assets/voiceover_timestamps.json`. Si tiene `words` con al menos 1 elemento, serializar como JSON compacto → `karaoke_words_json`. Si no, abortar.
9. Verificar checklist de animaciones en `index.html` generado.
10. Ejecutar `npx hyperframes lint index.html`.
11. Si lint falla por errores corregibles, autocorregir y reintentar hasta 2 veces.
12. Imprimir JSON final: `{"status":"ok","video_path":"...","case_title":"...","entity_name":"...","episode":"..."}`

## Variables de plantilla

### Comunes
`episode_label`, `caso_titulo`, `entidad_nombre`, `entidad_sigla`, `entidad_ruc_censurado`,
`monto_adjudicado_formato`, `objeto_contrato`, `numero_postores`, `dias_proceso`, `promedio_sector`,
`fuente_oficial`, `audio_duration`, `t_intro`, `t_facts`, `t_context`, `t_compare`, `t_punch`, `t_cta`,
`codigo_seace`, `confidence_pct`, `karaoke_words_json`

### Solo `funcionario_sancionado_activo`
`funcionario_dni_ultimos`, `sancion_fecha`, `firma_fecha`

## Sistema de animaciones de 3 capas

Las plantillas dependen de `assets/animations.css` y `assets/animations.js`.

### Capa 1: Ambiente
`#binary-rain` + `initBinaryRain()`, `.scanline` (4s), `.grid-pulse` (6s), `.corner-vignette` (3s), `.rec-indicator` (1s), `initPerryGlitch()` (4s)

### Capa 2: Bucles de elemento
`.anim-breathe`, `.anim-glow` (#monto-val), `.anim-wiggle` (flecha CTA), `.anim-cursor`, `.anim-survivor-glow`, `.anim-stamp-idle`, `.anim-hot`, `.anim-node-pulse`, `.anim-conflict-line`

### Capa 3: Helpers GSAP
`countUp`, `stampDrop`, `textCorrupt`, `rgbGlitch`, `growFromLeft`, `drawPath`, `slideIn`, `typeWriter`

## Reglas estrictas

- No publicar nombres propios sin censura si no hay sentencia firme.
- Frame final (scene-cta): solo marca "@agente_p" + "Siguenos en Agente P". Sin fuentes ni disclaimers.
- Si `confidence < 0.8` o falta campo critico, abortar con `status: "aborted"`.
- No inventar datos. Dato no critico faltante → usar "No reportado".
- No exponer RUCs, DNI, teléfonos, correos ni direcciones personales completos.
- Output: 1080x1920, 30fps, duración 19.5–20.5s (REGLA 1).
