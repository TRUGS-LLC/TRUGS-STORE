"""PostgreSQL GraphStore implementation using psycopg3."""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterator, List, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Json
except ImportError as e:
    raise ImportError(
        "PostgreSQL support requires psycopg3: pip install trugs-store[postgres]"
    ) from e

from trugs_store.protocol import Violation
from trugs_store.types import Edge, Node

_MAX_ANCESTOR_DEPTH = 100


class PostgresGraphStore:
    """PostgreSQL-backed GraphStore — indexed queries, transactional writes.

    Each instance is scoped to a single graph_id. All queries include
    a graph_id filter so multiple graphs coexist in the same database.

    Each write method is a self-contained transaction (auto-commit).
    """

    def __init__(self, conn: "psycopg.Connection", graph_id: str) -> None:
        self._conn = conn
        self._graph_id = graph_id

    # === Node Read ===

    def get_node(self, node_id: str) -> Optional[Node]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, type, properties, metric_level, parent_id, contains, dimension "
                "FROM nodes WHERE graph_id = %s AND id = %s",
                (self._graph_id, node_id),
            )
            row = cur.fetchone()
            return _row_to_node(row) if row else None

    def get_children(self, parent_id: str) -> List[Node]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, type, properties, metric_level, parent_id, contains, dimension "
                "FROM nodes WHERE graph_id = %s AND parent_id = %s",
                (self._graph_id, parent_id),
            )
            return [_row_to_node(r) for r in cur.fetchall()]

    def find_nodes(
        self,
        *,
        type: Optional[str] = None,
        status: Optional[str] = None,
        stale: Optional[bool] = None,
        dimension: Optional[str] = None,
    ) -> List[Node]:
        clauses = ["graph_id = %s"]
        params: list[Any] = [self._graph_id]
        if type is not None:
            clauses.append("type = %s")
            params.append(type)
        if status is not None:
            clauses.append("properties->>'status' = %s")
            params.append(status)
        if stale is not None:
            if stale:
                clauses.append("(properties->>'stale')::boolean IS TRUE")
            else:
                clauses.append("(properties->>'stale' IS NULL OR (properties->>'stale')::boolean IS NOT TRUE)")
        if dimension is not None:
            clauses.append("dimension = %s")
            params.append(dimension)
        where = " AND ".join(clauses)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT id, type, properties, metric_level, parent_id, contains, dimension "
                f"FROM nodes WHERE {where}",
                params,
            )
            return [_row_to_node(r) for r in cur.fetchall()]

    def node_count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM nodes WHERE graph_id = %s", (self._graph_id,))
            return cur.fetchone()[0]

    # === Node Write ===

    def add_node(self, node: Node, *, parent_id: Optional[str] = None) -> None:
        nid = node["id"]
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                # Check duplicate
                cur.execute(
                    "SELECT 1 FROM nodes WHERE graph_id = %s AND id = %s",
                    (self._graph_id, nid),
                )
                if cur.fetchone():
                    raise ValueError(f"Node {nid!r} already exists")

                if parent_id is not None:
                    # Check parent exists
                    cur.execute(
                        "SELECT 1 FROM nodes WHERE graph_id = %s AND id = %s",
                        (self._graph_id, parent_id),
                    )
                    if not cur.fetchone():
                        raise KeyError(f"Parent {parent_id!r} does not exist")

                    # Cycle detection via recursive CTE
                    cur.execute(
                        """
                        WITH RECURSIVE ancestors AS (
                            SELECT id, parent_id, 1 AS depth
                            FROM nodes WHERE graph_id = %s AND id = %s
                            UNION ALL
                            SELECT n.id, n.parent_id, a.depth + 1
                            FROM nodes n
                            JOIN ancestors a ON n.id = a.parent_id AND n.graph_id = %s
                            WHERE a.depth < %s
                        )
                        SELECT 1 FROM ancestors WHERE id = %s LIMIT 1
                        """,
                        (self._graph_id, parent_id, self._graph_id, _MAX_ANCESTOR_DEPTH, nid),
                    )
                    if cur.fetchone():
                        raise ValueError(f"Adding {nid!r} under {parent_id!r} would create a cycle")

                    node["parent_id"] = parent_id

                    # Update parent contains using array_append (atomic)
                    cur.execute(
                        "UPDATE nodes SET contains = array_append(contains, %s) "
                        "WHERE graph_id = %s AND id = %s AND NOT (%s = ANY(contains))",
                        (nid, self._graph_id, parent_id, nid),
                    )

                    # Create CONTAINS edge
                    cur.execute(
                        "INSERT INTO edges (graph_id, from_id, to_id, relation) "
                        "VALUES (%s, %s, %s, 'contains') ON CONFLICT DO NOTHING",
                        (self._graph_id, parent_id, nid),
                    )

                # Insert node
                cur.execute(
                    "INSERT INTO nodes (graph_id, id, type, properties, metric_level, parent_id, contains, dimension) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        self._graph_id,
                        nid,
                        node.get("type", ""),
                        Json(node.get("properties", {})),
                        node.get("metric_level"),
                        node.get("parent_id"),
                        node.get("contains", []),
                        node.get("dimension"),
                    ),
                )

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET properties = properties || %s::jsonb "
                "WHERE graph_id = %s AND id = %s RETURNING id",
                (Json(properties), self._graph_id, node_id),
            )
            if not cur.fetchone():
                raise KeyError(f"Node {node_id!r} does not exist")
        self._conn.commit()

    def mark_stale(self, node_id: str, reason: str) -> None:
        self.update_node(node_id, {"stale": True, "stale_reason": reason})

    def clear_stale(self, node_id: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE nodes SET properties = properties - 'stale' - 'stale_reason' "
                "WHERE graph_id = %s AND id = %s RETURNING id",
                (self._graph_id, node_id),
            )
            if not cur.fetchone():
                raise KeyError(f"Node {node_id!r} does not exist")
        self._conn.commit()

    def delete_node(self, node_id: str, *, cascade: bool = False) -> None:
        with self._conn.transaction():
            with self._conn.cursor() as cur:
                # Check exists
                cur.execute(
                    "SELECT contains, parent_id FROM nodes WHERE graph_id = %s AND id = %s",
                    (self._graph_id, node_id),
                )
                row = cur.fetchone()
                if not row:
                    raise KeyError(f"Node {node_id!r} does not exist")

                contains, parent_id = row
                if contains and not cascade:
                    raise ValueError(f"Node {node_id!r} has children {contains}; use cascade=True")

                if cascade:
                    # Collect all descendants via recursive CTE
                    cur.execute(
                        """
                        WITH RECURSIVE descendants AS (
                            SELECT id FROM nodes WHERE graph_id = %s AND id = %s
                            UNION ALL
                            SELECT n.id FROM nodes n
                            JOIN descendants d ON n.parent_id = d.id AND n.graph_id = %s
                        )
                        SELECT id FROM descendants
                        """,
                        (self._graph_id, node_id, self._graph_id),
                    )
                    to_delete = [r[0] for r in cur.fetchall()]
                else:
                    to_delete = [node_id]

                # Remove from parent's contains
                if parent_id:
                    cur.execute(
                        "UPDATE nodes SET contains = array_remove(contains, %s) "
                        "WHERE graph_id = %s AND id = %s",
                        (node_id, self._graph_id, parent_id),
                    )

                # Delete edges involving any deleted node
                cur.execute(
                    "DELETE FROM edges WHERE graph_id = %s AND (from_id = ANY(%s) OR to_id = ANY(%s))",
                    (self._graph_id, to_delete, to_delete),
                )

                # Delete nodes
                cur.execute(
                    "DELETE FROM nodes WHERE graph_id = %s AND id = ANY(%s)",
                    (self._graph_id, to_delete),
                )

    # === Edge Read ===

    def get_edges(
        self,
        *,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> List[Edge]:
        clauses = ["graph_id = %s"]
        params: list[Any] = [self._graph_id]
        if from_id is not None:
            clauses.append("from_id = %s")
            params.append(from_id)
        if to_id is not None:
            clauses.append("to_id = %s")
            params.append(to_id)
        if relation is not None:
            clauses.append("relation = %s")
            params.append(relation)
        where = " AND ".join(clauses)
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"SELECT from_id, to_id, relation, weight, properties FROM edges WHERE {where}",
                params,
            )
            return [_row_to_edge(r) for r in cur.fetchall()]

    def get_outgoing(self, node_id: str) -> List[Edge]:
        return self.get_edges(from_id=node_id)

    def get_incoming(self, node_id: str) -> List[Edge]:
        return self.get_edges(to_id=node_id)

    def edge_count(self) -> int:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM edges WHERE graph_id = %s", (self._graph_id,))
            return cur.fetchone()[0]

    # === Edge Write ===

    def add_edge(self, edge: Edge) -> None:
        fid, tid, rel = edge["from_id"], edge["to_id"], edge["relation"]

        with self._conn.cursor() as cur:
            # Validate local endpoints (skip cross-graph refs with ':')
            if ":" not in fid:
                cur.execute("SELECT 1 FROM nodes WHERE graph_id = %s AND id = %s", (self._graph_id, fid))
                if not cur.fetchone():
                    raise KeyError(f"from_id {fid!r} does not exist")
            if ":" not in tid:
                cur.execute("SELECT 1 FROM nodes WHERE graph_id = %s AND id = %s", (self._graph_id, tid))
                if not cur.fetchone():
                    raise KeyError(f"to_id {tid!r} does not exist")

            cur.execute(
                "INSERT INTO edges (graph_id, from_id, to_id, relation, weight, properties) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (
                    self._graph_id, fid, tid, rel,
                    edge.get("weight", 1.0),
                    Json(edge.get("properties", {})),
                ),
            )
        self._conn.commit()

    def update_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        *,
        properties: Optional[Dict[str, Any]] = None,
        weight: Optional[float] = None,
    ) -> None:
        sets: list[str] = []
        params: list[Any] = []
        if properties is not None:
            sets.append("properties = %s")
            params.append(Json(properties))
        if weight is not None:
            sets.append("weight = %s")
            params.append(weight)
        if not sets:
            return
        params.extend([self._graph_id, from_id, to_id, relation])
        with self._conn.cursor() as cur:
            cur.execute(
                f"UPDATE edges SET {', '.join(sets)} "
                "WHERE graph_id = %s AND from_id = %s AND to_id = %s AND relation = %s "
                "RETURNING from_id",
                params,
            )
            if not cur.fetchone():
                raise KeyError(f"Edge ({from_id!r}, {to_id!r}, {relation!r}) does not exist")
        self._conn.commit()

    def remove_edge(self, from_id: str, to_id: str, relation: str) -> bool:
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM edges WHERE graph_id = %s AND from_id = %s AND to_id = %s AND relation = %s "
                "RETURNING from_id",
                (self._graph_id, from_id, to_id, relation),
            )
            removed = cur.fetchone() is not None
        self._conn.commit()
        return removed

    # === Traversal ===

    def traverse(
        self,
        start_id: str,
        *,
        direction: str = "outgoing",
        relation: Optional[str] = None,
        max_depth: int = 1,
    ) -> Iterator[tuple[Node, Edge, int]]:
        # Verify start exists
        if self.get_node(start_id) is None:
            raise KeyError(f"Start node {start_id!r} does not exist")

        # BFS using iterative queries (simpler than recursive CTE for lazy iteration)
        visited = {start_id}
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])

        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue

            edges: List[Edge] = []
            if direction in ("outgoing", "both"):
                edges.extend(self.get_outgoing(current_id))
            if direction in ("incoming", "both"):
                edges.extend(self.get_incoming(current_id))

            for edge in edges:
                if relation is not None and edge["relation"] != relation:
                    continue
                neighbor_id = edge["to_id"] if edge["from_id"] == current_id else edge["from_id"]
                if neighbor_id in visited:
                    continue
                neighbor = self.get_node(neighbor_id)
                if neighbor is None:
                    continue
                visited.add(neighbor_id)
                yield (neighbor, edge, depth + 1)
                queue.append((neighbor_id, depth + 1))

    def get_neighbors(self, node_id: str, *, direction: str = "both") -> List[Node]:
        return [node for node, _e, _d in self.traverse(node_id, direction=direction, max_depth=1)]

    # === Subgraph ===

    def extract_subgraph(self, node_ids: List[str]) -> "GraphStore":
        """Extract subgraph into an InMemoryGraphStore (subgraphs are small)."""
        from trugs_store.memory import InMemoryGraphStore
        from copy import deepcopy

        sub = InMemoryGraphStore()
        sub._metadata = deepcopy(dict(self.get_metadata()))

        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id, type, properties, metric_level, parent_id, contains, dimension "
                "FROM nodes WHERE graph_id = %s AND id = ANY(%s)",
                (self._graph_id, list(node_ids)),
            )
            for row in cur.fetchall():
                sub._nodes[row["id"]] = _row_to_node(row)

            cur.execute(
                "SELECT from_id, to_id, relation, weight, properties "
                "FROM edges WHERE graph_id = %s AND from_id = ANY(%s) AND to_id = ANY(%s)",
                (self._graph_id, list(node_ids), list(node_ids)),
            )
            for row in cur.fetchall():
                sub._edges.append(_row_to_edge(row))

        sub._rebuild_edge_indexes()
        return sub

    # === Metadata ===

    def get_metadata(self) -> Dict[str, Any]:
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT name, version, type, description, metadata "
                "FROM graphs WHERE graph_id = %s",
                (self._graph_id,),
            )
            row = cur.fetchone()
            if not row:
                return {}
            result = dict(row.get("metadata", {}) or {})
            for k in ("name", "version", "type", "description"):
                if row.get(k) is not None:
                    result[k] = row[k]
            return result

    _GRAPH_COLUMNS = {"name", "version", "type", "description"}
    _GRAPH_COLUMN_SQL = {
        "name": "UPDATE graphs SET name = %s WHERE graph_id = %s",
        "version": "UPDATE graphs SET version = %s WHERE graph_id = %s",
        "type": "UPDATE graphs SET type = %s WHERE graph_id = %s",
        "description": "UPDATE graphs SET description = %s WHERE graph_id = %s",
    }

    def set_metadata(self, key: str, value: Any) -> None:
        # Top-level graph columns — use pre-built SQL (no f-string interpolation)
        if key in self._GRAPH_COLUMNS:
            with self._conn.cursor() as cur:
                cur.execute(self._GRAPH_COLUMN_SQL[key], (value, self._graph_id))
            self._conn.commit()
        else:
            with self._conn.cursor() as cur:
                cur.execute(
                    "UPDATE graphs SET metadata = jsonb_set(metadata, %s, %s::jsonb) "
                    "WHERE graph_id = %s",
                    ([key], Json(value), self._graph_id),
                )
            self._conn.commit()

    # === Validation ===

    def validate_graph(self) -> List[Violation]:
        """Validate by loading into memory and delegating.

        For v1, this is simpler and correct. Optimize with SQL queries
        in a future version if performance matters at scale.
        """
        from trugs_store.memory import InMemoryGraphStore

        mem = InMemoryGraphStore()
        mem._metadata = self.get_metadata()
        for node in self.find_nodes():
            mem._nodes[node["id"]] = node
        for edge in self.get_edges():
            mem._edges.append(edge)
        mem._rebuild_edge_indexes()
        return mem.validate_graph()


# ---------------------------------------------------------------------------
# Row conversion helpers
# ---------------------------------------------------------------------------

def _row_to_node(row: dict) -> Node:
    """Convert a psycopg dict_row to a TRUGS Node dict."""
    node: Node = {
        "id": row["id"],
        "type": row["type"],
        "properties": row.get("properties") or {},
        "metric_level": row.get("metric_level"),
        "parent_id": row.get("parent_id"),
        "contains": list(row.get("contains") or []),
        "dimension": row.get("dimension"),
    }
    return node


def _row_to_edge(row: dict) -> Edge:
    """Convert a psycopg dict_row to a TRUGS Edge dict."""
    edge: Edge = {
        "from_id": row["from_id"],
        "to_id": row["to_id"],
        "relation": row["relation"],
    }
    weight = row.get("weight")
    if weight is not None:
        edge["weight"] = weight
    props = row.get("properties")
    if props:
        edge["properties"] = props
    return edge
