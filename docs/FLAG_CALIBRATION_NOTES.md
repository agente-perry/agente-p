# Flag Calibration Notes — SPEC-0007

Running log of pattern changes to `agents/risk_analysis.py` driven by
observations on the golden set. Each entry should be small, justified by a
real PDF, and accompanied by a test.

## Editorial rules

1. Adjust a pattern only when at least one golden-set PDF shows a clear false
   positive **or** missed obvious match. Synthetic fixtures are not enough.
2. Each adjustment ships with:
   - a one-paragraph justification with PDF id + page,
   - a regression test in `tests/test_risk_analysis.py` (positive and, if
     applicable, negative case),
   - an entry below.
3. Never widen a pattern to grab a real PDF that the engine missed *but a
   human would also miss* — that means the flag definition itself is too broad
   and belongs in a separate spec.
4. Never silently soften the `LegalSafetyFilter` list. New banned terms come
   in, never out.

## Template

```markdown
### YYYY-MM-DD — <flag_code>

- **PDF**: `<id>` (`data/golden_set/pdfs/<file_name>`), page <N>.
- **Symptom**: <what the engine did vs what it should have done>.
- **Change**: <one-line summary of regex/pattern diff>.
- **Test**: `tests/test_risk_analysis.py::test_<name>`.
- **Risk**: <what this might break, e.g. could match plain "documento original">.
```

## Log

### 2026-05-17 — EXCESSIVE_DOCUMENT_REQUIREMENT (PR #7)

- **PDF**: `tdr_mineria_001` (`data/golden_set/pdfs/tdr_mineria_001.pdf`), pages 10, 11, 20, 22, 69.
- **Symptom**: Pattern `r"anexos?"` and `r"formatos?"` fired on boilerplate section headers and generic references present in every Peruvian procurement document. Also fired on `r"documentos?\s+adminis"` which matches any mention of administrative documents. 5 false positives in total.
- **Change**:
  - REMOVED (4 bare patterns): `r"documentos?\s+adminis"`, `r"anexos?"`, `r"formatos?"`, `r"lista\s+extensa"`
  - ADDED (11 strong signals): `copia(s)? legalizada`, `notarial`, `fedatead`, `foliad`, `visado`, `original y copia`, `tres juegos`, `sobre cerrado`, `entrega fisica obligatoria`, numeric documentary burden (`\d+ documentos`, `no menor a \d+`)
  - Result: 0 flags emitted on Golden Set (was 7/7 false positives).
- **Tests**: `tests/test_risk_analysis.py::test_excessive_doc_does_not_fire_on_bare_anexos`, `test_excessive_doc_does_not_fire_on_bare_formatos`, `test_excessive_doc_does_not_fire_on_declaraciones_juradas`, `test_excessive_doc_does_not_fire_on_generic_annex_header`, `test_excessive_doc_fires_on_copia_legalizada`, `test_excessive_doc_fires_on_foliado_visado`, `test_excessive_doc_fires_on_entrega_fisica_obligatoria`, `test_excessive_doc_fires_on_lista_extensa_de_documentos`, `test_excessive_doc_fires_on_presentar_siguientes_n_documentos`, `test_excessive_doc_fires_on_tres_juegos`, `test_excessive_doc_fires_on_sobre_cerrado`
- **Dedup**: `_semantic_dedup()` with Jaccard >= 0.7 threshold, keeping higher-confidence candidate.
- **Pattern catalog**: `flags/patterns.yaml` created with `ignore_patterns`, `medium_patterns`, `strong_patterns` per flag.

### 2026-05-17 — Semantic Dedup (PR #7)

- **Symptom**: Duplicate flags from near-identical quotes across adjacent pages (Jaccard >= 0.7 similarity).
- **Change**: `_semantic_dedup()` added to `RiskAnalysisAgent.analyze()`. Normalizes text (lowercase, accent-fold, remove punctuation, first 180 chars) and uses Jaccard similarity to suppress lower-confidence duplicates.
- **Tests**: `test_semantic_dedup_keeps_higher_confidence`, `test_semantic_dedup_keeps_different_flags`, `test_semantic_dedup_merges_near_duplicate_pages`

### 2026-05-17 — All Other Flags (PR #7)

- **Status**: No patterns changed for `LOW_TRACEABILITY_OUTPUT`, `OBSOLETE_PHYSICAL_FORMAT`, `SPECIFIC_EQUIPMENT_REQUIREMENT`, `EXCESSIVE_CERTIFICATION_REQUIREMENT`, `SUBJECTIVE_EVALUATION_CRITERIA`, `UNREALISTIC_DEADLINE`, `OVER_SPECIFIED_EXPERIENCE`.
- **Rationale**: Golden Set produced 0 flags for these codes; patterns appear intact. Review notes from SPEC-0005 open questions remain valid.

### 2026-05-17 — Query expansion + anti-hallucination fix (PR #8)

- **Scope**: retrieval/planner improvement. Patterns in `risk_analysis.py`
  intentionally untouched.
- **Added**: `flags/intent_map.yaml` with four intents (`risk_scan`,
  `documentary_burden`, `evaluation_discretion`, `market_restriction`)
  triggered by accent-folded substring match on the user question.
- **Added**: PlannerAgent intent expansion. Candidate flag set widens from
  doctrine hits + intent unions. New `PlannerAudit.expansion_sources` and
  `PlannerAudit.intent_matches` audit the provenance of every flag code.
- **Added**: PlannerConfig `enable_intent_expansion=True` and
  `fallback_to_all_flags_when_empty=True`. Both off → restores PR#7
  behaviour for strict tests.
- **Added**: `planner_queries.yaml` expanded with 3–4 retrieval templates
  per flag aligned with the strong-signal regex in
  `agents/risk_analysis.py` (e.g. "copia legalizada notarial",
  "a juicio del comite", "marca modelo especifico").
- **Added**: `cli.py --debug-retrieval` emits a JSON diagnostic block with
  question, planner audit, clusters_selected, queries_generated,
  retrieval_hits per query, candidate_patterns_seen,
  flags_{candidate,accepted,rejected}_count, and `flags_rejected_reasons`
  (parallel to `CriticCritique.rejected`).
- **Added**: `CriticCritique.reject_reasons: list[str]` so debug clients can
  read rejection reasons without sniffing private state. Field is
  documented as internal-only and must never reach user-facing copy.
- **Fixed (anti-hallucination)**: `_extract_quote()` now strips the trailing
  `"..."` that `TDRIndex` appends to truncated `text_excerpt` before
  performing window extraction. Without this fix, every quote from a
  long chunk ended with `"..."` and failed `EvidenceCriticAgent`'s
  literal-substring check against the full chunk text. Discovered via the
  real run on `tdr_ambiente_positive_001` page 52.
- **Tests added (PR #8)**:
  `test_intent_expansion.py` (6 tests on intent matching + expansion),
  `test_planner_expansion.py` (4 tests on planner with/without intent),
  `test_debug_retrieval.py` (5 integration tests on debug payload shape +
  reject reasons + boilerplate quiet).
- **Gates**: pytest 168 passed, ruff clean, pyright 0.

### 2026-05-17 — Pattern relaxation evidence-backed (PR #9)

Closes the OVER_SPECIFIED_EXPERIENCE gap identified in PR #8 and adds two
more medium-strength patterns surfaced by the debug retrieval scan over the
Golden Set. Total 3 new patterns. All evidence-backed. All paired with
positive + negative regression tests.

#### Pattern 1 — OVER_SPECIFIED_EXPERIENCE / "establecida en las bases"

- **Added**:
  ```python
  re.compile(
      r"experiencia\s+espec[ií]fica\s+(?:establecida|requerida|exigida|definida)"
      r"\s+en\s+(?:las\s+bases|el\s+procedimiento)",
      re.IGNORECASE,
  )
  ```
- **Evidence**: `tdr_ambiente_positive_001` p52 + `tdr_mineria_001` p52 (same SIE
  template). Verbatim quote: *"experiencia especifica establecida en las bases
  del procedimiento de seleccion"*.
- **Anchor required**: `establecida|requerida|exigida|definida` followed by
  `en (las bases|el procedimiento)`. Plain `"experiencia especifica"` never matches.
- **Tests**: `test_over_specified_fires_on_experiencia_establecida_en_bases`,
  `test_over_specified_does_not_fire_on_bare_experiencia_especifica`,
  `test_over_specified_does_not_fire_on_anchor_without_experiencia`.
- **Severity assigned**: medium (0.65) — signal is a pointer to the qualification
  clause, not proof of restrictiveness on its own. Review notes flag it as
  "señal débil" when it appears in pure template form.

#### Pattern 2 — OVER_SPECIFIED_EXPERIENCE / "similares al objeto"

- **Added**:
  ```python
  re.compile(
      r"(?:contratos?|servicios?|experiencia)\s+(?:iguales?\s+o\s+)?"
      r"similares\s+al\s+objeto",
      re.IGNORECASE,
  )
  ```
- **Evidence**: `tdr_salud_pliego_001` p206. Quote: *"contratación de servicios
  iguales o similares al objeto de convocatoria de los últimos ocho (08) años"*.
  Narrow-scope qualification clause common in tailored procurements.
- **Anchor required**: lead noun `contratos|servicios|experiencia`. Plain
  `"similar al objeto"` does not match.
- **Tests**: `test_over_specified_fires_on_servicios_similares_al_objeto`,
  `test_over_specified_does_not_fire_on_bare_similar_al_objeto`.

#### Pattern 3 — EXCESSIVE_DOCUMENT_REQUIREMENT / "firmas legalizadas ante notario"

- **Added**:
  ```python
  re.compile(r"firmas?\s+legalizadas?\s+ante\s+notari", re.IGNORECASE)
  ```
- **Evidence**: `tdr_ambiente_positive_001` p21 + `tdr_mineria_001` p21. Quote:
  *"Contrato de consorcio con firmas legalizadas ante notario público"*.
  Real notarial burden on every consortium member.
- **Anchor required**: `ante notari` (matches `ante notario` / `ante notarial`).
  Plain `"firmas digitales"` / `"firmas electrónicas"` do not match because
  the suffix is `digital`/`electronica`, not `notari…`.
- **Tests**: `test_excessive_doc_fires_on_firmas_legalizadas_ante_notario`,
  `test_excessive_doc_does_not_fire_on_firmas_digitales`.

#### Regression — PR #7 zero-FP baseline preserved

Four explicit regression tests pin the boilerplate that produced the original
7 false positives:

- `test_pr9_does_not_reintroduce_bare_anexos_fp` — "Veanse los anexos..."
- `test_pr9_does_not_reintroduce_bare_formatos_fp` — ".pdf .docx .xlsx..."
- `test_pr9_does_not_reintroduce_declaraciones_juradas_fp` — full SIE boilerplate
- `test_pr9_does_not_reintroduce_modelo_referencial_costos_fp` —
  `"Modelo referencial de Estructura de Costos"` must NOT fire
  `SPECIFIC_EQUIPMENT_REQUIREMENT` (it refers to cost-template, not equipment).

#### Golden Set verdict after PR #9

| Metric | PR #8 | PR #9 |
|--------|-------|-------|
| Documents analyzed | 3 (+1) | 3 |
| Flags total | 0 | 5 |
| Flags by code | {} | OVER:3, EXCESSIVE_DOC:2 |
| FPs reintroduced | 0 | 0 |
| Tests | 168 | 179 (+11) |

5 flags in 3 PDFs. 3 medium-strong, 2 weak (template duplicate). All carry
literal quote, page number, doctrine anchor, and pass `LegalSafetyFilter`.

Verdict: GREEN with the caveat that 2 of the 5 are "señal débil" (pointer to
template-driven qualification clause). The hackathon narrative is concrete
for the first time.

### 2026-05-17 — Severity tuning + test coverage gap close (PR #10)

Closes two test coverage gaps identified after PR #9 landed:

1. `_is_weak_signal()` / severity tuning logic was implemented but had zero
   dedicated tests (implicit coverage only via end-to-end golden set runs).
2. `CriticCritique.reject_reasons` was implemented and wired in PR #8 but
   had no unit tests verifying its content and parallel structure.

#### Severity tuning — `_is_weak_signal`

A candidate is considered "weak" when **both** conditions hold:

- `cluster_hint` is `"Otros"`, `"Confidencialidad y propiedad"`, or `""`
  (neutral cluster indicating boilerplate location), **AND**
- the matched quote contains no narrowing anchor for that flag code
  (e.g. for `OVER_SPECIFIED_EXPERIENCE`: no year number, no `monto acumulado`,
  no `del mismo sector`, no `restrictiv`).

When weak → `severity` is downgraded to `"low"` and `confidence` is capped at
`min(base_confidence, 0.45)`. The flag still surfaces as a human-review pointer
but does not inflate the aggregate score in Phase 3.

- **Tests added (7)**:
  - `test_weak_signal_downgraded_to_low_severity` — integration: neutral
    cluster, no year → severity=low, confidence≤0.45
  - `test_year_anchor_prevents_downgrade` — integration: neutral cluster +
    "8 años" → severity=high, confidence≥0.65
  - `test_non_neutral_cluster_never_downgraded` — integration: non-neutral
    cluster → severity=high regardless
  - `test_is_weak_signal_true_neutral_cluster_no_anchor` — unit
  - `test_is_weak_signal_false_year_present` — unit
  - `test_is_weak_signal_false_non_neutral_cluster` — unit
  - `test_is_weak_signal_false_monto_anchor` — unit

#### `reject_reasons` — EvidenceCriticAgent

- **Tests added (4)**:
  - `test_critic_reject_reasons_populated_on_rejection` — format is
    `"FLAG_CODE: reason text"`; empty-quote rejection emits `"vacio"`.
  - `test_critic_reject_reasons_parallel_to_rejected` — always
    `len(reject_reasons) == len(rejected)`
  - `test_critic_reject_reasons_empty_when_all_accepted`
  - `test_critic_reject_reasons_empty_on_empty_input`

#### Golden Set verdict after PR #10

| Metric | PR #9 | PR #10 |
|--------|-------|--------|
| Documents analyzed | 3 | 3 (unchanged) |
| Flags total | 5 | 5 (unchanged) |
| FPs reintroduced | 0 | 0 |
| Tests | 179 | 191 (+12) |
| `_is_weak_signal` test coverage | 0 explicit | 7 |
| `reject_reasons` test coverage | 0 explicit | 4 |

Verdict: GREEN. All 5 golden-set flags confirmed. Severity tuning and
reject_reasons telemetry fully covered. The only p52 "señal débil" now
correctly surfaces as `severity=low` when its cluster is neutral.
Next blocker: Fase 2 entry requires ≥3 verified flags in ≥2 distinct
templates; currently salud + ambiente/minería (same SIE template) = 2 true
templates. Need 1 additional non-SIE PDF.

### 2026-05-17 — Severity tuning + score debug-only (PR #10)

#### Severity downgrade for weak template signals

- **Symptom**: `OVER_SPECIFIED_EXPERIENCE` pattern PR #9 fires on the SIE-ANA
  template phrase `"experiencia especifica establecida en las bases del
  procedimiento"`. Quote is structurally valid but lacks any narrowing anchor
  (no numeric year, no monto, no "objeto similar", etc.) — i.e. a template
  pointer, not a restrictive clause.
- **Change**: `_is_weak_signal(flag_code, quote, cluster_hint)` helper added.
  When (a) `cluster_hint ∈ {"Otros", "Confidencialidad y propiedad", ""}` AND
  (b) the quote contains **no** narrowing anchor from
  `_NARROWING_ANCHORS_BY_FLAG[flag_code]` → severity is downgraded to `"low"`
  and confidence is capped at `0.45`. The flag still surfaces (it is a useful
  pointer) but no longer inflates the aggregate score.
- **Narrowing anchors**:
  - `OVER_SPECIFIED_EXPERIENCE`: years (with or without parens / spelled-out
    forms), `monto acumulado|minimo|no menor`, `S/`, `objeto similar(es)`,
    `similar(es) al objeto`, `mismo sector`, `restrictiv`, `sin equivalente`.
  - `EXCESSIVE_DOCUMENT_REQUIREMENT`: `\d+ + (documentos|copias|...)`,
    `tres juegos`, `sobre cerrado`, `original y copia`, `obligatori`.
- **Tests**: `test_pr10_template_quote_in_otros_is_downgraded_to_low`,
  `test_pr10_quote_with_years_stays_high_severity`,
  `test_pr10_quote_with_monto_stays_strong`,
  `test_pr10_quote_in_meaningful_cluster_keeps_severity`,
  `test_pr10_excessive_doc_notarial_in_otros_with_anchor_stays_strong`,
  `test_pr10_existing_strong_flags_unchanged`.
- **Year-anchor regex expanded** to cover three forms:
  - `\b\d+\s*(?:\([^)]{1,24}\))?\s*(?:años|anios|años)` → `"8 (ocho) años"`.
  - `\(\s*\d+\s*\)\s*años|anios` → `"(08) anios"`.
  - `años|anios\s*\(\s*\d+\s*\)` → `"anios (08)"`.
- **Golden Set effect**: p52 quotes in ambiente_positive and mineria moved
  from `high` (0.65) to `low` (0.45). p206 salud_pliego stays `high` (anchor
  present). p21 notarial stays `medium` (`obligatori` anchor present).

#### Aggregate score (debug-only)

- **New module**: `agents/score.py` with `ScoringContext`, `compute_score`,
  `apply_score`.
- **Schema**: `AnalysisResult.score`, `score_breakdown`, `graph_rag` added.
  All default-zero / inactive.
- **Hard invariant**: this code **never** triggers GraphRAG. It only computes
  whether the gate *would* fire. Verified by `test_graph_rag_never_activates_without_primary_key`.
- **Blockers surfaced explicitly**: `no_accepted_flags`, `no_doctrine_anchor`,
  `no_evidence_quote`, `no_primary_key`. Each prevents activation even when
  raw score crosses 75.
- **Tests**: `test_score.py` (11 tests covering zero, medium-with-context,
  high-with-full-context-activates, low-only-below-threshold, missing-doctrine,
  missing-evidence, exact-threshold, apply_score copy, no-flags-zero, primary
  key detection, no-primary-key blocks activation).

#### Golden Set expansion

- **Added**: `tdr_ambiente_pliego_001.pdf` (181 pp SERNANP seguros
  patrimoniales). Diversifies the set away from the SIE-ANA template.
- **Result**: 0 flags emitted on this PDF, confirming the engine does not
  generate false positives on unrelated content.

#### Architecture doc honesty

- `docs/ARCHITECTURE_AGENTEPERRY.md` updated: "9 PRs cerrados" reworded to
  "9 iteraciones documentadas en working tree" because git log shows no
  commits tagged `PR #1`..`PR #9`. Claim now matches reality.

### 2026-05-17 — AuditorGraph (LangGraph) + manual review (PR #11)

- **Scope**: demo hardening + human verdict on every flag emitted by the
  LangGraph wrapper `apps/scrapers/src/agenteperry/tdr/auditor.py` which
  delegates flag detection to `document_intelligence.AgentOrchestrator`.
- **Outputs**: 4 JSON files + summary in
  `data/golden_set/outputs/auditorgraph_demo/`.
- **Human review verdict** (5 flags across 4 PDFs):
  - 3 `true_positive`: notarial p21 × 2 + similares al objeto p206.
  - 2 `weak_signal`: experiencia p52 × 2 (SIE-ANA template pointer; PR #10
    severity tuning correctly downgraded both to LOW @ 0.45).
  - 0 `false_positive`.
  - 1 `correct_negative`: SERNANP pliego (181 pp) → 0 flags, calibration
    holds outside SIE-ANA template.
- **No pattern adjustments needed.** Current MEDIUM/LOW/HIGH assignments
  align with human verdict. Score 60 (MEDIO) consistent across all flagged
  PDFs; below 75 threshold so GraphRAG gate stays correctly closed.
- **Risks logged in summary.md**: 2/5 flags are SIE-ANA template
  duplicates (golden set diversity limited), doctrine still a stub,
  detect_flags now runs 600-1900ms because it executes the full
  calibrated pipeline.

### 2026-05-17 — DoctrineIndex real corpus (PR #12)

- **Sources ingested** (verbatim public PDFs already in `data/PDF-Base/`):
  - `OCP2024-RedFlagProcurement-1.pdf` — OCP *Red flags in public
    procurement* (2024), 100 pp. 113 chunks.
    URL: <https://www.open-contracting.org/resources/red-flags-in-public-procurement/>
  - `795de142-en.pdf` — OECD *Governing with Artificial Intelligence*
    (2024), 306 pp. 344 chunks.
    URL: <https://www.oecd.org/governance/governing-with-artificial-intelligence/>
- **Artifact**: `data/doctrine/{manifest.json, chunks.jsonl,
  chunks.rich.jsonl, vectors.npy, processed/*.txt}`. 457 chunks total.
- **Per-flag chunk counts** (after keyword-disambiguation pass):
  - EXCESSIVE_DOCUMENT_REQUIREMENT: 7
  - SUBJECTIVE_EVALUATION_CRITERIA: 14
  - LOW_TRACEABILITY_OUTPUT: 28
  - OVER_SPECIFIED_EXPERIENCE: 4
  - SPECIFIC_EQUIPMENT_REQUIREMENT: 3
  - AI_NO_AUDIT_TRAIL: 78
  - OBSOLETE_PHYSICAL_FORMAT: 2
  - EXCESSIVE_CERTIFICATION_REQUIREMENT: 0 (no OCP/OECD keyword match yet)
  - UNREALISTIC_DEADLINE: 0 (idem)
- **Builder**: `scripts/build_doctrine_index.py` parses PDFs with
  PyMuPDF, applies paragraph-aware chunking, assigns flag_codes by
  keyword match (priority: first matched keyword wins; disambiguated
  so "prequalification" maps only to OVER_SPECIFIED_EXPERIENCE, not
  EXCESSIVE_DOC). Output schema: chunk_id, source_document, source_url,
  page_number, section_title, text, quote, flag_codes, metadata.
- **Loader**: `load_doctrine()` now autodetects
  `<repo>/data/doctrine/manifest.json` when no path is passed. When
  the artifact dim does not match the embedder dim, autodetect falls
  back silently to stub (preserves test embedders at dim=64/128); an
  explicit `manifest_path=...` still enforces dim match and raises.
- **Anchor lookup**: added `DoctrineIndex.first_by_flag_code(flag_code)`
  for deterministic anchor assignment. `RiskAnalysisAgent` now prefers
  this over the previous natural-language top-k fallback — fixes the
  cross-language ranking noise (Spanish question vs English doctrine
  via FakeEmbedder).
- **Golden Set after PR #12**: 5 flags, 0 errors, 0 FP in SERNANP. Same
  counts as PR #11 (real doctrine swap did NOT regress detection).
  Anchors now show real OCP page references:
  - `EXCESSIVE_DOCUMENT_REQUIREMENT` (ambiente_positive p21 + mineria p21)
    → OCP page 4 (intro; real OCP source).
  - `OVER_SPECIFIED_EXPERIENCE` (ambiente_positive p52, mineria p52,
    salud_pliego p206) → OCP page 20 (Collusion risk red flags catalog;
    real OCP source).
- **Tests added** (`tests/test_doctrine_real.py`): first_by_flag_code
  returns first match, returns None for unknown flag, preserves source +
  page, autodetect falls back on dim mismatch, explicit manifest enforces
  dim, autodetected artifact loads when dim matches.
- **Gates**: pytest **214 passed** (PR #11 was 208, +6), ruff clean,
  pyright 0 errors.

#### Known gaps (deferred)

- Anchor quality for `EXCESSIVE_DOCUMENT_REQUIREMENT` lands on OCP p4
  (intro) rather than the R007/R011 documentary-burden pages.
  Improvement: priority-based flag assignment (multi-match → pick the
  page that mentions the flag's red-flag code, not the intro).
- `EXCESSIVE_CERTIFICATION_REQUIREMENT` + `UNREALISTIC_DEADLINE` have
  0 chunks. Need OCP-specific keywords ("certification requirement
  disproportionate", "abnormally short submission deadline").
- Doctrine is English-only; Spanish TDR vocabulary requires either a
  bilingual embedder or a Spanish-doctrine corpus (OSCE Peru).

## Open questions for future calibration

These are known shortcomings noted during PR #5 scaffolding. Resolve only
when a real PDF surfaces them:

- `OBSOLETE_PHYSICAL_FORMAT` matches `\bimpres[oa]s?\b` which can fire on
  "documento original impreso del postor" (paperwork stamp, not a deliverable
  format). Likely needs proximity to "entregable" / "informe".
- `LOW_TRACEABILITY_OUTPUT` requires negation ("sin dataset", "no se requiere")
  but Spanish double-negatives ("tampoco se requiere") and conjugated forms
  ("no exigira") are not yet covered.
- `EXCESSIVE_CERTIFICATION_REQUIREMENT` fires on bare ISO mentions. Real bases
  often legitimately reference ISO standards in a non-restrictive way. Likely
  needs a "obligatori|imprescindible|sin excepcion" anchor.
- `UNREALISTIC_DEADLINE` keys on the digit count of days. Without a baseline
  for the procurement type, a 15-day deadline can be either normal or
  abusive. Future calibration should anchor against SEACE statutory minimums
  per `tipo de procedimiento`.
- `SUBJECTIVE_EVALUATION_CRITERIA` matches "juicio del comite" — sometimes a
  legitimate procedural phrase. Needs "sin rubrica" or "sin pesos" context.

## When NOT to calibrate here

If the golden set reveals a *structural* problem (citations off by pages,
doctrine anchor misattributed, banned vocab leaking), that belongs in its
own spec, not in this file.
