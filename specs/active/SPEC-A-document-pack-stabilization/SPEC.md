# SPEC-A: Document Pack Stabilization — Contrato de Salida y Gates de Calidad

## Estado

- **Spec ID**: SPEC-A
- **Autor**: AgentePerry Staff AI Engineering
- **Fecha**: 2025-05-17
- **Branch**: `chore/SPEC-A-document-pack-stabilization`
- **Depende de**: SPEC-0009 (document-pack-graph, base funcional existente)

---

## Resumen ejecutivo

El módulo `document_pack/` (inventario, clasificación, pack builder, grafo, orchestrator) está **funcionalmente completo** con 284 tests passing. Esta fase cierra las brechas que impiden que el módulo sea **production-ready**:

1. **Contrato de salida versionado** — `analyze-pack` debe emitir JSON estable con `schema_version` para que el frontend no se rompa.
2. **Tests de integración del orchestrator** — `PackOrchestrator` necesita coverage de los flujos reales (pack cacheado, `max_docs`, mezcla usable/no usable).
3. **E2E CLI con fixtures** — smoke test completo de `build-pack` + `analyze-pack` con PDFs mínimos.
4. **Logs + métricas** — observabilidad básica por `pack_id` para depurar en datasets reales.
5. **Gates CI obligatorios** — pytest + ruff + pyright bloqueando merge.

---

## Brechas detalladas

### Gap 1: Contrato de salida sin versión

**Problema**: `PackAnalysisResult.to_dict()` no incluye `schema_version`, lo que impide a los consumidores saber cuándo cambió el formato.

**Solución**: Agregar campo `schema_version: str = "1.0"` al payload de salida. Cuando el contrato cambie, incrementar a `"1.1"`.

### Gap 2: Sin tests de integración de PackOrchestrator

**Problema**: `PackOrchestrator` no tiene tests dedicados. Los únicos tests son los 12 de `test_document_pack_builder.py` que testean `build_pack`, no el orchestrator.

**Flujos faltantes**:
- Pack existente en `_index/process_document_pack.json` → se carga sin rebuild
- `max_docs` limita correctamente los documentos analizados
- Documentos no-usables son saltados (no crash)
- `missing_for_graphrag` se propagan correctamente al resultado

**Solución**: Crear `tests/test_document_pack_orchestrator.py` con fixtures de tempdir + PDFs mínimos (reportlab) cubriendo los flujos arriba.

### Gap 3: Sin E2E CLI smoke test

**Problema**: Los tests de CLI (`test_cli_ocr.py`) no cubren `build-pack` ni `analyze-pack`. No hay smoke test que ejecute los comandos completos.

**Solución**: Agregar `tests/test_cli_pack.py` con `CliRunner` ejecutando `build-pack` + `analyze-pack` en un tmpdir con PDFs mínimos. Verificar:
- `build-pack` crea los 8 artefactos
- `analyze-pack` corre sin crash (modo mock)
- Código de salida = 0 en éxito

### Gap 4: Logs sin pack_id context

**Problema**: Los logs de `PackOrchestrator` incluyen `pack_id` en algunos mensajes pero no hay structured logging con `pack_id` como campo estándar.

**Solución**:
- Agregar `extra={"pack_id": pack.pack_id}` a todos los `logger.info/warning/error` del orchestrator
- Agregar resumen final al log: `total={total}, analyzed={analyzed}, skipped={skipped}, errors={errors}`

### Gap 5: Import circular resuelto parcialmente

**Problema**: El `__init__.py` original importaba desde `orchestrator.py` que a su vez importaba desde `document_pack`. Esto se "arregló" sacando los exports pero el import dentro de `orchestrator.py` sigue problematico.

**Estado actual**: El import en orchestrator.py (`from document_intelligence.document_pack import ProcessDocumentPack`) sigue apuntando a `__init__.py` que re-exporta. Esto funciona porque `__init__.py` ahora re-exporta `ProcessDocumentPack` desde `schemas`, pero es un import indirecto frágil.

**Solución**: En `orchestrator.py`, importar directamente desde `schemas`:
```python
from document_intelligence.document_pack.schemas import (
    ClassifiedDocument, MissingGraphRAGKey, PackMode, ProcessDocumentPack,
)
```

### Gap 6: ruff F401 `DocumentType` unused en orchestrator

**Problema**: `orchestrator.py` importa `DocumentType` de schemas pero no lo usa.

**Solución**: Remover `DocumentType` del import de `schemas` en `orchestrator.py`.

---

## Plan de implementación

### Fase A.1 — Contrato versionado

1. Editar `PackAnalysisResult.to_dict()` en `orchestrator.py` para incluir `"schema_version": "1.0"` como primer campo del dict.
2. Editar `__init__.py` de `document_pack` para que `PackOrchestrator`, `PackOrchestratorConfig`, `PackAnalysisResult` se exporten desde `orchestrator` (agregar al `__all__`).
3. Hacer commit: `feat(document_pack): add schema_version to PackAnalysisResult output (SPEC-A)`

### Fase A.2 — Tests de integración del orchestrator

4. Crear `tests/test_document_pack_orchestrator.py` con:
   - `_make_mini_pdf(tmp_dir, name)` helper usando reportlab
   - `test_orchestrator_builds_pack_if_no_cache` — invoca `PackOrchestrator().analyze()` con tmpdir vacío, verifica `pack_id` en resultado
   - `test_orchestrator_reuses_existing_pack` — crea `_index/process_document_pack.json` manualmente, verifica que no se rebuild
   - `test_orchestrator_respects_max_docs` — limita a 1 doc, verifica que solo 1 documento aparece en resultados
   - `test_orchestrator_skips_non_usable_documents` — pdf sin texto, verifica que no crash y skipped=1
   - `test_orchestrator_propagates_missing_for_graphrag` — pack sin award doc, verifica que `missing_for_graphrag` contiene `award_document`
5. Ejecutar tests. Si fallan, diagnosticar y corregir.
6. Commit: `test(document_pack): add PackOrchestrator integration tests (SPEC-A)`

### Fase A.3 — E2E CLI smoke test

7. Crear `tests/test_cli_pack.py`:
   - `test_build_pack_creates_all_artifacts` — `CliRunner.invoke(build-pack)`, verifica que se crean los 8 archivos
   - `test_analyze_pack_exits_zero_with_mock_mode` — invoca `analyze-pack` con `--mode mock`, verifica exit_code == 0
   - `test_analyze_pack_returns_json_with_schema_version` — parsea output JSON, verifica que tiene `schema_version`
8. Ejecutar tests. Corregir si hay fallas.
9. Commit: `test(document_pack): add E2E CLI smoke tests for build-pack and analyze-pack (SPEC-A)`

### Fase A.4 — Logs + métricas

10. Editar `PackOrchestrator.analyze()` para agregar logging estructurado con `pack_id` en cada `extra`:
    - Entrada: `logger.info("Starting pack analysis", extra={"pack_id": pack.pack_id, "total_docs": pack.total_documents})`
    - Por documento: `logger.info("Analyzed %(file)s (%(dtype)s) — %(flag_count)d flags", extra={"pack_id": pack.pack_id, ...})`
    - Resumen: `logger.info("Pack analysis complete", extra={"pack_id": pack.pack_id, "total": total, "analyzed": analyzed, "skipped": skipped, "errors": errors})`
11. Commit: `feat(document_pack): add structured logging with pack_id context (SPEC-A)`

### Fase A.5 — Limpieza ruff/pyright

12. Corregir import en `orchestrator.py` (importar `ProcessDocumentPack` desde `schemas` directamente, no desde `__init__`).
13. Remover `DocumentType` unused del import de `schemas` en `orchestrator.py`.
14. `uv run --extra dev ruff check src/document_intelligence/document_pack tests/test_document_pack_*.py --fix`
15. `uv run --extra dev pyright src/document_intelligence/document_pack`
16. Commit: `chore(document_pack): fix imports and remove unused imports (SPEC-A)`

### Fase A.6 — Gates CI

17. Verificar que `pyproject.toml` tiene scripts correctos para pytest/ruff/pyright.
18. Ejecutar `uv run --extra dev pytest tests/ -q && uv run --extra dev ruff check src/document_intelligence/document_pack tests/test_document_pack_*.py && uv run --extra dev pyright src/document_intelligence/document_pack`
19. Commit: `chore(document_pack): enforce CI gates (pytest, ruff, pyright) on document_pack (SPEC-A)`

---

## Criterios de aceptación (Definition of Done)

- [ ] `PackAnalysisResult.to_dict()` incluye `"schema_version": "1.0"` como primer campo
- [ ] `tests/test_document_pack_orchestrator.py` existe con ≥5 tests cubriendo los flujos descritos
- [ ] `tests/test_cli_pack.py` existe con ≥3 tests cubriendo los flujos E2E
- [ ] Todos los tests pasan: `pytest tests/ -q` → 0 failures
- [ ] `ruff check src/document_intelligence/document_pack tests/test_document_pack_*.py` → 0 errors
- [ ] `pyright src/document_intelligence/document_pack` → 0 errors
- [ ] Los artefactos de `build-pack` incluyen todos los 8 archivos en output
- [ ] `analyze-pack --mode mock` retorna exit code 0 con JSON conteniendo `schema_version`
- [ ] Logs de `PackOrchestrator` incluyen `pack_id` en todos los mensajes

---

## Artefactos generados

```
specs/active/SPEC-A-document-pack-stabilization/
  SPEC.md   — este archivo
  RATIONALE.md  — explica cada decisión de diseño (opcional, para reviewers)
```

---

## Seguimiento

Revisar el estado de la implementación ejecutando:

```bash
cd packages/document_intelligence
uv run --extra dev pytest tests/test_document_pack_orchestrator.py tests/test_cli_pack.py -v
uv run --extra dev ruff check src/document_intelligence/document_pack
uv run --extra dev pyright src/document_intelligence/document_pack
```

El spec se marca como **DONE** cuando todos los criterios de aceptación son verdes.