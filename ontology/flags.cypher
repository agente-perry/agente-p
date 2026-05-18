// ============================================================
// FLAGS DE CORRUPCIÓN — 19 queries Cypher
// Proyecto: agente-perry | Versión: 2.0 | 2026-05-17
//
// Grupo A  (F1-F4):   OCDS × SUNAT (estado, condicion, domicilio)
// Grupo B  (F5-F12):  Solo OCDS — cobertura alta
// Grupo C  (F13-F14): Dossiers TDR
// Grupo D  (F15-F19): SUNAT rico (trabajadores, CIIU, deuda, repr legal)
// ============================================================


// ============================================================
// GRUPO A — OCDS × SUNAT (cobertura baja hasta tener padrón completo)
// ============================================================

// ------------------------------------------------------------
// F1 — Empresa fantasma activa
// Empresa con estado=BAJA o condicion=NO HABIDO que ganó contratos
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE c.estado = 'BAJA' OR c.condicion = 'NO HABIDO'
WITH c, e,
     count(k)         AS n_contratos,
     sum(w.monto)     AS monto_total,
     min(w.fecha)     AS primer_contrato,
     max(w.fecha)     AS ultimo_contrato,
     collect(DISTINCT e.name)[..5] AS entidades_compradoras
RETURN
  c.ruc              AS ruc,
  c.name             AS empresa,
  c.estado           AS estado_sunat,
  c.condicion        AS condicion_sunat,
  n_contratos,
  monto_total,
  primer_contrato,
  ultimo_contrato,
  entidades_compradoras
ORDER BY monto_total DESC
LIMIT 100;


// ------------------------------------------------------------
// F2 — Testaferros por domicilio compartido
// ≥2 empresas en mismo domicilio ganando del mismo comprador
// ------------------------------------------------------------
MATCH (c1:Company)-[:LOCATED_AT]->(a:Address)<-[:LOCATED_AT]-(c2:Company)
WHERE c1.ruc < c2.ruc AND a.is_generic = false
MATCH (c1)-[w1:WON]->(k1:Contract)-[:AWARDED_BY]->(e:PublicEntity)
      <-[:AWARDED_BY]-(k2:Contract)<-[w2:WON]-(c2)
WITH a, e,
     collect(DISTINCT c1.ruc + ' — ' + c1.name) +
     collect(DISTINCT c2.ruc + ' — ' + c2.name) AS cluster_empresas,
     sum(w1.monto) + sum(w2.monto)               AS monto_cluster
RETURN
  a.domicilio_fiscal   AS domicilio,
  a.ubigeo             AS ubigeo,
  e.name               AS comprador_comun,
  cluster_empresas,
  monto_cluster
ORDER BY monto_cluster DESC
LIMIT 50;


// ------------------------------------------------------------
// F3 — Domicilio fachada / sin número
// Empresas con domicilio S/N o incompleto
// ------------------------------------------------------------
MATCH (c:Company)-[:LOCATED_AT]->(a:Address)
WHERE a.is_generic = true
OPTIONAL MATCH (c)-[w:WON]->(k:Contract)
WITH c, a,
     count(k)     AS n_contratos,
     sum(w.monto) AS monto_total
WHERE n_contratos > 0
RETURN
  c.ruc              AS ruc,
  c.name             AS empresa,
  c.estado           AS estado_sunat,
  a.domicilio_fiscal AS domicilio,
  n_contratos,
  monto_total
ORDER BY monto_total DESC
LIMIT 100;


// ------------------------------------------------------------
// F4 — Geo-mismatch (empresa en región distinta al contrato)
// ubigeo[0:2] es código de región SUNAT; region en contrato es string
// Mapa ubigeo → region: 15=Lima, 04=Arequipa, 07=Cusco, etc.
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)
WHERE c.ubigeo IS NOT NULL
  AND c.ubigeo <> ''
  AND k.region IS NOT NULL
WITH c, k, w,
     // Lima = ubigeo 15xx, Arequipa = 04xx, Cusco = 08xx
     CASE substring(c.ubigeo, 0, 2)
       WHEN '15' THEN 'LIMA'
       WHEN '04' THEN 'AREQUIPA'
       WHEN '08' THEN 'CUSCO'
       WHEN '17' THEN 'LORETO'
       WHEN '07' THEN 'CALLAO'
       WHEN '13' THEN 'LA LIBERTAD'
       WHEN '14' THEN 'LAMBAYEQUE'
       WHEN '25' THEN 'UCAYALI'
       WHEN '21' THEN 'PUNO'
       ELSE 'OTRA'
     END AS region_empresa
WHERE region_empresa <> 'OTRA'
  AND toUpper(k.region) <> region_empresa
  AND k.monto > 100000  // solo contratos > S/ 100k
WITH c,
     count(k)         AS n_contratos_lejanos,
     sum(w.monto)     AS monto_lejano,
     collect(DISTINCT k.region)[..5] AS regiones_contrato,
     region_empresa
RETURN
  c.ruc              AS ruc,
  c.name             AS empresa,
  region_empresa     AS region_domicilio,
  regiones_contrato,
  n_contratos_lejanos,
  monto_lejano
ORDER BY monto_lejano DESC
LIMIT 100;


// ============================================================
// GRUPO B — SOLO OCDS (alta cobertura)
// ============================================================

// ------------------------------------------------------------
// F5 — Cliente cautivo
// Supplier con ≥5 contratos donde ≥70% de su gasto viene de 1 entidad
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WITH c, e,
     count(k)     AS n_con_entidad,
     sum(w.monto) AS monto_con_entidad
WITH c,
     collect({entidad: e.name, ruc: e.ruc, n: n_con_entidad, monto: monto_con_entidad}) AS breakdown,
     sum(n_con_entidad)     AS total_contratos,
     sum(monto_con_entidad) AS monto_total
WHERE total_contratos >= 5
WITH c, breakdown, total_contratos, monto_total,
     reduce(top = {monto: 0, entidad: ''}, x IN breakdown |
       CASE WHEN x.monto > top.monto THEN x ELSE top END
     ) AS top_cliente
WITH c, total_contratos, monto_total, top_cliente,
     toFloat(top_cliente.monto) / toFloat(monto_total) AS concentracion
WHERE concentracion >= 0.70
RETURN
  c.ruc                    AS ruc_supplier,
  c.name                   AS supplier,
  top_cliente.entidad      AS cliente_principal,
  total_contratos,
  round(monto_total)       AS monto_total_pen,
  round(concentracion*100) AS pct_concentrado,
  c.estado                 AS estado_sunat
ORDER BY monto_total DESC
LIMIT 50;


// ------------------------------------------------------------
// F6 — Entidad capturada
// Entidad pública donde top-1 proveedor > 40% del gasto anual
// ------------------------------------------------------------
MATCH (e:PublicEntity)<-[:AWARDED_BY]-(k:Contract)<-[w:WON]-(c:Company)
WITH e, k.period_year AS year, c,
     sum(w.monto) AS monto_proveedor
WITH e, year,
     collect({company: c.name, ruc: c.ruc, monto: monto_proveedor}) AS proveedores,
     sum(monto_proveedor) AS monto_total_entidad
WITH e, year, proveedores, monto_total_entidad,
     reduce(top = {monto: 0, company: ''}, x IN proveedores |
       CASE WHEN x.monto > top.monto THEN x ELSE top END
     ) AS top_proveedor
WITH e, year, monto_total_entidad, top_proveedor,
     toFloat(top_proveedor.monto) / toFloat(monto_total_entidad) AS concentracion
WHERE concentracion >= 0.40 AND monto_total_entidad > 1000000
RETURN
  e.ruc                        AS ruc_entidad,
  e.name                       AS entidad,
  e.region                     AS region,
  year,
  top_proveedor.company        AS proveedor_dominante,
  round(monto_total_entidad)   AS gasto_total_pen,
  round(concentracion * 100)   AS pct_top_proveedor
ORDER BY concentracion DESC
LIMIT 50;


// ------------------------------------------------------------
// F7 — Fraccionamiento de contratos
// ≥3 contratos mismo par (supplier, entidad) en 30 días, procedure simplificada
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE k.procedure_type CONTAINS 'Simplificada'
   OR k.procedure_type CONTAINS 'Directa'
WITH c, e, k
ORDER BY c.ruc, e.ruc, k.fecha
WITH c, e,
     collect({fecha: k.fecha, monto: k.monto, ext_id: k.external_id}) AS contratos
WHERE size(contratos) >= 3
// Detectar ventanas de 30 días con ≥3 contratos
WITH c, e, contratos,
     [i IN range(0, size(contratos)-3) |
       CASE WHEN duration.between(
               date(contratos[i].fecha),
               date(contratos[i+2].fecha)
             ).days <= 30
            THEN {
              inicio:    contratos[i].fecha,
              fin:       contratos[i+2].fecha,
              n:         3,
              monto_sum: contratos[i].monto + contratos[i+1].monto + contratos[i+2].monto
            }
            ELSE null
       END
     ] AS ventanas_raw
WITH c, e,
     [v IN ventanas_raw WHERE v IS NOT NULL] AS ventanas
WHERE size(ventanas) > 0
UNWIND ventanas AS v
RETURN
  c.ruc              AS ruc_supplier,
  c.name             AS supplier,
  e.name             AS entidad_compradora,
  v.inicio           AS fecha_inicio_ventana,
  v.fin              AS fecha_fin_ventana,
  v.n                AS contratos_en_30_dias,
  round(v.monto_sum) AS monto_acumulado
ORDER BY monto_acumulado DESC
LIMIT 50;


// ------------------------------------------------------------
// F8 — Ráfaga fin de año
// Supplier con ≥50% de sus contratos anuales concentrados en diciembre
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)
WITH c, k.period_year AS year,
     count(k)                                            AS total_año,
     sum(CASE WHEN k.fecha.month = 12 THEN 1 ELSE 0 END) AS en_diciembre,
     sum(CASE WHEN k.fecha.month = 12 THEN w.monto ELSE 0 END) AS monto_dic,
     sum(w.monto) AS monto_año
WHERE total_año >= 5
WITH c, year, total_año, en_diciembre, monto_dic, monto_año,
     toFloat(en_diciembre) / toFloat(total_año) AS pct_dic
WHERE pct_dic >= 0.50
RETURN
  c.ruc              AS ruc,
  c.name             AS supplier,
  year,
  total_año          AS total_contratos_año,
  en_diciembre       AS contratos_en_dic,
  round(pct_dic*100) AS pct_diciembre,
  round(monto_dic)   AS monto_dic_pen,
  round(monto_año)   AS monto_total_año
ORDER BY pct_dic DESC
LIMIT 50;


// ------------------------------------------------------------
// F9 — Adjudicación directa anómala
// Contracts con procedure simplificada/directa y monto > p90 del tipo
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)
WHERE k.procedure_type CONTAINS 'Simplificada'
   OR k.procedure_type CONTAINS 'Directa'
WITH k.procedure_type AS tipo,
     percentileCont(k.monto, 0.90) AS p90
WITH tipo, p90
MATCH (c2:Company)-[w2:WON]->(k2:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE k2.procedure_type = tipo
  AND k2.monto > p90
RETURN
  c2.ruc            AS ruc_supplier,
  c2.name           AS supplier,
  e.name            AS entidad,
  k2.external_id    AS contract_id,
  k2.procedure_type AS modalidad,
  round(k2.monto)   AS monto_pen,
  round(p90)        AS p90_tipo,
  k2.fecha          AS fecha,
  k2.region         AS region
ORDER BY k2.monto DESC
LIMIT 100;


// ------------------------------------------------------------
// F10 — Supplier monógamo
// Supplier con ≥3 contratos y solo 1 entidad pública cliente en 2+ años
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WITH c,
     count(DISTINCT e.ruc)  AS n_clientes,
     count(k)               AS n_contratos,
     sum(w.monto)           AS monto_total,
     count(DISTINCT k.period_year) AS n_años,
     collect(DISTINCT e.name)[0] AS unico_cliente
WHERE n_contratos >= 3
  AND n_clientes = 1
  AND n_años >= 2
RETURN
  c.ruc            AS ruc,
  c.name           AS supplier,
  unico_cliente    AS cliente_unico,
  n_contratos,
  n_años,
  round(monto_total) AS monto_total_pen,
  c.estado         AS estado_sunat
ORDER BY monto_total DESC
LIMIT 50;


// ------------------------------------------------------------
// F11 — RUC incompleto (trazabilidad rota)
// Companies con ruc de tipo hash (supplier sin RUC en OCDS)
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE c.ruc STARTS WITH 'hash_' OR c.is_ruc_complete = false
WITH c,
     count(k)     AS n_contratos,
     sum(w.monto) AS monto_total,
     collect(DISTINCT e.name)[..3] AS entidades
RETURN
  c.ruc          AS ruc_o_hash,
  c.name         AS supplier_name,
  n_contratos,
  round(monto_total) AS monto_pen,
  entidades
ORDER BY monto_total DESC
LIMIT 100;


// ------------------------------------------------------------
// F12 — Outlier de monto
// Contracts con monto > μ + 3σ dentro del (region, procedure_type)
// ------------------------------------------------------------
MATCH (k:Contract)
WITH k.region AS region, k.procedure_type AS tipo,
     avg(k.monto)   AS media,
     stDev(k.monto) AS desv
WITH region, tipo, media, desv,
     media + 3 * desv AS umbral
MATCH (c:Company)-[w:WON]->(k2:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE k2.region = region
  AND k2.procedure_type = tipo
  AND k2.monto > umbral
  AND desv > 0
RETURN
  k2.external_id    AS contract_id,
  c.name            AS supplier,
  e.name            AS entidad,
  k2.region         AS region,
  k2.procedure_type AS modalidad,
  round(k2.monto)   AS monto,
  round(umbral)     AS umbral_3sigma,
  k2.fecha          AS fecha
ORDER BY k2.monto DESC
LIMIT 100;


// ============================================================
// GRUPO C — TDR DOSSIERS
// ============================================================

// ------------------------------------------------------------
// F13 — Dossier high-risk
// Contracts con dossier de riesgo MEDIO o ALTO
// ------------------------------------------------------------
MATCH (k:Contract)-[:ANALYZED_BY]->(d:Dossier)
WHERE d.risk_level IN ['MEDIO', 'ALTO']
OPTIONAL MATCH (c:Company)-[w:WON]->(k)
OPTIONAL MATCH (k)-[:AWARDED_BY]->(e:PublicEntity)
RETURN
  k.ocid             AS ocid,
  k.external_id      AS contract_id,
  c.name             AS supplier,
  c.ruc              AS ruc_supplier,
  e.name             AS entidad,
  round(k.monto)     AS monto_pen,
  d.risk_level       AS nivel_riesgo,
  d.total_score      AS score,
  d.total_flags      AS n_flags,
  d.sector           AS sector,
  k.fecha            AS fecha
ORDER BY d.total_score DESC;


// ------------------------------------------------------------
// F14 — Flags TDR por tipo
// Distribución de flags en dossiers y sus contratos
// ------------------------------------------------------------
MATCH (d:Dossier)-[:HAS_FLAG]->(f:RiskFlag)
OPTIONAL MATCH (k:Contract)-[:ANALYZED_BY]->(d)
OPTIONAL MATCH (c:Company)-[w:WON]->(k)
RETURN
  f.flag_code        AS flag_code,
  f.flag_name        AS flag_nombre,
  f.severity         AS severidad,
  f.score_contribution AS puntos,
  f.page_number      AS pagina,
  f.evidence_quote   AS cita_evidencia,
  d.ocid             AS dossier_ocid,
  d.risk_level       AS riesgo_dossier,
  round(k.monto)     AS monto_contrato,
  c.name             AS supplier,
  k.fecha            AS fecha
ORDER BY f.score_contribution DESC, k.monto DESC;


// ============================================================
// GRUPO D — SUNAT RICO (e-consultaruc)
// Requieren scraping completado
// ============================================================

// ------------------------------------------------------------
// F15 — Empresa fantasma por trabajadores
// Empresa ganó contratos grandes pero tiene 0 o muy pocos trabajadores
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE c.max_trabajadores IS NOT NULL
  AND c.max_trabajadores <= 2
  AND k.monto > 100000
WITH c, e,
     count(k)     AS n_contratos,
     sum(w.monto) AS monto_total,
     c.max_trabajadores AS max_trab
RETURN
  c.ruc                AS ruc,
  c.name               AS empresa,
  c.tipo_contribuyente AS tipo,
  c.estado             AS estado,
  max_trab             AS max_trabajadores_recientes,
  n_contratos,
  round(monto_total)   AS monto_total_pen,
  e.name               AS entidad_principal
ORDER BY monto_total DESC
LIMIT 100;


// ------------------------------------------------------------
// F16 — Representante legal compartido (MISMO_REPR_LEGAL)
// ≥2 empresas con el mismo representante legal ganando del mismo comprador
// ------------------------------------------------------------
MATCH (p:Person)-[:REPRESENTS]->(c1:Company)
MATCH (p)-[:REPRESENTS]->(c2:Company)
WHERE c1.ruc < c2.ruc
MATCH (c1)-[w1:WON]->(:Contract)-[:AWARDED_BY]->(e:PublicEntity)
      <-[:AWARDED_BY]-(:Contract)<-[w2:WON]-(c2)
WITH p, e,
     collect(DISTINCT c1.name + ' (' + c1.ruc + ')') +
     collect(DISTINCT c2.name + ' (' + c2.ruc + ')') AS empresas_vinculadas,
     sum(w1.monto) + sum(w2.monto)                   AS monto_combinado
RETURN
  p.doc_id              AS dni_representante,
  p.name                AS nombre_representante,
  e.name                AS comprador_comun,
  size(empresas_vinculadas) AS n_empresas,
  empresas_vinculadas,
  round(monto_combinado) AS monto_total_pen
ORDER BY monto_combinado DESC
LIMIT 50;


// ------------------------------------------------------------
// F17 — Empresa con deuda coactiva ganando contratos
// Empresa con problemas tributarios accediendo a dinero público
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE (c.deuda_coactiva = true OR c.omisiones_tributarias = true)
WITH c, e,
     count(k)     AS n_contratos,
     sum(w.monto) AS monto_total
RETURN
  c.ruc                  AS ruc,
  c.name                 AS empresa,
  c.estado               AS estado,
  c.deuda_coactiva       AS tiene_deuda_coactiva,
  c.omisiones_tributarias AS tiene_omisiones,
  c.tiene_actas_probatorias AS tiene_actas,
  n_contratos,
  round(monto_total)     AS monto_total_pen,
  e.name                 AS entidad_principal
ORDER BY monto_total DESC
LIMIT 100;


// ------------------------------------------------------------
// F18 — Mismatch de actividad económica (CIIU vs sector contrato)
// Empresa con CIIU de salud ganando en ambiente (o viceversa)
// Mapa CIIU → sector: 86=Salud, 38/39=Ambiente, 41/42/43=Construcción
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE c.ciiu_principal IS NOT NULL
WITH c, k, w, e,
  CASE
    WHEN c.ciiu_principal STARTS WITH '86' THEN 'salud'
    WHEN c.ciiu_principal STARTS WITH '87' THEN 'salud'
    WHEN c.ciiu_principal STARTS WITH '38' THEN 'ambiente'
    WHEN c.ciiu_principal STARTS WITH '39' THEN 'ambiente'
    WHEN c.ciiu_principal STARTS WITH '01' THEN 'agricultura'
    WHEN c.ciiu_principal STARTS WITH '41' THEN 'construccion'
    WHEN c.ciiu_principal STARTS WITH '42' THEN 'construccion'
    WHEN c.ciiu_principal STARTS WITH '43' THEN 'construccion'
    WHEN c.ciiu_principal STARTS WITH '51' THEN 'transporte_aereo'
    WHEN c.ciiu_principal STARTS WITH '47' THEN 'comercio_retail'
    ELSE 'otro'
  END AS sector_empresa
// Derivar sector del contrato desde entity region y procedure
WITH c, k, w, e, sector_empresa,
  CASE
    WHEN e.name CONTAINS 'SALUD' OR e.name CONTAINS 'ESSALUD' OR e.name CONTAINS 'HOSPITAL' THEN 'salud'
    WHEN e.name CONTAINS 'AMBIENTE' OR e.name CONTAINS 'ANA' OR e.name CONTAINS 'SERNANP' THEN 'ambiente'
    WHEN e.name CONTAINS 'EDUCACION' OR e.name CONTAINS 'UGEL' THEN 'educacion'
    ELSE 'otro'
  END AS sector_contrato
WHERE sector_empresa <> 'otro'
  AND sector_contrato <> 'otro'
  AND sector_empresa <> sector_contrato
  AND k.monto > 50000
WITH c, e,
     count(k)     AS contratos_mismatch,
     sum(w.monto) AS monto_mismatch,
     sector_empresa, sector_contrato
RETURN
  c.ruc              AS ruc,
  c.name             AS empresa,
  c.ciiu_principal   AS ciiu,
  c.actividad_principal AS actividad_empresa,
  sector_empresa,
  sector_contrato,
  e.name             AS entidad,
  contratos_mismatch,
  round(monto_mismatch) AS monto_pen
ORDER BY monto_mismatch DESC
LIMIT 100;


// ------------------------------------------------------------
// F19 — Empresa recién creada ganando contrato grande
// fecha_inicio_actividades < 12 meses antes del primer contrato > 500k
// ------------------------------------------------------------
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WHERE c.fecha_inicio_actividades IS NOT NULL
  AND k.monto > 500000
WITH c, k, w, e,
     duration.between(c.fecha_inicio_actividades, k.fecha).days AS dias_desde_creacion
WHERE dias_desde_creacion < 365 AND dias_desde_creacion >= 0
WITH c, e,
     count(k)                AS n_contratos_grandes,
     sum(w.monto)            AS monto_total,
     min(dias_desde_creacion) AS dias_minimo,
     c.fecha_inicio_actividades AS inicio_actividades
RETURN
  c.ruc                  AS ruc,
  c.name                 AS empresa,
  c.tipo_contribuyente   AS tipo,
  inicio_actividades,
  dias_minimo            AS dias_hasta_primer_contrato_grande,
  n_contratos_grandes,
  round(monto_total)     AS monto_total_pen,
  e.name                 AS entidad_principal
ORDER BY dias_minimo ASC
LIMIT 100;


// ============================================================
// RESUMEN EJECUTIVO — vista consolidada de todos los flags
// ============================================================
MATCH (c:Company)-[w:WON]->(k:Contract)-[:AWARDED_BY]->(e:PublicEntity)
WITH c, e,
     count(k)     AS n_contratos,
     sum(w.monto) AS monto_total,
     // F9 proxy: al menos 1 Adjudicacion Simplificada de alto monto
     sum(CASE WHEN (k.procedure_type CONTAINS 'Simplificada'
                    OR k.procedure_type CONTAINS 'Directa')
                   AND k.monto > 500000
              THEN 1 ELSE 0 END) AS f9_flags,
     // F11: RUC incompleto
     CASE WHEN c.ruc STARTS WITH 'hash_' THEN 1 ELSE 0 END AS f11_flag,
     // F1: fantasma SUNAT
     CASE WHEN c.estado = 'BAJA' OR c.condicion = 'NO HABIDO' THEN 1 ELSE 0 END AS f1_flag
RETURN
  c.ruc          AS ruc,
  c.name         AS empresa,
  e.name         AS entidad_principal,
  n_contratos,
  round(monto_total) AS monto_total_pen,
  f1_flag        AS flag_fantasma,
  f9_flags       AS flag_adj_directa_anomala,
  f11_flag       AS flag_ruc_incompleto,
  c.estado       AS estado_sunat,
  c.condicion    AS condicion_sunat
ORDER BY monto_total DESC
LIMIT 200;
