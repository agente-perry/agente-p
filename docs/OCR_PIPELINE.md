# OCR Pipeline — AgentePerry

## Objetivo

Proveer una capa OCR profesional para PDFs de TDR/SEACE escaneados o mixtos, con trazabilidad por pagina, idempotencia y outputs reutilizables por el analizador TDR.

Esta capa no hace scraping nuevo y no depende de SUNAT.

## Cuando se usa OCR

1. Se clasifica el PDF con PyMuPDF:
   - `textual`: cobertura de texto >= 70%
   - `mixed`: cobertura entre 20% y 70%
   - `scanned`: cobertura < 20%
2. Reglas de ejecucion:
   - `textual`: no llamar proveedor OCR, usar texto digital
   - `mixed`: OCR solo en paginas sin texto suficiente
   - `scanned`: OCR en todas las paginas

## Variables de entorno (MiniMax)

- `MINIMAX_API_KEY`
- `MINIMAX_API_BASE` (default: `https://api.minimax.chat/v1`)
- `MINIMAX_OCR_MODEL` (default: `MiniCPM-v2`)
- `MINIMAX_OCR_WORKERS` (opcional para invocaciones CLI)

Seguridad:

- Nunca imprimir la API key.
- Si no existe key, el error aparece solo al intentar OCR real.

## Comandos CLI

Desde `apps/scrapers/`:

```bash
uv run agenteperry ocr classify --input ../../data/scraped/tdrs --recursive
uv run agenteperry ocr run --input ../../data/scraped/tdrs --recursive --limit 3 --dry-run
uv run agenteperry ocr run-one --pdf ../../data/scraped/tdrs/salud/ocds_1/tdr.pdf --dry-run
uv run agenteperry ocr bridge \
  --input ../../data/ocr \
  --contracts-jsonl ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --output-dir ../../data/ocr_bridge
uv run agenteperry ocr prepare-analyzer --input ../../data/ocr_bridge --limit 5
uv run agenteperry ocr prepare-loader --input ../../data/ocr_bridge --limit 5
uv run agenteperry ocr load-ready --input ../../data/ocr_bridge --dry-run
uv run agenteperry ocr run-all --input ../../data/scraped/tdrs --contracts-jsonl ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl --strict --load-ready --load-dry-run

# Integracion directa con CDC (opcional)
uv run agenteperry cdc run \
  --input ../../data/scraped/filtered/salud_2024_2025_with_documents.jsonl \
  --sector salud \
  --limit 5 \
  --ocr-fallback \
  --ocr-workers 2 \
  --ocr-out-dir ../../data/ocr
```

Opciones principales:

- `--recursive/--no-recursive`
- `--limit`
- `--workers`
- `--dry-run`
- `--force`
- `--output-dir`
- `--only-needs-ocr`
- `--ocid` (solo `run-one`)

## Outputs por documento

Directorio: `data/ocr/<document_id>/`

- `ocr_manifest.json`
- `ocr_pages.jsonl`
- `ocr_text.txt`
- `ocr_errors.jsonl` (si hay errores por pagina)

Campos clave del manifest:

- `source_pdf_sha256`
- `pages_attempted`, `pages_succeeded`, `pages_failed`
- `coverage_before_pct`, `coverage_after_pct`
- `status` (`completed`, `completed_with_errors`, `failed`, `skipped`)

## Idempotencia

Si existe `ocr_manifest.json` en estado `completed` y el SHA256 del PDF no cambio:

- `force=False` -> retorna `skipped`
- `force=True` -> reprocesa y sobreescribe outputs

## Limites de workers

- El cliente procesa paginas en paralelo con semaforo de concurrencia.
- Recomendado para pruebas: `--workers 1..5`
- Evitar corridas masivas sin `--dry-run` previo.

## Conexion con TDR analyzer

`ocr_pages.jsonl` y `ocr_text.txt` se usan como entrada de las siguientes etapas:

1. parse/pages
2. chunking
3. flags
4. dossier

Este modulo solo prepara texto confiable y trazable para esas etapas.

## Bridge OCR -> Analyzer (provenance + contract context)

El comando `ocr bridge` transforma outputs OCR por documento en bundles trazables para el analizador:

- `pages.json` (compatible con parser/chunker/flags)
- `contract_context.json` (entidad, supplier, monto, artifacts)
- `provenance.json` (source_pdf, sha256, manifest, paths de entrada/salida)
- `bundle_manifest.json` (resumen del bundle)

Esto asegura que cada TDR escaneado quede enlazado con su contexto contractual y artifacts relacionados, sin mezclar datos ni perder origen.

Por defecto corre en modo `--strict`: si no hay match contractual (cuando se pasa `--contracts-jsonl`) el bundle se marca como `skipped` con `missing_contract_context`. Para auditoria exploratoria se puede usar `--no-strict`.

## OCR-2: prepare-analyzer

El comando `ocr prepare-analyzer` toma bundles de `ocr bridge` y produce:

- `chunks.json`
- `flags.json`
- `analyzer_input_manifest.json` en la raiz del directorio bridge

Con esto, cada documento queda listo para ejecutar etapas posteriores del analyzer sin volver a OCR ni perder trazabilidad contractual.

Tambien corre en `--strict` por defecto y exige que existan `contract_context.json` y `provenance.json` para cada bundle antes de generar chunks/flags.

## OCR-2: prepare-loader

El comando `ocr prepare-loader` toma bundles ya procesados y genera:

- `tdr_manifest.jsonl` por bundle (metadata minima compatible con loader)
- `loader_input_manifest.json` en la raiz del directorio bridge

Este paso deja la integracion lista para `agenteperry tdr load-pipeline` por documento, manteniendo trazabilidad de OCR -> contexto contractual -> chunks/flags.

## OCR-2: load-ready

El comando `ocr load-ready` usa `loader_input_manifest.json` y carga bundles `ready` hacia tablas TDR usando `load_pipeline_json`.

- `--dry-run`: valida entradas sin escribir en DB.
- `--limit`: carga solo un subconjunto controlado.

## OCR-2: run-all

El comando `ocr run-all` orquesta en secuencia:

1. OCR por documento
2. bridge OCR -> contexto contractual
3. prepare-analyzer (chunks + flags)
4. prepare-loader (manifiestos para carga)
5. load-ready (opcional, con dry-run por defecto recomendado)

Sirve para ejecutar el flujo completo de extremo a extremo con una sola invocacion y checkpoints por etapa.

## Integracion CDC -> OCR fallback

`agenteperry cdc run` ahora puede procesar PDFs escaneados cuando se habilita `--ocr-fallback`.

- Si un PDF no tiene capa de texto usable, CDC intenta OCR por documento.
- Si OCR completa y genera `ocr_pages.jsonl`, CDC continua con chunking, flags y dossier.
- Si OCR falla, el contrato queda con estado `needs_ocr` y razon en `error`.

Esto permite una ruta unificada de analisis para PDFs digitales y escaneados, manteniendo el mismo output final (`pages.json`, `chunks.json`, `flags.json`, `dossier.json`, `dossier.md`).

## Politica operativa

- OCR es obligatorio como capacidad del sistema.
- OCR no es obligatorio para cada documento.
- Siempre clasificar antes de ejecutar OCR.
- No correr OCR masivo sin dry-run de inventario.
