"""Tests for PostgresPersistence — requires TRUGS_TEST_DSN."""

import os
import uuid

import pytest

_PG_DSN = os.environ.get("TRUGS_TEST_DSN")
pytestmark = pytest.mark.skipif(not _PG_DSN, reason="TRUGS_TEST_DSN not set")


# AGENT claude SHALL DEFINE RECORD pg_conn AS A RECORD fixture.
@pytest.fixture
def pg_conn():
    import psycopg
    conn = psycopg.connect(_PG_DSN, autocommit=True)
    yield conn
    conn.close()


# AGENT claude SHALL DEFINE RECORD persistence AS A RECORD fixture.
@pytest.fixture
def persistence(pg_conn):
    from trugs_store.persistence.postgres import PostgresPersistence
    p = PostgresPersistence(pg_conn)
    p.ensure_schema()
    return p


# AGENT claude SHALL DEFINE RECORD sample_mem_store AS A RECORD fixture.
@pytest.fixture
def sample_mem_store():
    """An InMemoryGraphStore with sample data."""
    from trugs_store import InMemoryGraphStore
    s = InMemoryGraphStore()
    s.set_metadata("name", "test_pg_graph")
    s.set_metadata("version", "2.0.0")
    s.set_metadata("dimensions", {"d": {"description": "test dim"}})
    s.add_node({"id": "root", "type": "ROOT", "properties": {"status": "active"},
                "parent_id": None, "contains": [], "metric_level": "KILO_ROOT", "dimension": "d"})
    s.add_node({"id": "child", "type": "CHILD", "properties": {},
                "parent_id": None, "contains": [], "metric_level": "BASE_CHILD", "dimension": "d"},
               parent_id="root")
    s.add_edge({"from_id": "root", "to_id": "child", "relation": "LINKS", "weight": 0.9})
    return s


class TestPostgresPersistence:
    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_save_and_load(self, persistence, pg_conn, sample_mem_store):
        gid = f"test_{uuid.uuid4().hex[:8]}"
        persistence.save(sample_mem_store, gid)

        from trugs_store.postgres import PostgresGraphStore
        loaded = PostgresGraphStore(pg_conn, gid)
        assert loaded.node_count() == sample_mem_store.node_count()
        assert loaded.edge_count() == sample_mem_store.edge_count()
        assert loaded.get_metadata()["name"] == "test_pg_graph"
        persistence.delete_graph(gid)

    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_round_trip_json_to_postgres(self, persistence, pg_conn):
        """Load from JSON, save to Postgres, load back, compare."""
        from pathlib import Path
        from trugs_store import JsonFilePersistence

        json_p = JsonFilePersistence()
        repo = Path(__file__).parent.parent.parent.parent
        mem_store = json_p.load(str(repo / "TRUGS_STORE" / "folder.trug.json"))

        gid = f"test_rt_{uuid.uuid4().hex[:8]}"
        persistence.save(mem_store, gid)

        from trugs_store.postgres import PostgresGraphStore
        pg_store = PostgresGraphStore(pg_conn, gid)
        assert pg_store.node_count() == mem_store.node_count()
        assert pg_store.edge_count() == mem_store.edge_count()

        for node in mem_store.find_nodes():
            pg_node = pg_store.get_node(node["id"])
            assert pg_node is not None, f"Node {node['id']} not found in postgres"
            assert pg_node["type"] == node["type"]

        persistence.delete_graph(gid)

    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_save_replace_semantics(self, persistence, pg_conn, sample_mem_store):
        gid = f"test_replace_{uuid.uuid4().hex[:8]}"
        persistence.save(sample_mem_store, gid)

        # Modify and re-save
        sample_mem_store.add_node({"id": "new", "type": "NEW", "properties": {},
                                   "parent_id": None, "contains": [], "metric_level": "BASE", "dimension": "d"})
        persistence.save(sample_mem_store, gid)

        from trugs_store.postgres import PostgresGraphStore
        loaded = PostgresGraphStore(pg_conn, gid)
        assert loaded.node_count() == 3  # root + child + new
        assert loaded.get_node("new") is not None
        persistence.delete_graph(gid)

    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_list_graphs(self, persistence, sample_mem_store):
        gids = [f"test_list_{i}_{uuid.uuid4().hex[:8]}" for i in range(3)]
        for gid in gids:
            persistence.save(sample_mem_store, gid)

        graphs = persistence.list_graphs()
        listed_ids = {g["graph_id"] for g in graphs}
        for gid in gids:
            assert gid in listed_ids

        for gid in gids:
            persistence.delete_graph(gid)

    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_delete_graph(self, persistence, pg_conn, sample_mem_store):
        gid = f"test_del_{uuid.uuid4().hex[:8]}"
        persistence.save(sample_mem_store, gid)
        assert persistence.delete_graph(gid) is True
        assert persistence.delete_graph(gid) is False

    # AGENT SHALL VALIDATE DATA postgres_persistence.
    def test_load_nonexistent_raises_keyerror(self, persistence):
        with pytest.raises(KeyError):
            persistence.load("nonexistent_graph_id")
