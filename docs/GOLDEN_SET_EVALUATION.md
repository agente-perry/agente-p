# Golden Set Evaluation — SPEC-0007

How to validate the Document Intelligence Core against real TDR PDFs.

## Why a golden set

Until now the engine has only been exercised against synthetic fixtures.
The hackathon demo needs a calibrated yes/no answer to:

> Does the engine produce useful, well-cited signals on real Peruvian TDRs,
> with acceptable precision and minimal false positives?

A golden set is the cheapest path to that answer: 2–3 hand-picked PDFs, a
human verdict per emitted flag, and a delta plan for the next PR.

## How to obtain PDFs

Priorities (in order):

1. **Salud / equipamiento medico** — high signal for `SPECIFIC_EQUIPMENT_REQUIREMENT`,
   `EXCESSIVE_CERTIFICATION_REQUIREMENT`, `OBSOLETE_PHYSICAL_FORMAT`.
2. **Infraestructura municipal** — high signal for `OVER_SPECIFIED_EXPERIENCE`,
   `SUBJECTIVE_EVALUATION_CRITERIA`.
3. **Educacion regional** — high signal for `EXCESSIVE_DOCUMENT_REQUIREMENT`,
   `LOW_TRACEABILITY_OUTPUT`.

Sources to scan manually (no scraping in PR #5):

- SEACE public listings for recent `bases` and `TDR` PDFs.
- Regional government portals.
- Civic-tech repositories of past procurement controversies (e.g. OjoPublico).

Save each PDF as `data/golden_set/pdfs/<sensible_name>.pdf`. Never commit.

## How to fill metadata

1. Copy the schema:
   ```bash
   cp data/golden_set/metadata.example.csv data/golden_set/metadata.csv
   ```
2. One row per PDF. Columns documented in `data/golden_set/README.md`.
3. `expected_flags` is your *prediction* of what the engine should detect,
   written **before** running the script — that is what makes precision and
   recall meaningful.
4. `question` overrides the default analysis question on a per-row basis.

## Running the batch

From the repo root:

```bash
make doc-intel-install   # one-time, if not already done
python scripts/run_golden_set.py \
  --metadata data/golden_set/metadata.csv \
  --pdf-dir data/golden_set/pdfs \
  --out data/golden_set/outputs \
  --python packages/document_intelligence/.venv/bin/python
```

The `--python` flag points at the venv that has `document-intelligence`
installed. Omit it if the active interpreter already has the package.

Outputs:

- `data/golden_set/outputs/<id>.analysis.json` — one full `AnalysisResult` per PDF.
- `data/golden_set/outputs/<id>.analysis.json` also includes `parse_summary` when
  produced via the canonical CLI, exposing `pages_needing_ocr`,
  `ocr_applied_pages`, `ocr_available`, etc.
- `data/golden_set/outputs/summary.json` — aggregated counts + per-document
  precision/recall estimates against the `expected_flags` column.

## Metrics to review

| Metric | Where | Healthy range |
|--------|-------|---------------|
| `documents_analyzed / documents_total` | `summary.json` | == 1.0 (any failure is a bug) |
| `flags_total` | `summary.json` | 2–6 per PDF on average for real bases |
| `flags_by_code` | `summary.json` | No single flag dominates >70% across PDFs |
| `per_document.<id>.precision_estimate` | `summary.json` | ≥ 0.5 acceptable for v1 |
| `per_document.<id>.recall_estimate` | `summary.json` | ≥ 0.5 acceptable for v1 |
| `documents_with_no_flags` | `summary.json` | Investigate when expected_flags was non-empty |
| `errors` | `summary.json` | Should be empty |

Precision/recall are *estimates* because `expected_flags` is a human guess
made before running the engine. Use them to detect drift, not as ground truth.

## Human review checklist per flag

For each `flags[]` entry in every `<id>.analysis.json`, walk the checklist
and record verdicts in `data/golden_set/outputs/<id>.review.md` (gitignored):

- [ ] **Cita literal**: the `tdr_evidence.quote` exists verbatim in the PDF.
- [ ] **Pagina correcta**: open the PDF at `tdr_evidence.page_number` and confirm.
- [ ] **Flag correcta**: does the quoted text actually justify the flag code?
- [ ] **Doctrina aplica**: read `doctrine_anchor.quote`; does it apply to the case?
- [ ] **Explicacion no acusa**: no banned vocabulary, no leaps beyond evidence.
- [ ] **Pregunta util**: each `questions_for_authority[]` reads like a real journalist question.
- [ ] **No falso positivo**: if the quote is generic or out of context, mark as FP.

Aggregate per-document: how many flags are *true positives*, *false positives*,
*missing*. Feed these counts into `docs/FLAG_CALIBRATION_NOTES.md`.

## How to interpret the result

Three possible verdicts after one pass:

1. **GREEN — Engine usable as-is**. Precision and recall both ≥ 0.5, no banned
   vocabulary, citations align with pages. Move to PR #6 (real doctrine).
2. **YELLOW — Calibration needed**. Many false positives, or one flag fires
   on every doc. Update `docs/FLAG_CALIBRATION_NOTES.md`, tighten one or two
   patterns in `agents/risk_analysis.py`, re-run.
3. **RED — Structural problem**. Citations don't match pages, doctrine
   anchors are wrong, or the synthesizer leaks banned terms. Stop and triage;
   do not advance to PR #6.

## OCR / scanned PDFs

When the first golden-set pass ran, `tdr_salud_001.pdf` showed 143/143 pages
marked `needs_ocr=True` — the PDF was scanned, no embedded text. The agent
layer produced 0 flags because there was nothing to read. PR #6 added the OCR
fallback to handle that class of document.

### Running the batch with OCR

```bash
python scripts/run_golden_set.py \
  --metadata data/golden_set/metadata.csv \
  --pdf-dir data/golden_set/pdfs \
  --out data/golden_set/outputs \
  --python packages/document_intelligence/.venv/bin/python \
  --ocr auto
```

The summary now includes an `ocr` section:

```json
{
  "ocr": {
    "mode": "auto",
    "documents_needing_ocr": 1,
    "pages_needing_ocr": 143,
    "pages_ocr_applied": 0,
    "ocr_available": false
  }
}
```

If `ocr_available: false`, install Tesseract + the Spanish language pack
(see `docs/AGENT_DOCUMENT_CORE.md` § OCR for the exact commands), then re-run.

### Interpreting OCR outcomes

- `pages_ocr_applied == pages_needing_ocr` → engine had usable text on every
  page. Walk the human checklist on the resulting flags.
- `pages_ocr_applied < pages_needing_ocr` and `ocr_available == false` →
  Tesseract is not installed locally. Install it and re-run, or rule the PDF
  out of the golden set until OCR works.
- `pages_ocr_applied == 0` despite `ocr_available == true` → OCR ran but the
  scan quality is too low. Capture page-level `ocr_error` from
  `tdr_<id>.analysis.json` for diagnosis.

## What is intentionally out of scope here

PR #5 is the *first* contact with real PDFs. It deliberately does **not**:

- Re-train embeddings or clustering.
- Touch SEACE / SUNAT / scrapers.
- Replace the doctrine stub.
- Add UI, alerts, or persistence.
- Run the engine in `llm` mode.

Those decisions wait for the calibration verdict.
