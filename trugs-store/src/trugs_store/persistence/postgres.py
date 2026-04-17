"""PostgreSQL persistence — load/save graphs to/from PostgreSQL."""

from __future__ import annotations

import importlib.resources
from typing import Any

try:
    import psycopg
    from psycopg.types.json import Json
except ImportError as e:
    raise ImportError(
        "PostgreSQL support requires psycopg3: pip install trugs-store[postgres]"
    ) from e

from trugs_store.postgres import PostgresGraphStore
from trugs_store.types import Node


# AGENT claude SHALL DEFINE RECORD PostgresPersistence AS A RECORD persistence.
class PostgresPersistence:
    """Load and save TRUGS graphs to/from PostgreSQL.

    Uses COPY protocol for bulk operations (>100K nodes/sec).
    """

    def __init__(self, conn: "psycopg.Connection") -> None:
        self._conn = conn

    # PROCESS ensure_schema SHALL WRITE RECORD schema TO DATA database.
    def ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist. Idempotent."""
        schema_sql = (
            importlib.resources.files("trugs_store")
            .joinpath("schema.sql")
            .read_text(encoding="utf-8")
        )
        with self._conn.cursor() as cur:
            cur.execute(schema_sql)
        self._conn.commit()

    # PROCESS load SHALL READ RECORD graph THEN RETURN RECORD store.
    def load(self, graph_id: str) -> PostgresGraphStore:
        """Load a graph by graph_id. Returns a PostgresGraphStore scoped to it.

        Raises KeyError if graph_id does not exist.
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT 1 FROM graphs WHERE graph_id = %s", (graph_id,))
            if not cur.fetchone():
                raise KeyError(f"Graph {graph_id!r} does not exist")
        return PostgresGraphStore(self._conn, graph_id)

    # PROCESS save SHALL WRITE RECORD store TO DATA database.
    def save(self, store: Any, graph_id: str) -> None:
        """Persist a GraphStore's state to PostgreSQL under graph_id.

        Uses COPY protocol for bulk node/edge insertion.
        Replace semantics — deletes existing data for graph_id first.
        Single transaction — all-or-nothing.
        """
        metadata = store.get_metadata()
        nodes = store.find_nodes()
        edges = store.get_edges()

        with self._conn.transaction():
            with self._conn.cursor() as cur:
                # Delete existing graph data (if any)
                cur.execute("DELETE FROM edges WHERE graph_id = %s", (graph_id,))
                cur.execute("DELETE FROM nodes WHERE graph_id = %s", (graph_id,))
                cur.execute("DELETE FROM graphs WHERE graph_id = %s", (graph_id,))

                # Insert graph metadata
                cur.execute(
                    "INSERT INTO graphs (graph_id, name, version, type, description, metadata) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        graph_id,
                        metadata.get("name", graph_id),
                        metadata.get("version", "1.0.0"),
                        metadata.get("type"),
                        metadata.get("description"),
                        Json({
                            k: v for k, v in metadata.items()
                            if k not in ("name", "version", "type", "description")
                        }),
                    ),
                )

                # Bulk insert nodes via COPY
                if nodes:
                    with cur.copy(
                        "COPY nodes (graph_id, id, type, properties, metric_level, parent_id, contains, dimension) "
                        "FROM STDIN"
                    ) as copy:
                        for node in nodes:
                            copy.write_row((
                                graph_id,
                                node["id"],
                                node.get("type", ""),
                                Json(node.get("properties", {})),
                                node.get("metric_level"),
                                node.get("parent_id"),
                                node.get("contains", []),
                                node.get("dimension"),
                            ))

                # Bulk insert edges via COPY
                if edges:
                    with cur.copy(
                        "COPY edges (graph_id, from_id, to_id, relation, weight, properties) "
                        "FROM STDIN"
                    ) as copy:
                        for edge in edges:
                            copy.write_row((
                                graph_id,
                                edge["from_id"],
                                edge["to_id"],
                                edge["relation"],
                                edge.get("weight", 1.0),
                                Json(edge.get("properties", {})),
                            ))

    # PROCESS list_graphs SHALL FILTER ALL RECORD graph THEN RETURN RECORD result.
    def list_graphs(self) -> list[dict]:
        """Return all graphs with graph_id, name, version."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT graph_id, name, version FROM graphs ORDER BY graph_id")
            return [{"graph_id": r[0], "name": r[1], "version": r[2]} for r in cur.fetchall()]

    # PROCESS delete_graph SHALL REJECT RECORD graph.
    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph and all its nodes/edges. Returns True if existed."""
        with self._conn.cursor() as cur:
            cur.execute("DELETE FROM graphs WHERE graph_id = %s RETURNING graph_id", (graph_id,))
            deleted = cur.fetchone() is not None
        self._conn.commit()
        return deleted
