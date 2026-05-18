"""Human-readable index of the TDR subsystem."""

TDR_DIRECTORIES = [
    ("agenteperry/tdr/ingestion.py", "Manual CSV manifest validation and checksums"),
    ("agenteperry/tdr/parsing.py", "PDF page text extraction with PyMuPDF"),
    ("agenteperry/tdr/chunking.py", "Chunk creation with page provenance"),
    ("agenteperry/tdr/embeddings.py", "Provider-ready embedding payloads for search"),
    ("agenteperry/tdr/flags.py", "Rule-based signals with evidence quotes"),
    ("agenteperry/tdr/search.py", "Local smoke-search before pgvector search"),
    ("agenteperry/tdr/downloader.py", "Controlled downloader from OCDS tender documents"),
    ("agenteperry/tdr/dossier.py", "Legal-safe dossier generator (JSON + Markdown)"),
]

TDR_COMMANDS = [
    ("agenteperry tdr index", "Show MVP structure, commands and rules"),
    ("agenteperry tdr load-manual <metadata.csv>", "Validate manual TDR metadata"),
    ("agenteperry tdr parse <file.pdf>", "Extract text by page to JSON"),
    ("agenteperry tdr chunk <pages.json>", "Create searchable chunks"),
    ("agenteperry tdr embed-inputs <chunks.json>", "Prepare embedding payloads"),
    ("agenteperry tdr flags <pages.json>", "Detect rule-based flags with evidence"),
    ("agenteperry tdr smoke-search <chunks.json> <query>", "Lexical local smoke-search"),
    ("agenteperry tdr download --input <file.jsonl> --sector salud", "Download prioritized TDR/Bases docs"),
    ("agenteperry tdr audit-pdfs --base data/scraped/tdrs", "Classify downloaded PDFs by text-layer usability"),
    (
        "agenteperry tdr analyze <file.pdf> --sector salud --ocid ... --entity ...",
        "Full pipeline: verify → parse → chunk → flags → dossier (no DB required)",
    ),
]

TDR_RULES = [
    ("TDR-R001", "EXCESSIVE_DOCUMENT_REQUIREMENT"),
    ("TDR-R002", "OBSOLETE_PHYSICAL_FORMAT"),
    ("TDR-R003", "SPECIFIC_EQUIPMENT_REQUIREMENT"),
    ("TDR-R004", "EXCESSIVE_CERTIFICATION_REQUIREMENT"),
    ("TDR-R005", "LOW_TRACEABILITY_OUTPUT"),
    ("TDR-R006", "SUBJECTIVE_EVALUATION_CRITERIA"),
]
