"""Integration tests against real .trug.json files."""

import json
import tempfile
from pathlib import Path

import pytest
from trugs_store import InMemoryGraphStore, JsonFilePersistence

_REPO = Path(__file__).parent.parent.parent.parent
_STORE_TRUG = _REPO / "TRUGS_STORE" / "folder.trug.json"
_EPIC_TRUG = _REPO / "TRUGS_EPIC" / "epics" / "epic_tooling.trug.json"


@pytest.fixture
def persistence():
    return JsonFilePersistence()


class TestLoadStoreFolderTrug:
    @pytest.fixture(autouse=True)
    def _load(self, persistence):
        self.store = persistence.load(str(_STORE_TRUG))
        with open(_STORE_TRUG) as f:
            self.raw = json.load(f)

    def test_node_count_matches(self):
        assert self.store.node_count() == len(self.raw["nodes"])

    def test_edge_count_matches(self):
        assert self.store.edge_count() == len(self.raw["edges"])

    def test_metadata_name(self):
        assert self.store.get_metadata()["name"] == self.raw["name"]

    def test_find_nodes_by_type(self):
        docs = self.store.find_nodes(type="DOCUMENT")
        assert "spec_graphstore_protocol" in {n["id"] for n in docs}

    def test_get_children(self):
        roots = [n for n in self.raw["nodes"] if n.get("parent_id") is None]
        if roots:
            r = roots[0]
            assert {c["id"] for c in self.store.get_children(r["id"])} == set(r.get("contains", []))

    def test_validate_graph(self):
        errors = [v for v in self.store.validate_graph() if v.severity == "error" and v.rule not in ("orphan_edge", "hierarchy_orphan", "hierarchy_bidirectional")]
        assert len(errors) == 0, f"Unexpected errors: {errors}"


class TestLoadEpicToolingTrug:
    @pytest.fixture(autouse=True)
    def _load(self, persistence):
        self.store = persistence.load(str(_EPIC_TRUG))
        with open(_EPIC_TRUG) as f:
            self.raw = json.load(f)

    def test_node_count_matches(self):
        assert self.store.node_count() == len(self.raw["nodes"])

    def test_find_tasks(self):
        assert len(self.store.find_nodes(type="TASK")) > 0

    def test_traverse_from_epic(self):
        assert len(list(self.store.traverse("epic_tooling", direction="outgoing", max_depth=1))) > 0

    def test_get_outgoing_contains_edges(self):
        assert "CONTAINS" in {e["relation"] for e in self.store.get_outgoing("epic_tooling")}


class TestRoundTrip:
    def test_round_trip_preserves_data(self, persistence):
        s1 = persistence.load(str(_STORE_TRUG))
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

    def test_mutate_and_save(self, persistence):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        store = persistence.load(str(_STORE_TRUG))
        orig = store.node_count()
        store.add_node({"id": "test_node", "type": "TEST", "properties": {"x": 1}, "parent_id": None, "contains": [], "metric_level": "BASE_TEST", "dimension": "code_structure"})
        store.mark_stale("test_node", "test")
        persistence.save(store, tmp)
        s2 = persistence.load(tmp)
        assert s2.node_count() == orig + 1
        assert s2.get_node("test_node")["properties"]["stale"] is True
        Path(tmp).unlink()
