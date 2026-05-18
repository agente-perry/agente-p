import logging
import time
from neo4j import GraphDatabase
import config

logger = logging.getLogger(__name__)

_driver = None

_MAX_RETRIES = 5
_RETRY_BACKOFF = [2, 5, 10, 30, 60]  # seconds between retries


def _get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            config.NEO4J_URI,
            auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
            max_connection_lifetime=300,       # refresh connections every 5 min
            max_connection_pool_size=10,
            connection_acquisition_timeout=60,
            keep_alive=True,
        )
    return _driver


def _reset_driver():
    global _driver
    if _driver:
        try:
            _driver.close()
        except Exception:
            pass
    _driver = None


def close():
    _reset_driver()


def run_batch(cypher: str, rows: list) -> None:
    """Execute `UNWIND $rows AS row <cypher>` with retry on transient network errors."""
    if not rows:
        return
    for attempt in range(_MAX_RETRIES):
        try:
            with _get_driver().session(database=config.NEO4J_DATABASE) as s:
                s.run(f"UNWIND $rows AS row {cypher}", rows=rows)
            return
        except Exception as exc:
            wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
            logger.warning(
                "Neo4j error (attempt %d/%d), retrying in %ds: %s",
                attempt + 1, _MAX_RETRIES, wait, exc,
            )
            _reset_driver()
            time.sleep(wait)
    raise RuntimeError(f"Neo4j batch failed after {_MAX_RETRIES} retries")


def run_query(cypher: str, params: dict | None = None) -> list:
    for attempt in range(_MAX_RETRIES):
        try:
            with _get_driver().session(database=config.NEO4J_DATABASE) as s:
                return s.run(cypher, params or {}).data()
        except Exception as exc:
            wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
            logger.warning("Neo4j query error (attempt %d/%d), retrying in %ds: %s",
                           attempt + 1, _MAX_RETRIES, wait, exc)
            _reset_driver()
            time.sleep(wait)
    raise RuntimeError(f"Neo4j query failed after {_MAX_RETRIES} retries")
