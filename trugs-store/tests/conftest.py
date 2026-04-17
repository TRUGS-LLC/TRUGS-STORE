"""Shared fixtures for trugs-store tests."""

import os
import uuid

import pytest

from trugs_store import InMemoryGraphStore

# PostgreSQL DSN — set to enable postgres backend tests
_PG_DSN = os.environ.get("TRUGS_TEST_DSN")

_BACKENDS = ["memory"]
if _PG_DSN:
    _BACKENDS.append("postgres")


def _make_node(nid, ntype="ITEM", dimension="test_dim", metric_level="BASE_ITEM", **extra_props):
    return {
        "id": nid, "type": ntype, "properties": extra_props,
        "parent_id": None, "contains": [], "metric_level": metric_level,
        "dimension": dimension,
    }


# AGENT claude SHALL DEFINE RECORD store AS A RECORD fixture.
@pytest.fixture(params=_BACKENDS)
def store(request):
    """Yield a fresh empty GraphStore for each backend."""
    if request.param == "memory":
        yield InMemoryGraphStore()
    elif request.param == "postgres":
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        from trugs_store.postgres import PostgresGraphStore

        conn = psycopg.connect(_PG_DSN, autocommit=True)
        persistence = PostgresPersistence(conn)
        persistence.ensure_schema()
        graph_id = f"test_{uuid.uuid4().hex[:8]}"

        # Create the graph row so set_metadata works
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO graphs (graph_id, name, version) VALUES (%s, %s, %s)",
                (graph_id, "test", "1.0.0"),
            )

        pg_store = PostgresGraphStore(conn, graph_id)
        yield pg_store

        # Cleanup
        persistence.delete_graph(graph_id)
        conn.close()


# AGENT claude SHALL DEFINE RECORD populated_store AS A RECORD fixture.
@pytest.fixture
def populated_store(store):
    store.set_metadata("name", "test_graph")
    store.set_metadata("version", "1.0.0")
    store.set_metadata("dimensions", {"test_dim": {"description": "Test dimension", "base_level": "BASE"}})
    store.add_node(_make_node("root", "ROOT", metric_level="KILO_ROOT"))
    for i in range(3):
        store.add_node(_make_node(f"child_{i}", "CHILD", status=f"status_{i}"), parent_id="root")
    store.add_edge({"from_id": "child_0", "to_id": "child_1", "relation": "DEPENDS_ON"})
    store.add_edge({"from_id": "child_1", "to_id": "child_2", "relation": "DEPENDS_ON", "weight": 0.8, "properties": {"note": "important"}})
    return store
