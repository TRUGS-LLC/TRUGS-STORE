# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Runtime guards for the Postgres v2 dispatch path (AAA #1756 §"Postgres parity").

Closes AF-3 from AAA #1756 Phase 9 Final Audit by exercising:

1. v2-vocabulary load dispatch through `PostgresPersistence.load`
2. inherited metric_level stamping in `_save_v2` for in-memory stores
3. schema byte-equivalence before/after a v2 save
4. the documented invariant that `level_directives` is file-emission-only
   (never a schema column; round-trip as opaque JSONB metadata)
5. consumer-invoked `PostgresGraphStore.validate_graph()` runs the v2
   LEVEL_PREFIX hierarchy rules (deferred at load time per the
   `persistence/postgres.py:81-87` design comment)

All tests gate on `TRUGS_TEST_DSN` (the canonical env-var name used by
`conftest.py`, `test_postgres_persistence.py`, and `test_benchmarks.py`).
The CI `postgres-tests` job exports `TRUGS_TEST_DSN` so these tests
actually run; without that fix (landed in the same PR), they would
silent-skip — the precise failure mode AAA #1756 AF-3 calls out.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Iterator

import pytest

_PG_DSN = os.environ.get("TRUGS_TEST_DSN")
pytestmark = pytest.mark.skipif(not _PG_DSN, reason="TRUGS_TEST_DSN not set")


@pytest.fixture
def pg_conn() -> Iterator[Any]:
    import psycopg

    conn = psycopg.connect(_PG_DSN, autocommit=True)
    yield conn
    conn.close()


@pytest.fixture
def persistence(pg_conn: Any) -> Any:
    from trugs_store.persistence.postgres import PostgresPersistence

    p = PostgresPersistence(pg_conn)
    p.ensure_schema()
    return p


def _new_graph_id() -> str:
    return f"v2_test_{uuid.uuid4().hex[:8]}"


def _v2_store_with(
    nodes: list[dict[str, Any]] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> Any:
    """Build an InMemoryGraphStore declaring core_v2.0.0 vocabulary."""
    from trugs_store import InMemoryGraphStore

    store = InMemoryGraphStore()
    store.set_metadata("name", "v2_test_graph")
    store.set_metadata("version", "0.0.1")
    store.set_metadata("capabilities", {"vocabularies": ["core_v2.0.0"]})
    for key, value in (extra_metadata or {}).items():
        store.set_metadata(key, value)
    for node in nodes or []:
        parent_id = node.pop("_parent_id", None)
        store.add_node(node, parent_id=parent_id)
    return store


def _node(
    node_id: str,
    ntype: str = "ITEM",
    *,
    parent_id: str | None = None,
    metric_level: str | None = None,
    dimension: str = "test_dim",
) -> dict[str, Any]:
    n: dict[str, Any] = {
        "id": node_id,
        "type": ntype,
        "properties": {},
        "parent_id": None,
        "contains": [],
        "metric_level": metric_level,
        "dimension": dimension,
    }
    if parent_id is not None:
        n["_parent_id"] = parent_id
    return n


def test_postgres_load_v2_dispatches_to_v1_body(persistence: Any) -> None:
    """A v2-vocabulary TRUG saved + reloaded should classify as 'v2' on load."""
    from trugs_store.vocabulary import classify_vocabulary

    graph_id = _new_graph_id()
    store = _v2_store_with(nodes=[_node("root", "ROOT", metric_level="KILO_ROOT")])

    persistence.save(store, graph_id)
    loaded = persistence.load(graph_id)

    assert classify_vocabulary(loaded.get_metadata()) == "v2", (
        "Postgres load must round-trip the v2 vocabulary declaration so "
        "classify_vocabulary still returns 'v2' on the loaded store"
    )

    persistence.delete_graph(graph_id)


def test_postgres_save_v2_stamps_inherited_metric_level(persistence: Any) -> None:
    """`_save_v2` stamps a child node missing metric_level with one-step-finer prefix.

    Per `BaseGraph._stamp_inherited_metric_levels` (graph.py:124-180): for a
    parent at `KILO_FOLDER`, a child of type `DOCUMENT` missing metric_level
    is stamped `HECTO_DOCUMENT` (HECTO is one step finer than KILO in
    SI_PREFIX_ORDERING).
    """
    graph_id = _new_graph_id()
    store = _v2_store_with(
        nodes=[
            _node("parent", "FOLDER", metric_level="KILO_FOLDER"),
            _node("child", "DOCUMENT", parent_id="parent", metric_level=None),
        ]
    )

    persistence.save(store, graph_id)
    loaded = persistence.load(graph_id)
    child = loaded.get_node("child")

    assert child is not None
    assert child["metric_level"] == "HECTO_DOCUMENT", (
        f"v2 save should stamp child.metric_level as HECTO_DOCUMENT "
        f"(one step finer than parent KILO_FOLDER); got {child['metric_level']!r}"
    )

    persistence.delete_graph(graph_id)


def _capture_schema(pg_conn: Any) -> list[tuple[str, str, str, str]]:
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name IN ('graphs', 'nodes', 'edges') "
            "ORDER BY table_name, ordinal_position"
        )
        return [(r[0], r[1], r[2], r[3]) for r in cur.fetchall()]


def test_postgres_save_v2_preserves_schema(persistence: Any, pg_conn: Any) -> None:
    """A v2-path save must not mutate the Postgres schema."""
    graph_id = _new_graph_id()
    store = _v2_store_with(nodes=[_node("root", "ROOT", metric_level="KILO_ROOT")])

    before = _capture_schema(pg_conn)
    persistence.save(store, graph_id)
    after = _capture_schema(pg_conn)

    assert before == after, (
        f"v2 save mutated the schema. before={before!r}\nafter={after!r}"
    )

    persistence.delete_graph(graph_id)


def test_postgres_v2_round_trip_with_level_directives(
    persistence: Any, pg_conn: Any
) -> None:
    """`level_directives` is file-emission-only — never a Postgres schema column.

    Two invariants per AAA #1756 ADR + `persistence/postgres.py:170-173`:
    - No `level_directives` column exists in any of the public tables.
    - Round-tripping a v2 store with `level_directives` in its metadata
      preserves it as opaque JSONB (Postgres treats it as untyped meta,
      not as something it enforces or rejects).
    """
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND column_name = 'level_directives'"
        )
        directive_columns = list(cur.fetchall())
    assert directive_columns == [], (
        "level_directives is file-emission-only per AAA #1756 ADR; "
        f"found unexpected schema column(s): {directive_columns!r}"
    )

    graph_id = _new_graph_id()
    directives = ["KILO_ROOT", "HECTO_DOCUMENT"]
    store = _v2_store_with(
        nodes=[_node("root", "ROOT", metric_level="KILO_ROOT")],
        extra_metadata={"level_directives": directives},
    )

    persistence.save(store, graph_id)
    loaded = persistence.load(graph_id)

    assert loaded.get_metadata().get("level_directives") == directives, (
        "level_directives in input metadata should round-trip as opaque "
        "JSONB through the Postgres metadata column"
    )

    persistence.delete_graph(graph_id)


def test_postgres_v2_consumer_validate_graph_runs_rules(persistence: Any) -> None:
    """`PostgresGraphStore.validate_graph` runs v2 LEVEL_PREFIX rules.

    AAA #1756 Phase 3 ASSERTion: parent.metric_level must EXCEED child's in
    SI_PREFIX_ORDERING. Setup violates this — parent at BASE_FOLDER (idx 10),
    child at KILO_DOCUMENT (idx 7). KILO is coarser than BASE; parent does
    not exceed child → expect one Violation with rule='level_prefix_hierarchy'.
    """
    graph_id = _new_graph_id()
    store = _v2_store_with(
        nodes=[
            _node("parent", "FOLDER", metric_level="BASE_FOLDER"),
            _node(
                "child", "DOCUMENT", parent_id="parent", metric_level="KILO_DOCUMENT"
            ),
        ]
    )

    persistence.save(store, graph_id)
    loaded = persistence.load(graph_id)
    violations = loaded.validate_graph()

    level_prefix_violations = [
        v for v in violations if getattr(v, "rule", None) == "level_prefix_hierarchy"
    ]
    assert level_prefix_violations, (
        "PostgresGraphStore.validate_graph on a v2 TRUG with an invalid "
        "hierarchy must surface a level_prefix_hierarchy Violation; got "
        f"violations={violations!r}"
    )
    assert level_prefix_violations[0].severity == "error", (
        f"Expected severity='error'; got {level_prefix_violations[0].severity!r}"
    )

    persistence.delete_graph(graph_id)
