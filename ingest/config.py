import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI      = os.environ["NEO4J_URI"]
NEO4J_USER     = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

GCS_BUCKET            = os.environ.get("GCS_BUCKET", "agente-perry-data-prod")
GCS_OCDS_PATH         = os.environ.get("GCS_OCDS_PATH", "scraped/ocds/records.jsonl")
GCS_SUNAT_PATH        = os.environ.get("GCS_SUNAT_PATH", "scraped/collectors/sunat_padron/rucs.jsonl")
GCS_RESULTS_PREFIX    = os.environ.get("GCS_RESULTS_PREFIX", "scraped/results/")
GCS_DOWNLOADS_PREFIXES = [
    p.strip()
    for p in os.environ.get("GCS_DOWNLOADS_PREFIXES", "downloads/2024/,downloads/2025/").split(",")
]

BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "500"))
