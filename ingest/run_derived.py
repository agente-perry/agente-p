"""
Post-load step: derived relations + computed metrics.
Run after all loaders have completed.
"""
import logging
from neo4j_utils import run_query

logger = logging.getLogger(__name__)


def run_same_address():
    logger.info("Computing SAME_ADDRESS_AS...")
    result = run_query("""
        MATCH (c1:Company)-[:LOCATED_AT]->(a:Address)<-[:LOCATED_AT]-(c2:Company)
        WHERE c1.ruc < c2.ruc AND a.is_generic = false
        MERGE (c1)-[:SAME_ADDRESS_AS {via_address_hash: a.address_hash}]->(c2)
        RETURN count(*) AS created
    """)
    logger.info("  SAME_ADDRESS_AS: %s", result)


def run_same_repr():
    logger.info("Computing SAME_REPR_AS...")
    result = run_query("""
        MATCH (p:Person)-[:REPRESENTS]->(c1:Company)
        MATCH (p)-[:REPRESENTS]->(c2:Company)
        WHERE c1.ruc < c2.ruc
        MERGE (c1)-[:SAME_REPR_AS {via_person_doc_id: p.doc_id}]->(c2)
        RETURN count(*) AS created
    """)
    logger.info("  SAME_REPR_AS: %s", result)


def run_metrics():
    logger.info("Computing M1 — client diversity...")
    run_query("""
        MATCH (c:Company)-[:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
        WITH c,
             count(DISTINCT e.ruc) AS n_clientes,
             count(k)              AS total_contratos,
             sum(k.monto)          AS monto_total
        SET c.diversity_clients = n_clientes,
            c.total_contracts   = total_contratos,
            c.total_won_pen     = monto_total
    """)

    logger.info("Computing M2 — supplier concentration per entity-year...")
    run_query("""
        MATCH (e:PublicEntity)<-[:AWARDED_BY]-(k:Contract)<-[w:WON]-(c:Company)
        WITH e, k.period_year AS year, c, sum(w.monto) AS monto_proveedor
        WITH e, year, sum(monto_proveedor) AS gasto_total, max(monto_proveedor) AS gasto_top1
        WITH e, avg(toFloat(gasto_top1) / toFloat(gasto_total)) AS concentracion_media
        SET e.avg_supplier_concentration = round(concentracion_media * 100) / 100.0
    """)

    logger.info("Computing M3 — geographic coverage...")
    run_query("""
        MATCH (c:Company)-[:WON]->(k:Contract)
        WHERE k.region IS NOT NULL
        WITH c, count(DISTINCT k.region) AS n_regiones
        SET c.geographic_coverage = n_regiones
    """)

    logger.info("Computing M5 — days to first contract...")
    run_query("""
        MATCH (c:Company)-[:WON]->(k:Contract)
        WHERE c.fecha_inicio_actividades IS NOT NULL
        WITH c, min(k.fecha) AS primer_contrato
        SET c.days_to_first_contract =
            duration.between(c.fecha_inicio_actividades, primer_contrato).days
    """)

    logger.info("Computing M6 — risk_score_v2...")
    run_query("""
        MATCH (c:Company)
        WITH c,
          CASE WHEN c.estado = 'BAJA' OR c.condicion = 'NO HABIDO' THEN 30 ELSE 0 END AS s_fantasma,
          CASE WHEN c.ruc STARTS WITH 'hash_'                       THEN 20 ELSE 0 END AS s_ruc,
          CASE WHEN c.diversity_clients = 1
                    AND c.total_contracts >= 3                       THEN 15 ELSE 0 END AS s_mono,
          CASE WHEN c.max_trabajadores IS NOT NULL
                    AND c.max_trabajadores <= 2
                    AND c.total_won_pen > 100000                     THEN 25 ELSE 0 END AS s_sin_trab,
          CASE WHEN c.deuda_coactiva = true
                    OR c.omisiones_tributarias = true                THEN 20 ELSE 0 END AS s_deuda,
          CASE WHEN c.tiene_actas_probatorias = true                 THEN 10 ELSE 0 END AS s_actas,
          CASE WHEN c.days_to_first_contract IS NOT NULL
                    AND c.days_to_first_contract < 365               THEN 20 ELSE 0 END AS s_reciente
        SET c.risk_score_v2 = s_fantasma + s_ruc + s_mono + s_sin_trab + s_deuda + s_actas + s_reciente
    """)

    logger.info("Metrics done.")


def run_all_derived():
    run_same_address()
    run_same_repr()
    run_metrics()
    logger.info("All derived relations and metrics complete.")
