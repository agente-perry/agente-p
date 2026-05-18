# PDF-Base doctrine corpus

This folder is the only allowed `data/` exception in git.

It contains public doctrine PDFs used as evaluation criteria for document intelligence:

- procurement risk patterns;
- open contracting red flags;
- international public procurement guidance;
- doctrine anchors for evidence-backed TDR flags.

These files are not case data. They are not SEACE records, TDRs, supplier evidence,
scraped outputs, embeddings, or credentials.

Rules:

- Commit only source doctrine PDFs and the manifest.
- Do not commit generated chunks, vectors, indexes, JSONL outputs, OCR outputs, or caches.
- Do not commit TDR PDFs or process documents here.
- Any new PDF must be public, citeable, and listed in `manifest.yaml`.

The retrieval/indexing layer may build derived artifacts locally or in object storage,
but those artifacts remain ignored by git.
