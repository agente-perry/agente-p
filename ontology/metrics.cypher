// ============================================================
// MÉTRICAS DERIVADAS — persistir en propiedades de nodos
// Ejecutar post-carga completa, antes de correr flags
// Proyecto: agente-perry | Versión: 1.0 | 2026-05-17
// ============================================================


// ------------------------------------------------------------
// M1 — Diversidad de clientes por supplier
// Cuántas entidades públicas distintas le compran
// ------------------------------------------------------------
MATCH (c:Company)-[:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WITH c,
     count(DISTINCT e.ruc)  AS n_clientes_distintos,
     count(k)               AS total_contratos,
     sum(k.monto)           AS monto_total_ganado
SET c.diversity_clients  = n_clientes_distintos,
    c.total_contracts    = total_contratos,
    c.total_won_pen      = monto_total_ganado;


// ------------------------------------------------------------
// M2 — Concentración máxima de proveedor por entidad-año
// % del gasto de la entidad que va al top-1 proveedor
// ------------------------------------------------------------
MATCH (e:PublicEntity)<-[:AWARDED_BY]-(k:Contract)<-[w:WON]-(c:Company)
WITH e, k.period_year AS year, c,
     sum(w.monto) AS monto_proveedor
WITH e, year,
     sum(monto_proveedor) AS gasto_total,
     max(monto_proveedor) AS gasto_top1
WITH e,
     avg(toFloat(gasto_top1) / toFloat(gasto_total)) AS concentracion_media
SET e.avg_supplier_concentration = round(concentracion_media * 100) / 100.0;


// ------------------------------------------------------------
// M3 — Cobertura geográfica del supplier
// Cuántas regiones distintas tiene contratos
// ------------------------------------------------------------
MATCH (c:Company)-[:WON]->(k:Contract)
WHERE k.region IS NOT NULL
WITH c,
     count(DISTINCT k.region) AS n_regiones
SET c.geographic_coverage = n_regiones;


// ------------------------------------------------------------
// M4 — Score de riesgo compuesto por supplier
// Suma ponderada de señales detectables
// Escala 0-100 (orientativo)
// ------------------------------------------------------------
MATCH (c:Company)
WITH c,
  // Fantasma SUNAT: +30
  CASE WHEN c.estado = 'BAJA' OR c.condicion = 'NO HABIDO' THEN 30 ELSE 0 END AS s_fantasma,
  // RUC incompleto: +20
  CASE WHEN c.ruc STARTS WITH 'hash_' OR c.is_ruc_complete = false THEN 20 ELSE 0 END AS s_ruc,
  // Monogamia (1 cliente): +15
  CASE WHEN c.diversity_clients = 1 AND c.total_contracts >= 3 THEN 15 ELSE 0 END AS s_mono,
  // Domicilio genérico: +15
  CASE WHEN EXISTS { (c)-[:LOCATED_AT]->(a:Address) WHERE a.is_generic = true } THEN 15 ELSE 0 END AS s_dom
SET c.risk_score = s_fantasma + s_ruc + s_mono + s_dom;


// ------------------------------------------------------------
// M5 — Velocidad de monetización
// Días entre fecha_inicio_actividades (SUNAT) y primer contrato ganado
// Empresa recién creada que ya gana contratos = señal F19
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)
WHERE c.fecha_inicio_actividades IS NOT NULL
WITH c, min(k.fecha) AS primer_contrato
SET c.days_to_first_contract =
    duration.between(c.fecha_inicio_actividades, primer_contrato).days;


// ------------------------------------------------------------
// M6 — Score de riesgo compuesto v2 (incluye nuevas señales SUNAT rico)
// ------------------------------------------------------------
MATCH (c:Company)
WITH c,
  CASE WHEN c.estado = 'BAJA' OR c.condicion = 'NO HABIDO'   THEN 30 ELSE 0 END AS s_fantasma_sunat,
  CASE WHEN c.ruc STARTS WITH 'hash_'                         THEN 20 ELSE 0 END AS s_ruc_faltante,
  CASE WHEN c.diversity_clients = 1
            AND c.total_contracts >= 3                         THEN 15 ELSE 0 END AS s_monogamo,
  CASE WHEN c.max_trabajadores IS NOT NULL
            AND c.max_trabajadores <= 2
            AND c.total_won_pen > 100000                       THEN 25 ELSE 0 END AS s_sin_trabajadores,
  CASE WHEN c.deuda_coactiva = true
            OR c.omisiones_tributarias = true                  THEN 20 ELSE 0 END AS s_deuda_fiscal,
  CASE WHEN c.tiene_actas_probatorias = true                   THEN 10 ELSE 0 END AS s_actas,
  CASE WHEN c.days_to_first_contract IS NOT NULL
            AND c.days_to_first_contract < 365                 THEN 20 ELSE 0 END AS s_reciente
SET c.risk_score_v2 = s_fantasma_sunat + s_ruc_faltante + s_monogamo
                    + s_sin_trabajadores + s_deuda_fiscal + s_actas + s_reciente;


// ------------------------------------------------------------
// VERIFICAR métricas calculadas
// ------------------------------------------------------------
MATCH (c:Company)
WHERE c.total_contracts IS NOT NULL
RETURN
  count(c)              AS companies_con_metricas,
  avg(c.diversity_clients)   AS avg_diversidad,
  avg(c.geographic_coverage) AS avg_regiones,
  max(c.total_won_pen)       AS max_monto_ganado,
  sum(CASE WHEN c.risk_score > 0 THEN 1 ELSE 0 END) AS con_riesgo_score;
