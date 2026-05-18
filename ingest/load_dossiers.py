"""Load scraped/results/*/dossier.json + flags.json → Dossier, RiskFlag nodes + edges."""
import logging
import config
from gcs_utils import list_blobs, read_json
from neo4j_utils import run_batch

logger = logging.getLogger(__name__)

_CY_DOSSIER = """
MERGE (d:Dossier {ocid: row.ocid})
ON CREATE SET
  d.entity_name    = row.entity_name,
  d.sector         = row.sector,
  d.procedure_code = row.procedure_code,
  d.monto          = row.monto,
  d.total_score    = row.total_score,
  d.risk_level     = row.risk_level,
  d.total_flags    = row.total_flags,
  d.total_pages    = row.total_pages,
  d.coverage_pct   = row.coverage_pct,
  d.generated_at   = datetime(row.generated_at)
"""

_CY_ANALYZED_BY = """
MATCH (d:Dossier {ocid: row.ocid})
MATCH (ct:Contract) WHERE ct.ocid = row.ocid
MERGE (ct)-[:ANALYZED_BY]->(d)
"""

_CY_RISKFLAG = """
MERGE (f:RiskFlag {flag_id: row.flag_id})
ON CREATE SET
  f.flag_code          = row.flag_code,
  f.flag_name          = row.flag_name,
  f.severity           = row.severity,
  f.score_contribution = row.score_contribution,
  f.page_number        = row.page_number,
  f.evidence_quote     = row.evidence_quote,
  f.rule_id            = row.rule_id,
  f.detection_method   = row.detection_method
"""

_CY_HAS_FLAG = """
MATCH (d:Dossier {ocid: row.ocid}), (f:RiskFlag {flag_id: row.flag_id})
MERGE (d)-[:HAS_FLAG]->(f)
"""


def _find_dossier_dirs(bucket: str, prefix: str) -> list[str]:
    """Return unique directory prefixes that contain a dossier.json."""
    blobs = list_blobs(bucket, prefix)
    dirs = set()
    for b in blobs:
        if b.endswith("/dossier.json"):
            dirs.add(b[: -len("dossier.json")])
    return sorted(dirs)


def load_dossiers(results_prefix: str | None = None) -> None:
    prefix = results_prefix or config.GCS_RESULTS_PREFIX
    logger.info("Loading dossiers from gs://%s/%s", config.GCS_BUCKET, prefix)

    dirs = _find_dossier_dirs(config.GCS_BUCKET, prefix)
    logger.info("Found %d dossier directories", len(dirs))

    dossier_rows, flag_rows, rel_rows, analyzed_rows = [], [], [], []

    for d in dirs:
        try:
            dos = read_json(config.GCS_BUCKET, d + "dossier.json")
            doc = dos.get("document") or dos  # some versions nest under "document"
            rs = dos.get("risk_summary", {})
            ocid = doc.get("ocid") or dos.get("ocid")
            if not ocid:
                logger.warning("No ocid in %s, skipping", d)
                continue

            generated_at = dos.get("generated_at", "2000-01-01T00:00:00")
            # normalize: some timestamps lack timezone suffix
            if "T" in generated_at and "+" not in generated_at and "Z" not in generated_at:
                generated_at += "Z"

            dossier_rows.append({
                "ocid": ocid,
                "entity_name": doc.get("entity_name", ""),
                "sector": doc.get("sector", ""),
                "procedure_code": doc.get("procedure_code", ""),
                "monto": doc.get("monto"),
                "total_score": rs.get("total_score", 0),
                "risk_level": rs.get("risk_level", "BAJO"),
                "total_flags": rs.get("total_flags", 0),
                "total_pages": doc.get("total_pages", 0),
                "coverage_pct": doc.get("coverage_pct", 0.0),
                "generated_at": generated_at,
            })
            analyzed_rows.append({"ocid": ocid})

        except Exception as exc:
            logger.warning("Error reading dossier %s: %s", d, exc)
            continue

        try:
            flags_data = read_json(config.GCS_BUCKET, d + "flags.json")
            flags = flags_data.get("flags", [])
            for f in flags:
                flag_id = f"{ocid}_{f.get('flag_code', 'UNK')}_p{f.get('page_number', 0)}"
                flag_rows.append({
                    "flag_id": flag_id,
                    "flag_code": f.get("flag_code", ""),
                    "flag_name": f.get("flag_name", ""),
                    "severity": f.get("severity", "LOW"),
                    "score_contribution": f.get("score_contribution", 0),
                    "page_number": f.get("page_number", 0),
                    "evidence_quote": f.get("evidence_quote", ""),
                    "rule_id": f.get("rule_id", ""),
                    "detection_method": f.get("detection_method", "rule"),
                })
                rel_rows.append({"ocid": ocid, "flag_id": flag_id})
        except Exception as exc:
            logger.warning("Error reading flags %s: %s", d, exc)

    run_batch(_CY_DOSSIER, dossier_rows)
    run_batch(_CY_ANALYZED_BY, analyzed_rows)
    run_batch(_CY_RISKFLAG, flag_rows)
    run_batch(_CY_HAS_FLAG, rel_rows)

    logger.info("Dossiers done. dossiers=%d flags=%d", len(dossier_rows), len(flag_rows))
