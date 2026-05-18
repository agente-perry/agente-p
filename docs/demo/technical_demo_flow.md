# Technical Demo Flow — AgentePerry TDR Scanner

> **Nota:** Este documento describe el flujo técnico completo de la demo para jueces y评委 técnicos. Incluye comandos reales, output esperado y explicación de cada paso.

---

## Arquitectura general

```
OCDS JSONL (SEACE público)
       │
       ▼
  SEACE Change Detector
       │  Hash-based change detection
       │  Sector filter (salud / ambiente / otros)
       ▼
  CDCPipeline
       │
       ├── select_tdr_documents()  ← elegir mejor PDF
       ├── download_document()      ← guardar archivo
       ├── inspect_pdf_text_layer() ← OCR gate
       │      ✅ Text layer → process
       │      ❌ Scanneado → needs_ocr → skip
       │
       ├── extract_pdf_pages()       ← página por página
       ├── chunk_pages()             ← chunks semánticos
       ├── compute_embeddings()     ← vector por chunk
       ├── detect_flags_in_pages()  ← 12 reglas con evidencia
       │      flags: monto_atipico,
       │             unico_postor,
       │             modificatoria,
       │             presentacion_fisica, etc.
       │
       └── generate_dossier()        ← Markdown + cita + página + fuente
              │
              ▼
         data/results/<ocid>/dossier.md
```

---

## Flujo paso a paso

### Paso 0 — Preparar entorno (solo una vez)

```bash
cd apps/scrapers
uv sync
```

### Paso 1 — Descargar un contrato OCDS

```bash
# Descarga metadata del contrato desde SEACE
agenteperry tdr download \
  --ocid ocds-dgv273-seacev3-988512 \
  --out-dir data/results/
```

**Output esperado:**
```
📥 Descargando contrato ocds-dgv273-seacev3-988512...
✅ Metadata guardada en data/results/ocds-dgv273-seacev3-988512/
📄 Documentos encontrados: 12 PDFs
```

### Paso 2 — Auditar PDFs (quality gate)

```bash
# Evalúa cada PDF: ¿tiene texto digital o es escaneado?
agenteperry tdr audit-pdfs \
  --input data/results/ocds-dgv273-seacev3-988512/ \
  --sector salud
```

**Output esperado:**
```
Audit de PDFs — contrato ocds-dgv273-seacev3-988512
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Pliego_de_Absolucion_de_Consultas_y_Observaciones.pdf
   └─ 212 páginas — ✅ 100% texto digital — PROCESAR

📄 Bases_y_Pliegos.pdf
   └─ 48 páginas — ⚠️ 0% texto (escaneado) — needs_ocr

📄 Otros_Documentos.pdf
   └─ 12 páginas — ✅ 100% texto digital — PROCESAR

Total: 12 PDFs
  ✅ Con texto: 11 — se procesan
  ❌ Escaneados: 1 — se marcan needs_ocr
```

**Nota clave:** El sistema detecta que hay un PDF escaneado y lo excluye. No intenta analizarlo sin OCR. Esto evita falsos positivos por texto ilegible.

### Paso 3 — Analizar el documento

```bash
# Procesa páginas, genera chunks, detecta flags, crea dossier
agenteperry tdr analyze \
  --ocid ocds-dgv273-seacev3-988512 \
  --sector salud \
  --out-dir data/results/
```

**Output esperado:**
```
🔍 Analizando contrato ocds-dgv273-seacev3-988512
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 Pliego_de_Absolucion... — procesando 212 páginas...
   Páginas procesadas: 212/212 ✅
   Chunks generados: 445
   Flags detectados: 1 (11 falsos positivos — documento procesal)

📄 Otros_Documentos.pdf — procesando 12 páginas...
   Páginas procesadas: 12/12 ✅

⚠ Flags de baja confianza descartados: 11

📋 Dossier generado:
   data/results/ocds-dgv273-seacev3-988512/dossier.md
```

### Paso 4 — Ver el dossier generado

```bash
cat data/results/ocds-dgv273-seacev3-988512/dossier.md
```

**Fragmento del dossier esperado:**

```markdown
# Dossier — ocds-dgv273-seacev3-988512

## Metadata
- **Entidad:** Seguro Social de Salud — ESSALUD
- **Proceso:** AS-SM-55-2023-ESSALUD/GCL-1
- **Objeto:** Servicio de Seguridad y Vigilancia
- **Monto:** S/ 195,383,235.96
- **Ganador:** VIPROSEG S.A.C.
- **Duración:** 1,095 días

## Flags detectados

### ✅ Flag: presentacion_fisica_perfeccionamiento
- **Severidad:** MEDIA
- **Página:** 17
- **Chunk:** "La documentación para el perfeccionamiento del contrato
   ¿podrá ser presentado por mesa de partes virtual?"
- **Evidencia:**
  > "Debe presentar la documentación requerida en Jr. Domingo Cueto N° 120,
  > Primer Piso, Jesús María - Lima."
- **Fuente:** Pliego de Absolución de Consultas y Observaciones, pág. 17
- **Nota:** El documento es procesal, no técnico. Las 11 señales restantes
  fueron falsos positivos porque el texto no contiene especificaciones técnicas.

## Limitaciones
Este análisis se basa en el pliego procesal, no en el TDR técnico completo.
No se puede determinar si el requisito presencial afectó la competencia
sin analizar las bases completas y el TDR técnico.
```

### Paso 5 — CDC Pipeline completo (dry-run)

```bash
# Detecta cambios en un JSONL de contratos
agenteperry cdc run \
  --input ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud \
  --limit 10 \
  --dry-run \
  --hash-db /tmp/cdc_hashes.json
```

**Output esperado:**
```
CDC Run — input: salud_2024_2025_with_documents.jsonl
  Cargados 2,566 registros OCDS
  Hash DB: /tmp/cdc_hashes.json (0 hashes conocidos)

Resumen de cambios detectados en 2,566 registros:
  ✅ 2,566 contratos NUEVOS
  ⏭️  0 sin cambios — ignorados
  🎯 2,566 contratos de sectores prioritarios

--dry-run: no se descarga ni analiza nada.
```

### Paso 6 — CDC Pipeline real (5 contratos)

```bash
agenteperry cdc run \
  --input ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud \
  --limit 5 \
  --hash-db /tmp/cdc_hashes.json \
  --out-dir data/results/
```

**Output esperado:**
```
Contratos procesados
┏━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━┳━━━━━━━┳━━━━━━━━┓
┃ OCID          ┃ Entidad        ┃ Estado      ┃ Pp  ┃ Chunks ┃ Flags ┃ Riesgo ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━╇━━━━━━━╇━━━━━━━━┩
│ s-dgv273-sea… │ SEGURO SOCIAL  │ ⚠ needs_ocr │ 150 │ —      │ —     │ —      │
│ ds-dgv273-se… │ SEGURO SOCIAL  │ ✅ dossier  │ 212 │ 445    │ 1     │ MEDIO  │
│ ds-dgv273-se… │ SEGURO SOCIAL  │ ✅ dossier  │ 182 │ 383    │ 8     │ ALTO   │
│ 3-seacev3-20… │ SEGURO SOCIAL  │ ⚠ needs_ocr │ 154 │ —      │ —     │ —      │
│ ds-dgv273-se… │ SEGURO SOCIAL  │ ✅ dossier  │ 182 │ 383    │ 8     │ ALTO   │
└───────────────┴────────────────┴─────────────┴─────┴────────┴───────┴────────┘
```

---

## Comandos completos para la demo

```bash
# 1. Setup
cd apps/scrapers && uv sync

# 2. Descargar contrato
agenteperry tdr download \
  --ocid ocds-dgv273-seacev3-988512 \
  --out-dir data/results/

# 3. Auditar PDFs
agenteperry tdr audit-pdfs \
  --input data/results/ocds-dgv273-seacev3-988512/ \
  --sector salud

# 4. Analizar
agenteperry tdr analyze \
  --ocid ocds-dgv273-seacev3-988512 \
  --sector salud \
  --out-dir data/results/

# 5. Ver dossier
cat data/results/ocds-dgv273-seacev3-988512/dossier.md

# 6. CDC dry-run
agenteperry cdc run \
  --input ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud --limit 10 --dry-run

# 7. CDC real
agenteperry cdc run \
  --input ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud --limit 5
```

---

## Verificación post-demo

```bash
# Tests
uv run --extra dev pytest tests/ -q

# Lint
uv run --extra dev ruff check src tests

# Type check
uv run --extra dev pyright
```

**Resultado esperado:** 126 tests passed, 0 errors.

---

*Fuentes: Portal SEACE, OCDS, proceso AS-SM-55-2023-ESSALUD/GCL-1.*