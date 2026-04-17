"""Dual I/O persistence — JSON file + PostgreSQL.

Write: every .trug.json write persists to both JSON and PostgreSQL (when PORT_DSN set).
       DB write failures are logged but never raised (JSON always written).
Read:  reads from PostgreSQL when PORT_DSN set. Raises on DB error (loud failure).
       Reads from JSON when PORT_DSN is unset (environments without DB).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def write_trug(
    trug: Dict[str, Any],
    path: str | Path,
    *,
    db_dsn: Optional[str] = None,
) -> None:
    """Write a TRUG dict to disk and optionally to PostgreSQL.

    1. Write JSON file (always — never fails due to DB)
    2. If db_dsn or PORT_DSN env var is set, also write to PostgreSQL
    3. DB failures are logged but never raise

    Args:
        trug: The TRUG dict (metadata + nodes + edges).
        path: Destination file path (e.g., folder.trug.json).
        db_dsn: PostgreSQL DSN. If None, reads PORT_DSN env var.
    """
    path = Path(path)

    # Step 1: Write JSON file (always)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(trug, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Step 2: Write to PostgreSQL (optional, best-effort)
    dsn = db_dsn or os.environ.get("PORT_DSN")
    if not dsn:
        return

    try:
        _write_to_postgres(trug, path, dsn)
    except Exception as exc:
        logger.warning("[PORT dual-write] DB write failed for %s: %s", path, exc)


_schema_ensured: set[str] = set()  # DSNs where schema has been created


def _write_to_postgres(
    trug: Dict[str, Any],
    path: Path,
    dsn: str,
) -> None:
    """Internal: persist TRUG to PostgreSQL via trugs-store PostgresPersistence."""
    try:
        import psycopg
    except ImportError:
        logger.warning(
            "[PORT dual-write] psycopg3 not installed — skipping DB write. "
            "Install with: pip install trugs-store[postgres]"
        )
        return

    from trugs_store.memory import InMemoryGraphStore
    from trugs_store.persistence.postgres import PostgresPersistence

    graph_id = path.parent.name

    # Load TRUG dict into InMemoryGraphStore
    store = InMemoryGraphStore()
    for key, value in trug.items():
        if key not in ("nodes", "edges"):
            store.set_metadata(key, value)
    for node in trug.get("nodes", []):
        store._nodes[node["id"]] = node
    for edge in trug.get("edges", []):
        store._edges.append(edge)
    store._rebuild_edge_indexes()

    # Write to PostgreSQL
    conn = psycopg.connect(dsn)
    try:
        pg = PostgresPersistence(conn)
        if dsn not in _schema_ensured:
            pg.ensure_schema()
            _schema_ensured.add(dsn)
        pg.save(store, graph_id)
        conn.commit()
    finally:
        conn.close()


def read_trug(
    path: str | Path,
    *,
    db_dsn: Optional[str] = None,
) -> Dict[str, Any]:
    """Read a TRUG from PostgreSQL (if PORT_DSN set), or from JSON file.

    When PORT_DSN is set: reads from PostgreSQL. Raises on DB error (loud failure).
    When PORT_DSN is unset: reads from JSON file (environments without DB).

    Args:
        path: Path to folder.trug.json (used for JSON read and graph_id derivation).
        db_dsn: PostgreSQL DSN. If None, reads PORT_DSN env var.

    Returns:
        Parsed TRUG dictionary (identical format whether from DB or JSON).

    Raises:
        FileNotFoundError: If JSON file doesn't exist (when reading JSON).
        RuntimeError: If DB read fails (when PORT_DSN is set).
    """
    path = Path(path)
    dsn = db_dsn or os.environ.get("PORT_DSN")

    if dsn:
        return _read_from_postgres(path, dsn)

    # No DSN: read from JSON file (environments without DB)
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_from_postgres(path: Path, dsn: str) -> Dict[str, Any]:
    """Internal: read TRUG from PostgreSQL via trugs-store PostgresPersistence."""
    try:
        import psycopg
    except ImportError:
        raise ImportError("psycopg3 not installed")

    from trugs_store.persistence.postgres import PostgresPersistence

    graph_id = path.parent.name

    conn = psycopg.connect(dsn)
    try:
        pg = PostgresPersistence(conn)
        if dsn not in _schema_ensured:
            pg.ensure_schema()
            _schema_ensured.add(dsn)
        store = pg.load(graph_id)

        # Reconstruct TRUG dict: metadata + nodes + edges
        trug: Dict[str, Any] = dict(store.get_metadata())
        trug["nodes"] = store.find_nodes()
        trug["edges"] = store.get_edges()
        return trug
    finally:
        conn.close()


def export_trug(
    path: str | Path,
    *,
    db_dsn: Optional[str] = None,
) -> bool:
    """Export a graph from PostgreSQL to a JSON file.

    Reads the graph from the database and writes it as folder.trug.json.
    This is the inverse of import_trug().

    Args:
        path: Destination file path (e.g., TRUGS_AAA/folder.trug.json).
        db_dsn: PostgreSQL DSN. If None, reads PORT_DSN env var.

    Returns:
        True if exported, False if graph not found in DB.

    Raises:
        RuntimeError: If PORT_DSN is not set.
    """
    path = Path(path)
    dsn = db_dsn or os.environ.get("PORT_DSN")
    if not dsn:
        raise RuntimeError("PORT_DSN not set — cannot export from database")

    try:
        trug = _read_from_postgres(path, dsn)
    except KeyError:
        return False
    except Exception as exc:
        raise RuntimeError(f"DB read failed for {path.parent.name}: {exc}") from exc

    with open(path, "w", encoding="utf-8") as fh:
        json.dump(trug, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return True


def import_trug(
    path: str | Path,
    *,
    db_dsn: Optional[str] = None,
) -> bool:
    """Import a JSON file into PostgreSQL.

    Reads the JSON file and writes it to the database via write_trug().

    Args:
        path: Source file path (e.g., TRUGS_AAA/folder.trug.json).
        db_dsn: PostgreSQL DSN. If None, reads PORT_DSN env var.

    Returns:
        True if imported successfully.

    Raises:
        RuntimeError: If PORT_DSN is not set.
        FileNotFoundError: If JSON file doesn't exist.
    """
    path = Path(path)
    dsn = db_dsn or os.environ.get("PORT_DSN")
    if not dsn:
        raise RuntimeError("PORT_DSN not set — cannot import to database")

    with open(path, "r", encoding="utf-8") as fh:
        trug = json.load(fh)

    write_trug(trug, path, db_dsn=dsn)
    return True
