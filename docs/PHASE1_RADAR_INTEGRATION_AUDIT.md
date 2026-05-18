# Phase 1 / Radar Integration Audit

**Fecha**: 2026-05-17
**Auditor**: opencode agent
**Spec**: SPEC-0009 + SPEC-0010

---

## Resumen Ejecutivo

Phase 1 implementa el pipeline de scraping para OCDS, SUNAT y SEACE.
Radar/CDC es un sistema de monitoreo separado (no de scraping) que puede
reutilizar las fuentes de Phase 1 para detección de cambios.

**Estado general**: En desarrollo. Scripts existen y pasan tests, pero
el orchestrator tiene un bug de naming corregido en esta sesión.

---

## 1. Inventario de Scripts Phase 1

| Script | Ubicación | Estado | Deps externas |
|--------|-----------|--------|---------------|
| `phase1_ocds_filter.py` | `scripts/` | ✅ Existe | urllib (stdlib) |
| `phase1_sunat_padron.py` | `scripts/` | ✅ Existe | urllib, zipfile (stdlib) |
| `phase1_seace_documents.py` | `scripts/` | ✅ Existe | `fitz` (PyMuPDF) |
| `phase1_ocr_classifier.py` | `scripts/` | ✅ Existe | `fitz`, MiniMax API |
| `validate_scraping_delivery.py` | `scripts/` | ✅ Existe | `fitz` |
| `build_process_document_packs.py` | `scripts/` | ✅ Existe | stdlib only |
| `select_golden_candidates.py` | `scripts/` | ✅ Existe | stdlib only |
| `phase1_orchestrator.py` | `scripts/` | ✅ Bug corregido | todos |

---

## 2. Bug Corregido

**Archivo**: `scripts/phase1_orchestrator.py`

**Problema**: Los IDs en `STEPS` tenían prefijo `1_`, `2_`, etc.
(`"1_ocds_filter"`, `"2_sunat_padron"`, ...). El código buscaba
`"phase1_1_ocds_filter.py"` en vez de `"phase1_ocds_filter.py"`.

**Fix**: Removido prefijo numerico de los step IDs:
```python
# Antes
("1_ocds_filter", "..."), ("2_sunat_padron", "..."), ...

# Después
("ocds_filter", "..."), ("sunat_padron", "..."), ...
```

El resto del código (`step_args`, `"4_ocr_classifier"`) sigue funcionando
porque las referencias están alineadas.

---

## 3. Dependencias Faltantes

Los scripts `phase1_seace_documents.py` y `phase1_ocr_classifier.py`
usan `import fitz` (PyMuPDF), pero la raíz del repo no tiene un
`pyproject.toml` que declare esta dependencia.

**Solución**: Ejecutar desde `apps/scrapers/` donde `pyproject.toml`
ya declara `pymupdf>=1.24`, o crear `pyproject.toml` en la raíz con
las dependencias necesarias para los scripts.

**Verificado**: En `apps/scrapers/` → `uv run pytest` funciona, pero
`uv run python scripts/...` desde la raíz falla con `ModuleNotFoundError: fitz`.

---

## 4. Test Suite — 148 Passed

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0
rootdir: /home/miguel/projects/hacklatam/apps/scrapers
configfile: pyproject.toml
plugins: cov-7.1.0, asyncio-1.3.0
asyncio: mode=Mode.AUTO
collected 148 items

148 passed in 2.61s
```

**Linting**: `uv run ruff check src/ tests/` → All checks passed!
**Type checking**: `uv run pyright src/` → 0 errors, 0 warnings

---

## 5. Módulos Compartidos Detectados

### Reutilización correcta
- `apps/scrapers/src/agenteperry/collectors/` → los parsers (OCDS, SUNAT,
  SEACE, SANCIONES, CKAN) son usados por el sync loader.
- `apps/scrapers/src/agenteperry/sync/loader.py` → upsert desde JSONL
  a las tablas `source_records`, `entities`, `relationships`.
- `apps/scrapers/src/agenteperry/tdr/loader.py` →upsert a `tdr_documents`,
  `tdr_pages`, `tdr_chunks`, `tdr_flags`, `tdr_embeddings` (pipeline completo).

### Módulos de Radar/CDC (no Phase 1)
- `apps/scrapers/src/agenteperry/radar/` — orchestrator, models, cdc, health
- `apps/scrapers/src/agenteperry/cdc/` — pipeline, detector

### Phase 1 scripts → standalone
Los scripts de `scripts/` son independientes. No importan desde
`src/agenteperry/`. Solo dependen de stdlib + fitz (PyMuPDF).

---

## 6. Estructura de Datos Phase 1

```
data/scraped/seace_salud/
  processes.csv      # OCDS filtrado salud+ambiente
  documents.csv      # PDFs baixados + OCR class
  awards.csv         # proveedores adjudicados
  pdfs/{process_id}/*.pdf
  manifests/process_document_packs.jsonl

data/sunat/
  padron_reducido_ruc.csv
  padron_enriched.csv

data/golden_set/
  metadata.csv
```

---

## 7. OCR Classification — MiniMax API

- **Key**: `MINIMAX_API_KEY` (ilimitado, no rate limit)
- **Modelo**: `MiniCPM-v2`
- **Parallelismo**: 20 workers default (configurable)
- **Output**: `ocr_class` ∈ {textual, mixed, scanned}

---

## 8. Radar/CDC — Integración con Phase 1

Phase 1 genera datos que Radar puede monitorear:

| Source | Datos generados | Uso Radar |
|--------|----------------|-----------|
| OCDS | `data/scraped/filtered/*.jsonl.gz` | Detectar cambios en contratos |
| SEACE docs | `data/scraped/seace_salud/pdfs/` | Detectar nuevos PDFs |
| SUNAT | `data/sunat/padron_enriched.csv` | Detectar cambios en RUCs |

Radar (spec-0010 pending) lee las fuentes y detecta changes via CDC.

---

## 9. Issues Abiertos

| Issue | Severity | Descripción |
|-------|----------|-------------|
| fitz no disponible en raíz | medium | Scripts fallan si no se ejecutan desde apps/scrapers |
| OCDS download falla con "embedded null byte" | high | La descarga de 2024 da error. Necesita debug |
| `.env` no tiene MINIMAX_API_KEY | medium | OCR classifier no funciona sin la key |
| data/scraped/seace_salud/ no existe | low | Creado por orchestrator o manualmente |

---

## 10. Recomendaciones

1. **Instalar fitz en raíz**: Crear `pyproject.toml` en la raíz o ejecutar
   los scripts desde `apps/scrapers/`.
2. **Debug OCDS 2024**: El URL puede haber cambiado o necesitar headers.
3. **Agregar MINIMAX_API_KEY a .env.example**.
4. **No hay duplicación**: Phase 1 y Radar son independientes.
   Phase 1 genera datos; Radar los monitorea.

---

## 11. Próximos Pasos (SPEC-0010, SPEC-0011)

- [ ] Integrar Radar con datos Phase 1
- [ ] Ejecutar orchestrator completo (con datos reales)
- [ ] Crear golden set metadata
- [ ] Limpiar repo (SPEC-0011)