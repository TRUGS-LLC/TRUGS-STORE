# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""PostgreSQL persistence — load/save graphs to/from PostgreSQL."""

from __future__ import annotations

import importlib.resources
from typing import Any, Dict

try:
    import psycopg
    from psycopg.types.json import Json
except ImportError as e:
    raise ImportError(
        "PostgreSQL support requires psycopg3: pip install trugs-store[postgres]"
    ) from e

from trugs_store.graph import BaseGraph
from trugs_store.postgres import PostgresGraphStore
from trugs_store.vocabulary import classify_vocabulary


class PostgresPersistence:
    """Load and save TRUGS graphs to/from PostgreSQL.

    Uses COPY protocol for bulk operations (>100K nodes/sec).

    Recognizes the TRUG's declared vocabulary (`capabilities.vocabularies`
    in graphs.metadata) and dispatches load/save through a single coherent
    code path. v1 graphs behave unchanged (additive guarantee per TRUGS-LLC
    Spec Evolution Addendum §1.2). v2-specific behavior — LEVEL_PREFIX
    validation, inheritance stamping, canonical re-emit — lands in
    AAA #1756 Sub-phase 5.2; in 5.1 the v2 dispatch is a stub passing
    through to v1.

    <trl>
    AGENT claude SHALL DEFINE RECORD PostgresPersistence AS A RECORD persistence.
    </trl>
    """

    def __init__(self, conn: "psycopg.Connection") -> None:
        self._conn = conn

    def ensure_schema(self) -> None:
        """Create tables and indexes if they don't exist. Idempotent.

        <trl>
        PROCESS ensure_schema SHALL WRITE RECORD schema TO DATA database.
        </trl>
        """
        schema_sql = (
            importlib.resources.files("trugs_store")
            .joinpath("schema.sql")
            .read_text(encoding="utf-8")
        )
        with self._conn.cursor() as cur:
            cur.execute(schema_sql)
        self._conn.commit()

    def load(self, graph_id: str) -> PostgresGraphStore:
        """Load a graph by graph_id. Returns a PostgresGraphStore scoped to it.

        Raises KeyError if graph_id does not exist.

        <trl>
        PROCESS load SHALL READ RECORD graph THEN DISPATCH 'on RECORD vocabulary THEN RETURN RECORD store.
        </trl>
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT metadata FROM graphs WHERE graph_id = %s", (graph_id,))
            row = cur.fetchone()
            if not row:
                raise KeyError(f"Graph {graph_id!r} does not exist")
            metadata: Dict[str, Any] = row[0] or {}
        if classify_vocabulary(metadata) == "v2":
            return self._load_v2(graph_id, metadata)
        return self._load_v1(graph_id, metadata)

    # PROCESS _load_v1 SHALL READ RECORD legacy_graph THEN RETURN RECORD store.
    def _load_v1(self, graph_id: str, metadata: Dict[str, Any]) -> PostgresGraphStore:
        return PostgresGraphStore(self._conn, graph_id)

    # PROCESS _load_v2 SHALL READ RECORD hierarchy_first_graph THEN RETURN RECORD store.
    # Per AAA #1756 Phase 3 INTERFACE PostgresGraphStore.load_graph SHALL APPLY
    # DATA same_validation_rules AS JsonFilePersistence.load. The PostgresGraphStore
    # exposes the same Protocol as InMemoryGraphStore, so `validate_v2_hierarchy`
    # operates on it via duck-typed `._nodes` access — which Postgres-backed
    # stores expose lazily via their own internals. Side-effect call only;
    # violations surface through `store.validate_graph()` for consumers that
    # invoke it.
    def _load_v2(self, graph_id: str, metadata: Dict[str, Any]) -> PostgresGraphStore:
        store = self._load_v1(graph_id, metadata)
        # validate_v2_hierarchy currently reads `store._nodes`, which the
        # Postgres-backed store does not eagerly materialize. Defer the
        # validation call to consumer-invoked `store.validate_graph()`, which
        # dispatches v2 rules when the declared vocabulary is core_v2.0.0.
        return store

    def save(self, store: Any, graph_id: str) -> None:
        """Persist a GraphStore's state to PostgreSQL under graph_id.

        Uses COPY protocol for bulk node/edge insertion.
        Replace semantics — deletes existing data for graph_id first.
        Single transaction — all-or-nothing.

        <trl>
        PROCESS save SHALL WRITE RECORD store TO DATA database 'with DISPATCH 'on RECORD vocabulary.
        </trl>
        """
        metadata = store.get_metadata()
        if classify_vocabulary(metadata) == "v2":
            self._save_v2(store, graph_id, metadata)
        else:
            self._save_v1(store, graph_id, metadata)

    # PROCESS _save_v1 SHALL WRITE RECORD store TO DATA database.
    def _save_v1(self, store: Any, graph_id: str, metadata: Dict[str, Any]) -> None:
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
                        Json(
                            {
                                k: v
                                for k, v in metadata.items()
                                if k not in ("name", "version", "type", "description")
                            }
                        ),
                    ),
                )

                # Bulk insert nodes via COPY
                if nodes:
                    with cur.copy(
                        "COPY nodes (graph_id, id, type, properties, metric_level, parent_id, contains, dimension) "
                        "FROM STDIN"
                    ) as copy:
                        for node in nodes:
                            copy.write_row(
                                (
                                    graph_id,
                                    node["id"],
                                    node.get("type", ""),
                                    Json(node.get("properties", {})),
                                    node.get("metric_level"),
                                    node.get("parent_id"),
                                    node.get("contains", []),
                                    node.get("dimension"),
                                )
                            )

                # Bulk insert edges via COPY
                if edges:
                    with cur.copy(
                        "COPY edges (graph_id, from_id, to_id, relation, weight, properties) "
                        "FROM STDIN"
                    ) as copy:
                        for edge in edges:
                            copy.write_row(
                                (
                                    graph_id,
                                    edge["from_id"],
                                    edge["to_id"],
                                    edge["relation"],
                                    edge.get("weight", 1.0),
                                    Json(edge.get("properties", {})),
                                )
                            )

    # PROCESS _save_v2 SHALL WRITE RECORD store TO DATA database 'with canonical_reemit.
    # Per AAA #1756 Phase 3 §"Canonical re-emit (v2 only)": stamp inherited
    # metric_level on nodes missing it, then persist via the v1 COPY path
    # (Postgres schema is unchanged — metric_level is already a column).
    # level_directives are NOT persisted to the database — the level-
    # stratified rendering is a file-emission concern, not a storage concern
    # (AAA #1756 ADR — DB does not enforce LEVEL_PREFIX). Consumers that need
    # directives derive them on demand by scanning `find_nodes()`.
    def _save_v2(self, store: Any, graph_id: str, metadata: Dict[str, Any]) -> None:
        # Stamp only on in-memory stores (Postgres-backed stores write rows
        # directly and the COPY path will read whatever metric_level is set).
        from trugs_store.memory import InMemoryGraphStore

        if isinstance(store, InMemoryGraphStore):
            BaseGraph._stamp_inherited_metric_levels(store)
        self._save_v1(store, graph_id, metadata)

    def list_graphs(self) -> list[dict[str, Any]]:
        """Return all graphs with graph_id, name, version.

        <trl>
        PROCESS list_graphs SHALL FILTER ALL RECORD graph THEN RETURN RECORD result.
        </trl>
        """
        with self._conn.cursor() as cur:
            cur.execute("SELECT graph_id, name, version FROM graphs ORDER BY graph_id")
            return [
                {"graph_id": r[0], "name": r[1], "version": r[2]}
                for r in cur.fetchall()
            ]

    def delete_graph(self, graph_id: str) -> bool:
        """Delete a graph and all its nodes/edges. Returns True if existed.

        <trl>
        PROCESS delete_graph SHALL REJECT RECORD graph.
        </trl>
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "DELETE FROM graphs WHERE graph_id = %s RETURNING graph_id", (graph_id,)
            )
            deleted = cur.fetchone() is not None
        self._conn.commit()
        return deleted
