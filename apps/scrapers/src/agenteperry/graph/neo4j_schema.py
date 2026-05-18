"""Neo4j graph schema setup — SPEC-0012.

Creates constraints (uniqueness) and indexes (fast lookup) on first run.
All statements use IF NOT EXISTS so this module is idempotent.

Run once before any ingestion::

    from agenteperry.graph.neo4j_schema import setup_schema
    setup_schema()

Or via CLI::

    agenteperry graph neo4j-setup
"""

from __future__ import annotations

from agenteperry.graph.neo4j_client import Neo4jClient

# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

# Constraints guarantee uniqueness and create a backing index automatically.
# Named constraints allow IF NOT EXISTS semantics in Neo4j 4.4+.
_CONSTRAINTS: list[tuple[str, str]] = [
    (
        "contract_ocid_unique",
        "CREATE CONSTRAINT contract_ocid_unique IF NOT EXISTS "
        "FOR (c:Contract) REQUIRE c.ocid IS UNIQUE",
    ),
    (
        "company_ruc_unique",
        "CREATE CONSTRAINT company_ruc_unique IF NOT EXISTS "
        "FOR (co:Company) REQUIRE co.ruc IS UNIQUE",
    ),
    (
        "person_canonical_unique",
        "CREATE CONSTRAINT person_canonical_unique IF NOT EXISTS "
        "FOR (p:Person) REQUIRE p.canonical_id IS UNIQUE",
    ),
    (
        "public_entity_ruc_unique",
        "CREATE CONSTRAINT public_entity_ruc_unique IF NOT EXISTS "
        "FOR (e:PublicEntity) REQUIRE e.ruc IS UNIQUE",
    ),
    (
        "tdr_id_unique",
        "CREATE CONSTRAINT tdr_id_unique IF NOT EXISTS "
        "FOR (t:TDR) REQUIRE t.tdr_id IS UNIQUE",
    ),
    (
        "flag_id_unique",
        "CREATE CONSTRAINT flag_id_unique IF NOT EXISTS "
        "FOR (f:Flag) REQUIRE f.flag_id IS UNIQUE",
    ),
]

# Secondary indexes for common filter/sort columns.
_INDEXES: list[tuple[str, str]] = [
    (
        "contract_amount_idx",
        "CREATE INDEX contract_amount_idx IF NOT EXISTS "
        "FOR (c:Contract) ON (c.amount)",
    ),
    (
        "contract_date_idx",
        "CREATE INDEX contract_date_idx IF NOT EXISTS "
        "FOR (c:Contract) ON (c.contract_date)",
    ),
    (
        "company_name_idx",
        "CREATE INDEX company_name_idx IF NOT EXISTS "
        "FOR (co:Company) ON (co.name)",
    ),
    (
        "flag_code_idx",
        "CREATE INDEX flag_code_idx IF NOT EXISTS "
        "FOR (f:Flag) ON (f.flag_code)",
    ),
    (
        "flag_severity_idx",
        "CREATE INDEX flag_severity_idx IF NOT EXISTS "
        "FOR (f:Flag) ON (f.severity)",
    ),
    (
        "tdr_ocid_idx",
        "CREATE INDEX tdr_ocid_idx IF NOT EXISTS "
        "FOR (t:TDR) ON (t.ocid)",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def setup_schema(client: Neo4jClient | None = None) -> dict[str, int]:
    """Create all constraints and indexes.  Idempotent — safe to run multiple times.

    Returns a summary dict with counts of created/skipped statements.
    """
    own_client = client is None
    if own_client:
        client = Neo4jClient()

    created = 0
    skipped = 0
    errors: list[str] = []

    try:
        for name, ddl in _CONSTRAINTS:
            try:
                client.execute_write(ddl)
                created += 1
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "already exists" in msg or "equivalent constraint" in msg:
                    skipped += 1
                else:
                    errors.append(f"constraint {name}: {exc}")

        for name, ddl in _INDEXES:
            try:
                client.execute_write(ddl)
                created += 1
            except Exception as exc:  # noqa: BLE001
                msg = str(exc).lower()
                if "already exists" in msg or "equivalent index" in msg:
                    skipped += 1
                else:
                    errors.append(f"index {name}: {exc}")
    finally:
        if own_client:
            client.close()

    if errors:
        raise RuntimeError(
            f"Schema setup completed with {len(errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    return {"created": created, "skipped": skipped, "total": created + skipped}


def drop_all_data(client: Neo4jClient) -> int:
    """Delete all nodes and relationships.  DESTRUCTIVE — development use only.

    Returns total nodes deleted.
    """
    result = client.execute_write("MATCH (n) DETACH DELETE n RETURN count(n) AS deleted")
    return result[0]["deleted"] if result else 0
