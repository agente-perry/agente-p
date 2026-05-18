# CONSTITUTION — AgentePerry TDR Scanner

Reglas inviolables del proyecto. Toda decision, codigo y comunicacion obedece este documento.

> Si tu trabajo viola la constitucion, no se mergea. Sin excepciones.

Version: 2.0.0 — 2026-05-14
Firmantes: equipo AgentePerry TDR Scanner

---

## I. Principio rector

No acusamos corrupcion. Detectamos senales de riesgo con evidencia publica.

- Prohibido: "robo", "corrupto", "mafioso", "culpable", "delincuente", "ladron", "complice", "criminal", "delito".
- Obligatorio: "presenta senales de riesgo", "merece revision", "requiere explicacion", "patron atipico".
- Toda evidencia debe incluir cita textual, pagina y fuente cuando exista.

---

## II. Spec-Driven Development

Ninguna linea de codigo entra a `main` sin un spec activo.

Flujo obligatorio:

```text
Idea -> specs/active/SPEC-NNNN-slug/ -> branch <tipo>/SPEC-NNNN-slug -> commit con (SPEC-NNNN) -> PR -> review
```

Excepciones:

- Typo menor.
- Hotfix de CI/build.
- Documentacion interna que no cambie alcance.

---

## III. Foco MVP

El MVP activo es AgentePerry TDR Scanner.

Implementar solo:

- TDR ingestion.
- PDF parsing.
- Text cleaning.
- Chunking.
- Embeddings para busqueda.
- Rule-based TDR flags.
- Evidence-backed dossier API.

No implementar ahora ONPE, JNE, SUNARP, Graphiti, Neo4j, ConflictMap full, Civic Amplifier full, mapa nacional ni SMS.

---

## IV. Calidad minima

- Python: `uv run --extra dev pytest`, `uv run --extra dev ruff check src tests`, `uv run --extra dev pyright`.
- SQL: migraciones secuenciales en `packages/db/migrations/`.
- Tests para parsing, chunking y flags.
- RLS habilitado en tablas publicas.
- Sin secretos ni data real commiteada.

---

## V. Seguridad y datos

- `.env` nunca se commitea.
- PDFs reales, CSVs grandes, JSONL, ZIPs y dumps procesados no se commitean.
- No DNIs completos, telefonos o direcciones personales en UI publica.
- Service role keys solo en CI secrets o `.env` local.

---

## VI. Comunicacion

- Espanol peruano neutro en UI publica.
- Ingles permitido en codigo.
- Sin emojis en commits/PRs.
- Disclaimer obligatorio en dossiers: el analisis identifica senales de riesgo y requiere revision humana.

---

## VII. Honor

> Comparte evidencia, no rumores. Pide respuestas, no linchamientos.
