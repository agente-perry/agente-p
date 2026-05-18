"""Load downloads/2024/ + downloads/2025/ metadata.json → ProcedureSeace nodes."""
import logging
from datetime import datetime
import config
from gcs_utils import list_blobs, read_json
from neo4j_utils import run_batch

logger = logging.getLogger(__name__)

_CY_SEACE = """
MERGE (p:ProcedureSeace {uuid: row.uuid})
ON CREATE SET
  p.nomenclatura       = row.nomenclatura,
  p.numero             = row.numero,
  p.entidad            = row.entidad,
  p.descripcion        = row.descripcion,
  p.cuantia            = row.cuantia,
  p.fecha_hora         = datetime(row.fecha_hora),
  p.completed_targets  = row.completed_targets,
  p.linked_contract_ocid = null
"""


def _parse_fecha_hora(s: str) -> str:
    """'DD/MM/YYYY HH:MM' → ISO datetime string."""
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).isoformat() + "Z"
        except ValueError:
            continue
    return "2000-01-01T00:00:00Z"


def _parse_cuantia(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ""))
    except ValueError:
        return None


def load_seace(prefixes: list[str] | None = None) -> None:
    prefixes = prefixes or config.GCS_DOWNLOADS_PREFIXES
    rows = []

    for prefix in prefixes:
        logger.info("Scanning gs://%s/%s", config.GCS_BUCKET, prefix)
        blobs = list_blobs(config.GCS_BUCKET, prefix)
        metadata_blobs = [b for b in blobs if b.endswith("/metadata.json")]
        logger.info("  Found %d metadata.json files", len(metadata_blobs))

        for blob_path in metadata_blobs:
            try:
                meta = read_json(config.GCS_BUCKET, blob_path)
                uuid = meta.get("uuid")
                if not uuid:
                    logger.warning("No uuid in %s", blob_path)
                    continue
                rows.append({
                    "uuid": uuid,
                    "nomenclatura": meta.get("nomenclatura", ""),
                    "numero": int(meta.get("numero") or 0),
                    "entidad": meta.get("entidad", ""),
                    "descripcion": meta.get("descripcion", ""),
                    "cuantia": _parse_cuantia(meta.get("cuantia")),
                    "fecha_hora": _parse_fecha_hora(meta.get("fecha_hora", "")),
                    "completed_targets": meta.get("completed_targets", []),
                })
            except Exception as exc:
                logger.warning("Error reading %s: %s", blob_path, exc)

    run_batch(_CY_SEACE, rows)
    logger.info("SEACE done. procedures=%d", len(rows))
