"""Load SUNAT e-consultaruc JSONL → enrich Company + Person nodes + REPRESENTS edges + Address."""
import hashlib
import logging
from datetime import datetime
from tqdm import tqdm
import config
import checkpoint
from gcs_utils import stream_jsonl
from neo4j_utils import run_batch

logger = logging.getLogger(__name__)


# ---------- Helpers ----------

def _iso_date(peru_date: str) -> str | None:
    """'DD/MM/YYYY' → 'YYYY-MM-DD'. Returns None on empty/invalid."""
    if not peru_date or peru_date.strip() in ("", "Sin información"):
        return None
    try:
        return datetime.strptime(peru_date.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_ciiu(actividades: list) -> tuple[str | None, str | None]:
    """Extract (ciiu_code, description) from first 'Principal - XXXX - DESC' entry.
    Skips entries where CIIU code is not exactly 4 digits (garbage concatenated by scraper)."""
    for act in (actividades or []):
        parts = [p.strip() for p in act.split(" - ")]
        if len(parts) >= 3 and "principal" in parts[0].lower() and parts[1].isdigit() and len(parts[1]) == 4:
            return parts[1], parts[2]
    return None, None


def _parse_trabajadores(lista: list) -> tuple[int | None, int | None]:
    """Return (max, min) worker counts from monthly list."""
    nums = []
    for item in (lista or []):
        if not isinstance(item, dict):
            continue
        try:
            v = int(item.get("N° de Trabajadores") or 0)
            nums.append(v)
        except (ValueError, TypeError):
            pass
    return (max(nums), min(nums)) if nums else (None, None)


def _is_truthy(val) -> bool:
    """True if val indicates something actionable (not empty / 'Sin información')."""
    if val is None:
        return False
    if isinstance(val, list):
        # actas_probatorias is a list of dicts; truthy if any entry has real data
        return any(
            isinstance(item, dict) and
            "No existe información" not in (item.get("Nº Acta Probatoria") or "")
            for item in val
        )
    return bool(val) and str(val).strip() not in ("Sin información", "")


def _address_hash(domicilio: str) -> str:
    return hashlib.md5((domicilio or "").encode()).hexdigest()


# ---------- Cypher ----------

_CY_COMPANY_ENRICH = """
MERGE (c:Company {ruc: row.ruc})
ON CREATE SET
  c.name              = row.name,
  c.is_ruc_complete   = true,
  c.source            = ['sunat_econsulta']
ON MATCH SET
  c.nombre_comercial         = row.nombre_comercial,
  c.tipo_contribuyente       = row.tipo_contribuyente,
  c.estado                   = row.estado,
  c.condicion                = row.condicion,
  c.domicilio_fiscal         = row.domicilio_fiscal,
  c.fecha_inscripcion        = CASE WHEN row.fecha_inscripcion IS NOT NULL THEN date(row.fecha_inscripcion) ELSE null END,
  c.fecha_inicio_actividades = CASE WHEN row.fecha_inicio IS NOT NULL THEN date(row.fecha_inicio) ELSE null END,
  c.ciiu_principal           = row.ciiu_principal,
  c.actividad_principal      = row.actividad_principal,
  c.max_trabajadores         = row.max_trabajadores,
  c.min_trabajadores         = row.min_trabajadores,
  c.deuda_coactiva           = row.deuda_coactiva,
  c.omisiones_tributarias    = row.omisiones_tributarias,
  c.tiene_actas_probatorias  = row.tiene_actas,
  c.source                   = CASE WHEN 'sunat_econsulta' IN c.source THEN c.source
                                    ELSE c.source + ['sunat_econsulta'] END
"""

_CY_ADDRESS = """
MERGE (a:Address {address_hash: row.address_hash})
ON CREATE SET
  a.domicilio_fiscal = row.domicilio_fiscal,
  a.is_generic       = row.is_generic
"""

_CY_LOCATED_AT = """
MATCH (c:Company {ruc: row.ruc}), (a:Address {address_hash: row.address_hash})
MERGE (c)-[:LOCATED_AT]->(a)
"""

_CY_PERSON = """
MERGE (p:Person {doc_id: row.doc_id})
ON CREATE SET p.doc_type = row.doc_type, p.name = row.name
"""

_CY_REPRESENTS = """
MATCH (p:Person {doc_id: row.doc_id}), (c:Company {ruc: row.ruc})
MERGE (p)-[r:REPRESENTS]->(c)
ON CREATE SET
  r.cargo       = row.cargo,
  r.fecha_desde = CASE WHEN row.fecha_desde IS NOT NULL THEN date(row.fecha_desde) ELSE null END
"""


def load_sunat(blob_path: str | None = None) -> None:
    path = blob_path or config.GCS_SUNAT_PATH
    logger.info("Loading SUNAT from gs://%s/%s", config.GCS_BUCKET, path)

    companies, addresses, located_at_pairs = [], [], []
    persons, represents_edges = [], []

    def _flush():
        run_batch(_CY_COMPANY_ENRICH, companies)
        run_batch(_CY_ADDRESS, addresses)
        run_batch(_CY_LOCATED_AT, located_at_pairs)
        run_batch(_CY_PERSON, persons)
        run_batch(_CY_REPRESENTS, represents_edges)
        for lst in [companies, addresses, located_at_pairs, persons, represents_edges]:
            lst.clear()

    resume_from = checkpoint.load("sunat")
    if resume_from >= 0:
        logger.info("Resuming from checkpoint: skipping first %d records", resume_from + 1)

    errors = 0
    count = 0
    n_persons = 0
    n_addresses = 0
    for i, rec in enumerate(tqdm(stream_jsonl(config.GCS_BUCKET, path), desc="SUNAT")):
        if i <= resume_from:
            continue

        try:
            ruc = rec.get("numero_ruc", "").strip()
            if not ruc:
                continue

            domicilio = (rec.get("domicilio_fiscal") or "").strip()
            ciiu, actividad = _parse_ciiu(rec.get("actividades_economicas"))
            max_t, min_t = _parse_trabajadores(rec.get("cantidad_trabajadores"))

            companies.append({
                "ruc": ruc,
                "name": rec.get("razon_social", ""),
                "nombre_comercial": rec.get("nombre_comercial"),
                "tipo_contribuyente": rec.get("tipo_contribuyente"),
                "estado": rec.get("estado"),
                "condicion": rec.get("condicion"),
                "domicilio_fiscal": domicilio,
                "fecha_inscripcion": _iso_date(rec.get("fecha_inscripcion")),
                "fecha_inicio": _iso_date(rec.get("fecha_inicio_actividades")),
                "ciiu_principal": ciiu,
                "actividad_principal": actividad,
                "max_trabajadores": max_t,
                "min_trabajadores": min_t,
                "deuda_coactiva": _is_truthy(rec.get("deuda_coactiva")),
                "omisiones_tributarias": _is_truthy(rec.get("omisiones_tributarias")),
                "tiene_actas": _is_truthy(rec.get("actas_probatorias")),
            })

            if domicilio:
                ahash = _address_hash(domicilio)
                addresses.append({
                    "address_hash": ahash,
                    "domicilio_fiscal": domicilio,
                    "is_generic": "S/N" in domicilio.upper() or not domicilio.strip(),
                })
                located_at_pairs.append({"ruc": ruc, "address_hash": ahash})
                n_addresses += 1

            for rep in (rec.get("representantes_legales") or []):
                if not isinstance(rep, dict):
                    continue
                doc_id = (rep.get("Nro. Documento") or "").strip()
                if not doc_id:
                    continue
                persons.append({
                    "doc_id": doc_id,
                    "doc_type": rep.get("Documento", ""),
                    "name": rep.get("Nombre", ""),
                })
                represents_edges.append({
                    "doc_id": doc_id,
                    "ruc": ruc,
                    "cargo": rep.get("Cargo"),
                    "fecha_desde": _iso_date(rep.get("Fecha Desde") or rep.get("Desde")),
                })
                n_persons += 1

        except Exception as exc:
            errors += 1
            if errors <= 10:
                logger.warning("Skipping record %d: %s", i, exc)

        count += 1
        if count % config.BATCH_SIZE == 0:
            _flush()
            checkpoint.save("sunat", i)
            logger.info(
                "Batch %d flushed — companies=%d | persons=%d | addresses=%d | errors=%d",
                count // config.BATCH_SIZE, count, n_persons, n_addresses, errors,
            )

    _flush()
    checkpoint.clear("sunat")
    logger.info(
        "SUNAT done. companies=%d persons=%d addresses=%d errors=%d",
        count, n_persons, n_addresses, errors,
    )
