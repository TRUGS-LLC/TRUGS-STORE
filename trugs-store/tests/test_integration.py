"""Integration tests against real .trug.json files.

Uses in-repo fixtures (tests/fixtures/) instead of external monorepo paths.
"""

import json
import tempfile
from pathlib import Path

import pytest
from trugs_store import InMemoryGraphStore, JsonFilePersistence

_FIXTURES = Path(__file__).parent / "fixtures"
_SAMPLE = _FIXTURES / "sample.trug.json"


# AGENT claude SHALL DEFINE RECORD persistence AS A RECORD fixture.
@pytest.fixture
def persistence():
    return JsonFilePersistence()


class TestLoadSampleTrug:
    @pytest.fixture(autouse=True)
    def _load(self, persistence):
        self.store = persistence.load(str(_SAMPLE))
        with open(_SAMPLE) as f:
            self.raw = json.load(f)

    # PROCESS load SHALL PRESERVE RECORD node count FROM DATA json file.
    def test_node_count_matches(self):
        assert self.store.node_count() == len(self.raw["nodes"])

    # PROCESS load SHALL PRESERVE RECORD edge count FROM DATA json file.
    def test_edge_count_matches(self):
        assert self.store.edge_count() == len(self.raw["edges"])

    # PROCESS load SHALL PRESERVE RECORD metadata name FROM DATA json file.
    def test_metadata_name(self):
        assert self.store.get_metadata()["name"] == self.raw["name"]

    # PROCESS find_nodes SHALL FILTER RECORD node BY DATA type FROM loaded graph.
    def test_find_nodes_by_type(self):
        specs = self.store.find_nodes(type="SPECIFICATION")
        assert "child_b" in {n["id"] for n in specs}

    # PROCESS get_children SHALL RETURN RECORD children FROM loaded RECORD parent.
    def test_get_children(self):
        children = self.store.get_children("root")
        assert {c["id"] for c in children} == {"child_a", "child_b"}

    # PROCESS get_children SHALL RETURN RECORD children AT nested depth.
    def test_get_children_nested(self):
        children = self.store.get_children("child_b")
        assert {c["id"] for c in children} == {"grandchild"}

    # PROCESS validate_graph SHALL RETURN NO error RECORD violation FOR sample graph.
    def test_validate_graph(self):
        errors = [v for v in self.store.validate_graph() if v.severity == "error"]
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    # PROCESS traverse SHALL RETURN RECORD neighbor FROM RECORD root outgoing.
    def test_traverse_from_root(self):
        neighbors = list(self.store.traverse("root", direction="outgoing", max_depth=1))
        neighbor_ids = {n["id"] for n, e, d in neighbors}
        assert "child_a" in neighbor_ids
        assert "child_b" in neighbor_ids

    # PROCESS find_nodes SHALL FILTER RECORD node BY type TASK.
    def test_find_tasks(self):
        tasks = self.store.find_nodes(type="TASK")
        assert len(tasks) == 1
        assert tasks[0]["id"] == "task_1"


class TestRoundTrip:
    # PROCESS save AND load SHALL PRESERVE ALL RECORD node AND RECORD edge AND RECORD metadata.
    def test_round_trip_preserves_data(self, persistence):
        s1 = persistence.load(str(_SAMPLE))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        persistence.save(s1, tmp)
        s2 = persistence.load(tmp)
        assert s1.node_count() == s2.node_count()
        assert s1.edge_count() == s2.edge_count()
        for n in s1.find_nodes():
            assert s1.get_node(n["id"]) == s2.get_node(n["id"])
        assert s1.get_metadata() == s2.get_metadata()
        Path(tmp).unlink()

    # PROCESS save SHALL PERSIST RECORD mutation AFTER add_node AND mark_stale.
    def test_mutate_and_save(self, persistence):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        store = persistence.load(str(_SAMPLE))
        orig = store.node_count()
        store.add_node({
            "id": "test_node", "type": "TEST", "properties": {"x": 1},
            "parent_id": None, "contains": [], "metric_level": "BASE_TEST",
            "dimension": "test_dim",
        })
        store.mark_stale("test_node", "test")
        persistence.save(store, tmp)
        s2 = persistence.load(tmp)
        assert s2.node_count() == orig + 1
        assert s2.get_node("test_node")["properties"]["stale"] is True
        Path(tmp).unlink()

    # PROCESS save SHALL WRITE VALID RECORD json WITH nodes AND edges arrays.
    def test_save_creates_valid_json(self, persistence):
        store = persistence.load(str(_SAMPLE))
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        persistence.save(store, tmp)
        with open(tmp) as fh:
            data = json.load(fh)
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        Path(tmp).unlink()
