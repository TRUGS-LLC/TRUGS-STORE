# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Round-trip identity — store ∘ retrieve = identity across all three backends.

Verifies ASSERT-4 (AAA #2330): `round_trip_identity SHALL HOLD 'across
in_memory AND json_file AND postgres backend` — the load-bearing L3 contract.

A graph persisted and reloaded preserves its node and edge sets; re-emission
reaches a byte-stable fixed point. (The *first* v2 save normalizes — stamps
inherited `metric_level` + emits `level_directives` — so identity for v2 is the
idempotent fixed point of the second round-trip, matching
`test_canonical_reemit.test_v2_second_round_trip_idempotent`.)

The Postgres leg gates on `TRUGS_TEST_DSN`; CI's must-run guard (store-dev#16)
ensures it is not silently skipped there.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

import pytest

from trugs_store import InMemoryGraphStore, JsonFilePersistence

_FIXTURES = Path(__file__).parent / "fixtures"
_PG_DSN = os.environ.get("TRUGS_TEST_DSN")

# v1 corpus (no v2 vocabulary declared) — round-trips byte-for-byte.
V1_CORPUS: dict[str, Any] = json.loads((_FIXTURES / "sample.trug.json").read_text())

# v2 corpus — declares core_v2.0.0; uses known SI prefixes with a valid
# parent-coarser-than-child hierarchy (KILO_FOLDER > BASE_DOCUMENT).
V2_CORPUS: dict[str, Any] = {
    "name": "RoundTrip v2 Corpus",
    "version": "2.0.0",
    "type": "PROJECT",
    "description": "v2 round-trip fixture",
    "capabilities": {"vocabularies": ["core_v2.0.0"]},
    "dimensions": {"d": {"description": "dim", "base_level": "BASE"}},
    "nodes": [
        {
            "id": "root",
            "type": "FOLDER",
            "properties": {"name": "root"},
            "parent_id": None,
            "contains": ["leaf"],
            "metric_level": "KILO_FOLDER",
            "dimension": "d",
        },
        {
            "id": "leaf",
            "type": "DOCUMENT",
            "properties": {"name": "leaf"},
            "parent_id": "root",
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "d",
        },
    ],
    "edges": [{"from_id": "root", "to_id": "leaf", "relation": "contains"}],
}

_CORPORA = [pytest.param(V1_CORPUS, id="v1"), pytest.param(V2_CORPUS, id="v2")]


def _build(corpus: dict[str, Any]) -> InMemoryGraphStore:
    """Faithfully load a corpus into an InMemoryGraphStore (no mutation)."""
    store = InMemoryGraphStore()
    for key, value in corpus.items():
        if key not in ("nodes", "edges"):
            store.set_metadata(key, value)
    for node in corpus["nodes"]:
        store._nodes[node["id"]] = node
    for edge in corpus.get("edges", []):
        store._edges.append(edge)
    return store


def _node_ids(store: Any) -> set[str]:
    return {n["id"] for n in store.find_nodes()}


def _edge_set(store: Any) -> set[tuple]:
    return {
        (e.get("from_id"), e.get("to_id"), e.get("relation")) for e in store.get_edges()
    }


def _snapshot(store: Any) -> tuple:
    nodes = {n["id"]: n for n in store.find_nodes()}
    return (nodes, sorted(_edge_set(store)))


# --- in_memory backend ------------------------------------------------------


@pytest.mark.parametrize("corpus", _CORPORA)
def test_in_memory_holds_graph(corpus: dict[str, Any]) -> None:
    """The in-memory store retrieves exactly the node/edge sets put in."""
    store = _build(corpus)
    assert _node_ids(store) == {n["id"] for n in corpus["nodes"]}
    assert _edge_set(store) == {
        (e.get("from_id"), e.get("to_id"), e.get("relation"))
        for e in corpus.get("edges", [])
    }


# --- json_file backend ------------------------------------------------------


@pytest.mark.parametrize("corpus", _CORPORA)
def test_json_file_round_trip_identity(corpus: dict[str, Any], tmp_path: Path) -> None:
    p1 = tmp_path / "rt1.trug.json"
    p2 = tmp_path / "rt2.trug.json"
    persistence = JsonFilePersistence()

    persistence.save(_build(corpus), str(p1))
    s1 = persistence.load(str(p1))
    persistence.save(s1, str(p2))
    s2 = persistence.load(str(p2))

    # No nodes/edges lost relative to the source corpus.
    assert _node_ids(s1) == {n["id"] for n in corpus["nodes"]}
    # Re-emission is a byte-stable fixed point.
    assert p1.read_text() == p2.read_text(), "json re-emit is not byte-idempotent"
    # And the reloaded graphs are identical.
    assert _snapshot(s1) == _snapshot(s2)


# --- postgres backend -------------------------------------------------------


@pytest.mark.skipif(not _PG_DSN, reason="TRUGS_TEST_DSN not set")
@pytest.mark.parametrize("corpus", _CORPORA)
def test_postgres_round_trip_identity(corpus: dict[str, Any]) -> None:
    import psycopg

    from trugs_store.persistence.postgres import PostgresPersistence

    conn = psycopg.connect(_PG_DSN, autocommit=True)
    try:
        persistence = PostgresPersistence(conn)
        persistence.ensure_schema()
        graph_id = f"rt_{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graphs (graph_id, name, version) VALUES (%s, %s, %s)",
                (graph_id, corpus["name"], corpus["version"]),
            )
        try:
            persistence.save(_build(corpus), graph_id)
            loaded = persistence.load(graph_id)
            assert _node_ids(loaded) == {n["id"] for n in corpus["nodes"]}
            assert _edge_set(loaded) == {
                (e.get("from_id"), e.get("to_id"), e.get("relation"))
                for e in corpus.get("edges", [])
            }
        finally:
            persistence.delete_graph(graph_id)
    finally:
        conn.close()
