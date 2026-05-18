"""Load scraped/ocds/records.jsonl → Company, PublicEntity, Contract, Tender nodes + edges."""
import hashlib
import logging
from tqdm import tqdm
import config
import checkpoint
from gcs_utils import stream_jsonl
from neo4j_utils import run_batch

logger = logging.getLogger(__name__)

# ---------- Cypher statements (used with UNWIND $rows AS row) ----------

_CY_COMPANY = """
MERGE (c:Company {ruc: row.ruc})
ON CREATE SET
  c.name = row.name,
  c.is_ruc_complete = row.is_ruc_complete,
  c.estado = null, c.condicion = null,
  c.source = ['ocds_peru']
ON MATCH SET
  c.name = CASE WHEN c.name IS NULL THEN row.name ELSE c.name END
"""

_CY_ENTITY = """
MERGE (e:PublicEntity {ruc: row.ruc})
ON CREATE SET e.name = row.name, e.region = row.region
"""

_CY_CONTRACT = """
MERGE (ct:Contract {external_id: row.external_id})
ON CREATE SET
  ct.ocid           = row.ocid,
  ct.tender_id      = row.tender_id,
  ct.award_id       = row.award_id,
  ct.monto          = row.monto,
  ct.fecha          = date(row.fecha),
  ct.period_year    = row.period_year,
  ct.procedure_type = row.procedure_type,
  ct.region         = row.region,
  ct.evidence_quote = row.evidence_quote
"""

_CY_TENDER = """
MERGE (t:Tender {tender_id: row.tender_id})
ON CREATE SET
  t.ocid           = row.ocid,
  t.procedure_type = row.procedure_type,
  t.fecha          = date(row.fecha),
  t.monto          = row.monto,
  t.region         = row.region
"""

_CY_WON = """
MATCH (c:Company {ruc: row.supplier_ruc}), (ct:Contract {external_id: row.external_id})
MERGE (c)-[w:WON]->(ct)
ON CREATE SET
  w.monto = row.monto, w.fecha = date(row.fecha),
  w.procedure_type = row.procedure_type, w.region = row.region
"""

_CY_AWARDED_BY = """
MATCH (ct:Contract {external_id: row.external_id}), (e:PublicEntity {ruc: row.entity_ruc})
MERGE (ct)-[:AWARDED_BY]->(e)
"""

_CY_UNDER_TENDER = """
MATCH (ct:Contract {external_id: row.external_id}), (t:Tender {tender_id: row.tender_id})
MERGE (ct)-[:UNDER_TENDER]->(t)
"""


def _canonical_ruc(raw_ruc: str | None, name: str) -> str:
    if raw_ruc and len(raw_ruc) == 11 and raw_ruc.isdigit():
        return raw_ruc
    return "hash_" + hashlib.md5((name or "").lower().encode()).hexdigest()[:16]


def load_ocds(blob_path: str | None = None) -> None:
    path = blob_path or config.GCS_OCDS_PATH
    logger.info("Loading OCDS from gs://%s/%s", config.GCS_BUCKET, path)

    companies, entities, contracts, tenders = [], [], [], []
    won_edges, awarded_edges, under_pairs = [], [], []

    def _flush():
        run_batch(_CY_COMPANY, companies)
        run_batch(_CY_ENTITY, entities)
        run_batch(_CY_CONTRACT, contracts)
        run_batch(_CY_TENDER, tenders)
        run_batch(_CY_WON, won_edges)
        run_batch(_CY_AWARDED_BY, awarded_edges)
        for lst in [companies, entities, contracts, tenders, won_edges, awarded_edges]:
            lst.clear()

    resume_from = checkpoint.load("ocds")
    if resume_from >= 0:
        logger.info("Resuming from checkpoint: skipping first %d records", resume_from + 1)

    errors = 0
    n_contracts = n_tenders = 0

    for i, rec in enumerate(tqdm(stream_jsonl(config.GCS_BUCKET, path), desc="OCDS", total=72399)):
        if i <= resume_from:
            continue

        try:
            pd = rec.get("parsed_data") or {}
            rt = rec.get("record_type")
            entity_ruc = rec["entity_ruc"]
            fecha = rec.get("fecha") or "2000-01-01"
            region = rec.get("region", "")
            pt = pd.get("procedure_type", "")
            ocid = pd.get("ocid", "")
            tid = pd.get("tender_id", "")

            entities.append({"ruc": entity_ruc, "name": rec.get("entity_name", ""), "region": region})

            if rt == "contract":
                raw_ruc = rec.get("supplier_ruc")
                sname = rec.get("supplier_name") or ""
                canonical = _canonical_ruc(raw_ruc, sname)
                eid = rec["external_id"]

                companies.append({
                    "ruc": canonical,
                    "name": sname,
                    "is_ruc_complete": raw_ruc is not None and len(raw_ruc) == 11,
                })
                contracts.append({
                    "external_id": eid,
                    "ocid": ocid,
                    "tender_id": tid,
                    "award_id": pd.get("award_id"),
                    "monto": rec.get("monto"),
                    "fecha": fecha,
                    "period_year": rec.get("period_year"),
                    "procedure_type": pt,
                    "region": region,
                    "evidence_quote": rec.get("evidence_quote"),
                })
                won_edges.append({
                    "supplier_ruc": canonical,
                    "external_id": eid,
                    "monto": rec.get("monto"),
                    "fecha": fecha,
                    "procedure_type": pt,
                    "region": region,
                })
                awarded_edges.append({"external_id": eid, "entity_ruc": entity_ruc})
                if tid:
                    under_pairs.append({"external_id": eid, "tender_id": tid})
                n_contracts += 1

            elif rt == "procedure" and tid:
                tenders.append({
                    "tender_id": tid,
                    "ocid": ocid,
                    "procedure_type": pt,
                    "fecha": fecha,
                    "monto": rec.get("monto"),
                    "region": region,
                })
                n_tenders += 1

        except Exception as exc:
            errors += 1
            if errors <= 10:
                logger.warning("Skipping record %d: %s", i, exc)

        if (i + 1) % config.BATCH_SIZE == 0:
            _flush()
            checkpoint.save("ocds", i)
            batch_num = (i + 1) // config.BATCH_SIZE
            logger.info(
                "Batch %d flushed — records=%d | contracts=%d | tenders=%d | errors=%d",
                batch_num, i + 1, n_contracts, n_tenders, errors,
            )

    _flush()
    logger.info("Stream done — contracts=%d tenders=%d errors=%d", n_contracts, n_tenders, errors)

    # UNDER_TENDER post-pass (needs both Tender + Contract to exist)
    total_under = len(under_pairs)
    logger.info("Creating %d UNDER_TENDER edges...", total_under)
    for start in range(0, total_under, config.BATCH_SIZE):
        run_batch(_CY_UNDER_TENDER, under_pairs[start : start + config.BATCH_SIZE])
        logger.info("  UNDER_TENDER %d/%d", min(start + config.BATCH_SIZE, total_under), total_under)

    checkpoint.clear("ocds")
    logger.info("OCDS done. contracts=%d tenders=%d errors=%d", n_contracts, n_tenders, errors)
