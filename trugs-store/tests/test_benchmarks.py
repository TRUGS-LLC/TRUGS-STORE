"""Performance benchmarks for PostgreSQL backend.

Requires TRUGS_TEST_DSN environment variable.
Run with: pytest tests/test_benchmarks.py -v -s
"""

import os
import random
import statistics
import time
import uuid

import pytest

_PG_DSN = os.environ.get("TRUGS_TEST_DSN")
pytestmark = pytest.mark.skipif(not _PG_DSN, reason="TRUGS_TEST_DSN not set")


def _generate_nodes(count: int, seed: int = 42) -> list[dict]:
    """Generate count nodes with realistic payloads."""
    rng = random.Random(seed)
    nodes = []
    for i in range(count):
        nodes.append({
            "id": f"node_{i:06d}",
            "type": rng.choice(["TASK", "DOCUMENT", "COMPONENT", "SPEC", "FOLDER"]),
            "properties": {
                "name": f"Node {i}",
                "status": rng.choice(["OPEN", "IN_PROGRESS", "DONE", "BACKLOG"]),
                "description": f"Description for node {i} with some payload " * rng.randint(1, 5),
                "priority": rng.choice(["P1", "P2", "P3"]),
            },
            "metric_level": "BASE_ITEM",
            "parent_id": None,
            "contains": [],
            "dimension": "test_dim",
        })
    return nodes


def _generate_edges(nodes: list[dict], avg_per_node: float = 2.5, seed: int = 42) -> list[dict]:
    """Generate random edges between nodes."""
    rng = random.Random(seed)
    ids = [n["id"] for n in nodes]
    total = int(len(ids) * avg_per_node)
    edges = []
    seen = set()
    for _ in range(total):
        fid = rng.choice(ids)
        tid = rng.choice(ids)
        if fid == tid:
            continue
        rel = rng.choice(["DEPENDS_ON", "INFORMS", "CONTAINS", "BLOCKS"])
        key = (fid, tid, rel)
        if key in seen:
            continue
        seen.add(key)
        edges.append({"from_id": fid, "to_id": tid, "relation": rel, "weight": round(rng.random(), 2)})
    return edges


# AGENT claude SHALL DEFINE RECORD pg_conn AS A RECORD fixture.
@pytest.fixture(scope="module")
def pg_conn():
    import psycopg
    conn = psycopg.connect(_PG_DSN, autocommit=True)
    yield conn
    conn.close()


# AGENT claude SHALL DEFINE RECORD pg_persistence AS A RECORD fixture.
@pytest.fixture(scope="module")
def pg_persistence(pg_conn):
    from trugs_store.persistence.postgres import PostgresPersistence
    p = PostgresPersistence(pg_conn)
    p.ensure_schema()
    return p


# AGENT claude SHALL DEFINE RECORD pg_store_10k AS A RECORD fixture.
@pytest.fixture(scope="module")
def pg_store_10k(pg_conn, pg_persistence):
    """A 10K-node graph loaded into PostgreSQL."""
    from trugs_store.memory import InMemoryGraphStore
    from trugs_store.postgres import PostgresGraphStore

    graph_id = f"bench_10k_{uuid.uuid4().hex[:8]}"
    mem = InMemoryGraphStore()
    mem.set_metadata("name", "bench_10k")
    mem.set_metadata("version", "1.0.0")
    mem.set_metadata("dimensions", {"test_dim": {"description": "bench"}})

    nodes = _generate_nodes(10_000)
    edges = _generate_edges(nodes)
    for n in nodes:
        mem._nodes[n["id"]] = n
    for e in edges:
        mem._edges.append(e)
    mem._rebuild_edge_indexes()

    pg_persistence.save(mem, graph_id)
    store = PostgresGraphStore(pg_conn, graph_id)
    yield store
    pg_persistence.delete_graph(graph_id)


class TestGetNodeLatency:
    # PROCESS get_node SHALL RETURN RECORD node WITHIN 0.5ms AT p95 ON 10K graph.
    def test_get_node_p95_under_500us(self, pg_store_10k):
        """get_node p95 < 0.5 ms on 10K-node graph."""
        node_ids = [n["id"] for n in pg_store_10k.find_nodes()]
        rng = random.Random(42)
        times_ms = []
        for _ in range(1000):
            nid = rng.choice(node_ids)
            t0 = time.perf_counter_ns()
            pg_store_10k.get_node(nid)
            t1 = time.perf_counter_ns()
            times_ms.append((t1 - t0) / 1_000_000)
        p95 = sorted(times_ms)[int(len(times_ms) * 0.95)]
        print(f"\n  get_node: p50={statistics.median(times_ms):.3f}ms p95={p95:.3f}ms mean={statistics.mean(times_ms):.3f}ms")
        assert p95 < 0.5, f"get_node p95 = {p95:.3f} ms (target < 0.5 ms)"


class TestTraverseLatency:
    # PROCESS traverse SHALL RETURN ALL RECORD neighbor WITHIN 10ms AT p95 AT depth 10.
    def test_traverse_depth_10_p95_under_10ms(self, pg_store_10k):
        """traverse depth 10 p95 < 10 ms."""
        node_ids = [n["id"] for n in pg_store_10k.find_nodes()]
        rng = random.Random(42)
        times_ms = []
        for _ in range(50):
            start = rng.choice(node_ids)
            t0 = time.perf_counter_ns()
            list(pg_store_10k.traverse(start, direction="outgoing", max_depth=10))
            t1 = time.perf_counter_ns()
            times_ms.append((t1 - t0) / 1_000_000)
        p95 = sorted(times_ms)[int(len(times_ms) * 0.95)]
        print(f"\n  traverse d=10: p50={statistics.median(times_ms):.3f}ms p95={p95:.3f}ms mean={statistics.mean(times_ms):.3f}ms")
        assert p95 < 10, f"traverse p95 = {p95:.3f} ms (target < 10 ms)"


class TestBulkLoadPerformance:
    # PROCESS save SHALL WRITE 100K RECORD node TO DATA database WITHIN 1 second.
    def test_bulk_load_100k_under_1s(self, pg_conn, pg_persistence):
        """Bulk load 100K nodes via COPY in < 1 second."""
        from trugs_store.memory import InMemoryGraphStore

        graph_id = f"bench_100k_{uuid.uuid4().hex[:8]}"
        mem = InMemoryGraphStore()
        mem.set_metadata("name", "bench_100k")
        mem.set_metadata("version", "1.0.0")
        mem.set_metadata("dimensions", {"test_dim": {"description": "bench"}})

        nodes = _generate_nodes(100_000)
        edges = _generate_edges(nodes, avg_per_node=2.0)
        for n in nodes:
            mem._nodes[n["id"]] = n
        for e in edges:
            mem._edges.append(e)
        mem._rebuild_edge_indexes()

        t0 = time.perf_counter()
        pg_persistence.save(mem, graph_id)
        elapsed = time.perf_counter() - t0
        print(f"\n  bulk load 100K: {elapsed:.2f}s ({len(nodes)} nodes, {len(edges)} edges)")

        # Verify data landed
        from trugs_store.postgres import PostgresGraphStore
        store = PostgresGraphStore(pg_conn, graph_id)
        assert store.node_count() == len(nodes)

        pg_persistence.delete_graph(graph_id)
        assert elapsed < 1.0, f"bulk load = {elapsed:.2f}s (target < 1s)"


class TestValidatePerformance:
    # PROCESS validate_graph SHALL VALIDATE 10K RECORD node WITHIN 500ms.
    def test_validate_10k_under_500ms(self, pg_store_10k):
        """validate_graph on 10K nodes < 500 ms."""
        t0 = time.perf_counter()
        violations = pg_store_10k.validate_graph()
        elapsed = time.perf_counter() - t0
        elapsed_ms = elapsed * 1000
        print(f"\n  validate 10K: {elapsed_ms:.1f}ms ({len(violations)} violations)")
        assert elapsed_ms < 500, f"validate = {elapsed_ms:.1f}ms (target < 500ms)"
