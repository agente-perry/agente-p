// ============================================================
// SCHEMA — Ontología Anticorrupción Neo4j AuraDB
// Proyecto: agente-perry | Versión: 2.0 | 2026-05-17
// SUNAT: e-consultaruc (rico) — incluye Person, trabajadores, CIIU
// Ejecutar ANTES de ingestar data
// ============================================================

// ------------------------------------------------------------
// CONSTRAINTS (garantizan unicidad y crean índice automático)
// ------------------------------------------------------------

CREATE CONSTRAINT company_ruc IF NOT EXISTS
FOR (c:Company) REQUIRE c.ruc IS UNIQUE;

CREATE CONSTRAINT public_entity_ruc IF NOT EXISTS
FOR (e:PublicEntity) REQUIRE e.ruc IS UNIQUE;

CREATE CONSTRAINT contract_external_id IF NOT EXISTS
FOR (c:Contract) REQUIRE c.external_id IS UNIQUE;

CREATE CONSTRAINT tender_tender_id IF NOT EXISTS
FOR (t:Tender) REQUIRE t.tender_id IS UNIQUE;

CREATE CONSTRAINT address_hash IF NOT EXISTS
FOR (a:Address) REQUIRE a.address_hash IS UNIQUE;

CREATE CONSTRAINT dossier_ocid IF NOT EXISTS
FOR (d:Dossier) REQUIRE d.ocid IS UNIQUE;

CREATE CONSTRAINT riskflag_id IF NOT EXISTS
FOR (f:RiskFlag) REQUIRE f.flag_id IS UNIQUE;

CREATE CONSTRAINT procedure_seace_uuid IF NOT EXISTS
FOR (p:ProcedureSeace) REQUIRE p.uuid IS UNIQUE;

CREATE CONSTRAINT person_doc_id IF NOT EXISTS
FOR (p:Person) REQUIRE p.doc_id IS UNIQUE;

// ------------------------------------------------------------
// ÍNDICES adicionales (propiedades de búsqueda frecuente)
// ------------------------------------------------------------

CREATE INDEX contract_fecha IF NOT EXISTS
FOR (c:Contract) ON (c.fecha);

CREATE INDEX contract_monto IF NOT EXISTS
FOR (c:Contract) ON (c.monto);

CREATE INDEX contract_procedure_type IF NOT EXISTS
FOR (c:Contract) ON (c.procedure_type);

CREATE INDEX contract_period_year IF NOT EXISTS
FOR (c:Contract) ON (c.period_year);

CREATE INDEX contract_region IF NOT EXISTS
FOR (c:Contract) ON (c.region);

CREATE INDEX company_estado IF NOT EXISTS
FOR (c:Company) ON (c.estado);

CREATE INDEX company_condicion IF NOT EXISTS
FOR (c:Company) ON (c.condicion);

CREATE INDEX company_ubigeo IF NOT EXISTS
FOR (c:Company) ON (c.ubigeo);

CREATE INDEX company_is_ruc_complete IF NOT EXISTS
FOR (c:Company) ON (c.is_ruc_complete);

CREATE INDEX public_entity_region IF NOT EXISTS
FOR (e:PublicEntity) ON (e.region);

CREATE INDEX dossier_risk_level IF NOT EXISTS
FOR (d:Dossier) ON (d.risk_level);

CREATE INDEX dossier_total_score IF NOT EXISTS
FOR (d:Dossier) ON (d.total_score);

CREATE INDEX riskflag_code IF NOT EXISTS
FOR (f:RiskFlag) ON (f.flag_code);

CREATE INDEX riskflag_severity IF NOT EXISTS
FOR (f:RiskFlag) ON (f.severity);

CREATE INDEX company_deuda IF NOT EXISTS
FOR (c:Company) ON (c.deuda_coactiva);

CREATE INDEX company_trabajadores IF NOT EXISTS
FOR (c:Company) ON (c.max_trabajadores);

CREATE INDEX company_ciiu IF NOT EXISTS
FOR (c:Company) ON (c.ciiu_principal);

CREATE INDEX person_name IF NOT EXISTS
FOR (p:Person) ON (p.name);

// ------------------------------------------------------------
// EJEMPLOS DE MERGE (upsert) — para el ingestor
// ------------------------------------------------------------

// --- Company (desde OCDS, sin enrich SUNAT) ---
MERGE (c:Company {ruc: $ruc})
ON CREATE SET
  c.name              = $name,
  c.is_ruc_complete   = (size($ruc) = 11 AND NOT $ruc STARTS WITH 'hash_'),
  c.estado            = null,
  c.condicion         = null,
  c.domicilio_fiscal  = null,
  c.source            = ['ocds_peru']
ON MATCH SET
  c.name              = CASE WHEN c.name IS NULL THEN $name ELSE c.name END;

// --- Company enrich desde SUNAT e-consultaruc ---
// $trabajadores = list of {Período, N° de Trabajadores}
// $actividades  = list of strings "Principal - CIIU - DESC"
MERGE (c:Company {ruc: $ruc})
ON MATCH SET
  c.nombre_comercial        = $nombre_comercial,
  c.tipo_contribuyente      = $tipo_contribuyente,
  c.estado                  = $estado,
  c.condicion               = $condicion,
  c.domicilio_fiscal        = $domicilio_fiscal,
  c.fecha_inscripcion       = CASE WHEN $fecha_inscripcion <> '' THEN date($fecha_inscripcion_iso) ELSE null END,
  c.fecha_inicio_actividades= CASE WHEN $fecha_inicio_iso <> '' THEN date($fecha_inicio_iso) ELSE null END,
  c.ciiu_principal          = $ciiu_principal,
  c.actividad_principal     = $actividad_principal,
  c.max_trabajadores        = $max_trabajadores,
  c.min_trabajadores        = $min_trabajadores,
  c.deuda_coactiva          = ($deuda_coactiva <> 'Sin información' AND $deuda_coactiva <> ''),
  c.omisiones_tributarias   = ($omisiones <> 'Sin información' AND $omisiones <> ''),
  c.tiene_actas_probatorias = $tiene_actas,
  c.source                  = CASE WHEN 'sunat_econsulta' IN c.source THEN c.source
                                   ELSE c.source + ['sunat_econsulta'] END;

// --- Person (representante legal) ---
MERGE (p:Person {doc_id: $doc_id})
ON CREATE SET
  p.doc_type = $doc_type,
  p.name     = $nombre;

// --- Person -[REPRESENTS]-> Company ---
MATCH (p:Person {doc_id: $doc_id}), (c:Company {ruc: $ruc})
MERGE (p)-[r:REPRESENTS]->(c)
ON CREATE SET
  r.cargo       = $cargo,
  r.fecha_desde = CASE WHEN $fecha_desde <> '' THEN date($fecha_desde_iso) ELSE null END;

// --- PublicEntity ---
MERGE (e:PublicEntity {ruc: $ruc})
ON CREATE SET
  e.name   = $name,
  e.region = $region;

// --- Contract ---
MERGE (ct:Contract {external_id: $external_id})
ON CREATE SET
  ct.ocid           = $ocid,
  ct.tender_id      = $tender_id,
  ct.award_id       = $award_id,
  ct.monto          = $monto,
  ct.fecha          = date($fecha),
  ct.period_year    = $period_year,
  ct.procedure_type = $procedure_type,
  ct.region         = $region,
  ct.evidence_quote = $evidence_quote;

// --- Tender (procedure sin ganador) ---
MERGE (t:Tender {tender_id: $tender_id})
ON CREATE SET
  t.ocid           = $ocid,
  t.procedure_type = $procedure_type,
  t.fecha          = date($fecha),
  t.monto          = $monto,
  t.region         = $region;

// --- Address ---
MERGE (a:Address {address_hash: $address_hash})
ON CREATE SET
  a.domicilio_fiscal = $domicilio_fiscal,
  a.ubigeo           = $ubigeo,
  a.tipo_via         = $tipo_via,
  a.nombre_via       = $nombre_via,
  a.numero           = $numero,
  a.tipo_zona        = $tipo_zona,
  a.is_generic       = ($numero IN ['S/N', '', null]);

// --- Dossier ---
MERGE (d:Dossier {ocid: $ocid})
ON CREATE SET
  d.entity_name    = $entity_name,
  d.sector         = $sector,
  d.procedure_code = $procedure_code,
  d.monto          = $monto,
  d.total_score    = $total_score,
  d.risk_level     = $risk_level,
  d.total_flags    = $total_flags,
  d.total_pages    = $total_pages,
  d.coverage_pct   = $coverage_pct,
  d.generated_at   = datetime($generated_at);

// --- RiskFlag ---
MERGE (f:RiskFlag {flag_id: $flag_id})
ON CREATE SET
  f.flag_code         = $flag_code,
  f.flag_name         = $flag_name,
  f.severity          = $severity,
  f.score_contribution= $score_contribution,
  f.page_number       = $page_number,
  f.evidence_quote    = $evidence_quote,
  f.rule_id           = $rule_id,
  f.detection_method  = $detection_method;

// --- ProcedureSeace ---
MERGE (p:ProcedureSeace {uuid: $uuid})
ON CREATE SET
  p.nomenclatura        = $nomenclatura,
  p.numero              = $numero,
  p.entidad             = $entidad,
  p.descripcion         = $descripcion,
  p.cuantia             = $cuantia,
  p.fecha_hora          = datetime($fecha_hora),
  p.completed_targets   = $completed_targets,
  p.linked_contract_ocid= null;

// --- Relaciones ---

// Company -[WON]-> Contract
MATCH (c:Company {ruc: $supplier_ruc}), (ct:Contract {external_id: $external_id})
MERGE (c)-[w:WON]->(ct)
ON CREATE SET
  w.monto          = $monto,
  w.fecha          = date($fecha),
  w.procedure_type = $procedure_type,
  w.region         = $region;

// Contract -[AWARDED_BY]-> PublicEntity
MATCH (ct:Contract {external_id: $external_id}), (e:PublicEntity {ruc: $entity_ruc})
MERGE (ct)-[:AWARDED_BY]->(e);

// Contract -[UNDER_TENDER]-> Tender
MATCH (ct:Contract {external_id: $external_id}), (t:Tender {tender_id: $tender_id})
MERGE (ct)-[:UNDER_TENDER]->(t);

// Company -[LOCATED_AT]-> Address
MATCH (c:Company {ruc: $ruc}), (a:Address {address_hash: $address_hash})
MERGE (c)-[:LOCATED_AT]->(a);

// Contract -[ANALYZED_BY]-> Dossier  (por ocid)
MATCH (ct:Contract), (d:Dossier {ocid: $ocid})
WHERE ct.ocid = $ocid
MERGE (ct)-[:ANALYZED_BY]->(d);

// Dossier -[HAS_FLAG]-> RiskFlag
MATCH (d:Dossier {ocid: $ocid}), (f:RiskFlag {flag_id: $flag_id})
MERGE (d)-[:HAS_FLAG]->(f);

// ------------------------------------------------------------
// DERIVADA: SAME_ADDRESS_AS
// Ejecutar UNA VEZ post-carga de Address nodes
// ------------------------------------------------------------
MATCH (c1:Company)-[:LOCATED_AT]->(a:Address)<-[:LOCATED_AT]-(c2:Company)
WHERE c1.ruc < c2.ruc AND a.is_generic = false
MERGE (c1)-[:SAME_ADDRESS_AS {via_address_hash: a.address_hash}]->(c2);

// ------------------------------------------------------------
// SANITY QUERIES — verificar carga
// ------------------------------------------------------------

// Conteos esperados post carga completa:
MATCH (c:Company)       RETURN 'Company'      AS label, count(c) AS n;
// esperado: ~30,578

MATCH (e:PublicEntity)  RETURN 'PublicEntity' AS label, count(e) AS n;
// esperado: ~2,731

MATCH (c:Contract)      RETURN 'Contract'     AS label, count(c) AS n;
// esperado: ~55,457

MATCH (t:Tender)        RETURN 'Tender'       AS label, count(t) AS n;
// esperado: ~16,942

MATCH ()-[r:WON]->()    RETURN 'WON edges'    AS label, count(r) AS n;
// esperado: ~55,457 (uno por contract, si supplier_ruc no null)
// realista: ~41,994 (58% con supplier_ruc válido)
