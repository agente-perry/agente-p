"""
agente-perry ingestor — GCS → Neo4j AuraDB

Usage:
  python main.py schema      # Apply ontology/schema.cypher (constraints + indexes)
  python main.py ocds        # Load OCDS contracts + tenders (72k records)
  python main.py sunat       # Enrich companies + load Person nodes from SUNAT JSONL
  python main.py dossiers    # Load Dossier + RiskFlag nodes from scraped/results/
  python main.py seace       # Load ProcedureSeace nodes from downloads/
  python main.py derived     # SAME_ADDRESS_AS, SAME_REPR_AS, metrics
  python main.py all         # Run all steps in order
  python main.py verify      # Print node/edge counts
"""
import argparse
import logging
import sys
import os


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
    )
    # Suppress Neo4j performance notifications (CartesianProduct, etc.)
    logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)


def cmd_schema(_args) -> None:
    from neo4j_utils import run_query
    schema_path = os.path.join(os.path.dirname(__file__), "..", "ontology", "schema.cypher")
    with open(schema_path, encoding="utf-8") as f:
        raw = f.read()

    stmts = [s.strip() for s in raw.split(";") if s.strip() and not s.strip().startswith("//")]
    # Keep only CREATE CONSTRAINT / CREATE INDEX statements (skip MERGE examples + MATCH queries)
    ddl = [s for s in stmts if s.upper().startswith(("CREATE CONSTRAINT", "CREATE INDEX"))]
    logging.getLogger("schema").info("Applying %d DDL statements...", len(ddl))
    for stmt in ddl:
        try:
            run_query(stmt)
        except Exception as exc:
            logging.getLogger("schema").warning("  %s — %s", stmt[:60], exc)
    logging.getLogger("schema").info("Schema applied.")


def cmd_ocds(args) -> None:
    from load_ocds import load_ocds
    load_ocds(getattr(args, "path", None))


def cmd_sunat(args) -> None:
    from load_sunat import load_sunat
    load_sunat(getattr(args, "path", None))


def cmd_dossiers(_args) -> None:
    from load_dossiers import load_dossiers
    load_dossiers()


def cmd_seace(_args) -> None:
    from load_seace import load_seace
    load_seace()


def cmd_derived(_args) -> None:
    from run_derived import run_all_derived
    run_all_derived()


def cmd_all(args) -> None:
    cmd_schema(args)
    cmd_ocds(args)
    cmd_sunat(args)
    cmd_dossiers(args)
    cmd_seace(args)
    cmd_derived(args)


def cmd_checkpoint(_args) -> None:
    import checkpoint as cp
    status = cp.status()
    if not status:
        print("No checkpoints — loaders completed cleanly or never run.")
    else:
        for name, last in status.items():
            print(f"  {name:12s}: last flushed record {last:,}")


def cmd_verify(_args) -> None:
    from neo4j_utils import run_query
    labels = ["Company", "PublicEntity", "Contract", "Tender", "Address",
              "Person", "Dossier", "RiskFlag", "ProcedureSeace"]
    for label in labels:
        result = run_query(f"MATCH (n:{label}) RETURN count(n) AS n")
        print(f"  {label:20s}: {result[0]['n']:>8,}")

    edges = ["WON", "AWARDED_BY", "UNDER_TENDER", "LOCATED_AT",
             "SAME_ADDRESS_AS", "REPRESENTS", "SAME_REPR_AS", "ANALYZED_BY", "HAS_FLAG"]
    for rel in edges:
        result = run_query(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS n")
        print(f"  {rel:20s}: {result[0]['n']:>8,}")


COMMANDS = {
    "schema": cmd_schema,
    "ocds": cmd_ocds,
    "sunat": cmd_sunat,
    "dossiers": cmd_dossiers,
    "seace": cmd_seace,
    "derived": cmd_derived,
    "all": cmd_all,
    "verify": cmd_verify,
    "checkpoint": cmd_checkpoint,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="agente-perry ingestor")
    parser.add_argument("command", choices=list(COMMANDS.keys()))
    parser.add_argument("--path", help="Override GCS blob path for ocds/sunat commands")
    parser.add_argument("--log", default="INFO", help="Log level (default: INFO)")
    args = parser.parse_args()

    _setup_logging(args.log)
    try:
        COMMANDS[args.command](args)
    finally:
        from neo4j_utils import close
        close()


if __name__ == "__main__":
    main()
