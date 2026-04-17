"""Tests for BaseGraph — shared graph model base class."""

import json
import tempfile
from pathlib import Path

from trugs_store import BaseGraph
from trugs_store.memory import InMemoryGraphStore


SAMPLE_TRUG = {
    "name": "Test Graph",
    "version": "1.0.0",
    "type": "TEST",
    "dimensions": {},
    "capabilities": {"extensions": [], "vocabularies": ["test_v1"], "profiles": []},
    "nodes": [
        {"id": "root", "type": "FOLDER", "parent_id": None, "contains": ["child1", "child2"],
         "properties": {"name": "root"}, "metric_level": "KILO", "dimension": "test"},
        {"id": "child1", "type": "DOC", "parent_id": "root", "contains": [],
         "properties": {"name": "child1"}, "metric_level": "BASE", "dimension": "test"},
        {"id": "child2", "type": "DOC", "parent_id": "root", "contains": [],
         "properties": {"name": "child2"}, "metric_level": "BASE", "dimension": "test"},
    ],
    "edges": [
        {"from_id": "root", "to_id": "child1", "relation": "contains", "weight": 1.0, "properties": {}},
        {"from_id": "root", "to_id": "child2", "relation": "contains", "weight": 1.0, "properties": {}},
        {"from_id": "child1", "to_id": "child2", "relation": "uses", "weight": 0.8, "properties": {}},
    ],
}


class TestBaseGraphFactory:
    # PROCESS from_dict SHALL READ RECORD trug dict THEN RETURN RECORD graph WITH correct counts.
    def test_from_dict(self):
        g = BaseGraph.from_dict(SAMPLE_TRUG)
        assert len(g.get_all_nodes()) == 3
        assert len(g.get_all_edges()) == 3

    # PROCESS from_json SHALL READ RECORD json string THEN RETURN RECORD graph.
    def test_from_json(self):
        g = BaseGraph.from_json(json.dumps(SAMPLE_TRUG))
        assert len(g.get_all_nodes()) == 3

    # PROCESS from_file SHALL READ RECORD file THEN RETURN RECORD graph.
    def test_from_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_TRUG, f)
            path = f.name
        try:
            g = BaseGraph.from_file(path)
            assert len(g.get_all_nodes()) == 3
        finally:
            Path(path).unlink()

    # PROCESS from_dict SHALL REPLACE DATA from_node WITH DATA from_id IN RECORD edge.
    def test_from_dict_normalizes_edge_keys(self):
        trug = {**SAMPLE_TRUG, "edges": [
            {"from_node": "root", "to_node": "child1", "relation": "contains"},
        ]}
        g = BaseGraph.from_dict(trug)
        edge = g.get_all_edges()[0]
        assert edge["from_id"] == "root"
        assert edge["to_id"] == "child1"


class TestBaseGraphAccessors:
    def setup_method(self):
        self.g = BaseGraph.from_dict(SAMPLE_TRUG)

    # PROCESS get_node SHALL READ RECORD node BY DATA id.
    def test_get_node(self):
        node = self.g.get_node("root")
        assert node is not None
        assert node["type"] == "FOLDER"

    # PROCESS get_node SHALL RETURN NONE WHEN RECORD node SHALL_NOT EXISTS.
    def test_get_node_missing(self):
        assert self.g.get_node("nonexistent") is None

    # PROCESS get_all_nodes SHALL RETURN ALL RECORD node FROM DATA store.
    def test_get_all_nodes(self):
        nodes = self.g.get_all_nodes()
        assert len(nodes) == 3

    # PROCESS get_nodes_by_type SHALL FILTER RECORD node BY DATA type.
    def test_get_nodes_by_type(self):
        docs = self.g.get_nodes_by_type("DOC")
        assert len(docs) == 2

    # PROCESS node_ids SHALL RETURN ALL RECORD id AS set.
    def test_node_ids(self):
        ids = self.g.node_ids()
        assert ids == {"root", "child1", "child2"}

    # PROCESS get_all_edges SHALL RETURN ALL RECORD edge FROM DATA store.
    def test_get_all_edges(self):
        edges = self.g.get_all_edges()
        assert len(edges) == 3

    # PROCESS store SHALL RETURN RECORD InMemoryGraphStore instance.
    def test_store_property(self):
        assert isinstance(self.g.store, InMemoryGraphStore)

    # PROCESS edge_from SHALL READ DATA from_id FROM RECORD edge.
    def test_edge_from(self):
        edge = {"from_id": "a", "to_id": "b"}
        assert BaseGraph.edge_from(edge) == "a"

    # PROCESS edge_from SHALL READ DATA from_node AS fallback FROM RECORD edge.
    def test_edge_from_legacy(self):
        edge = {"from_node": "a", "to_node": "b"}
        assert BaseGraph.edge_from(edge) == "a"

    # PROCESS edge_to SHALL READ DATA to_id FROM RECORD edge.
    def test_edge_to(self):
        edge = {"from_id": "a", "to_id": "b"}
        assert BaseGraph.edge_to(edge) == "b"

    # PROCESS edge_to SHALL READ DATA to_node AS fallback FROM RECORD edge.
    def test_edge_to_legacy(self):
        edge = {"from_node": "a", "to_node": "b"}
        assert BaseGraph.edge_to(edge) == "b"


class TestBaseGraphSubclassing:
    """Verify subclasses get factory methods that return the subclass type."""

    # PROCESS from_dict SHALL RETURN RECORD subclass instance WHEN called ON subclass.
    def test_subclass_from_dict(self):
        class MyGraph(BaseGraph):
            pass

        g = MyGraph.from_dict(SAMPLE_TRUG)
        assert isinstance(g, MyGraph)
        assert len(g.get_all_nodes()) == 3

    # PROCESS from_json SHALL RETURN RECORD subclass instance WHEN called ON subclass.
    def test_subclass_from_json(self):
        class MyGraph(BaseGraph):
            pass

        g = MyGraph.from_json(json.dumps(SAMPLE_TRUG))
        assert isinstance(g, MyGraph)

    # PROCESS from_file SHALL RETURN RECORD subclass instance WHEN called ON subclass.
    def test_subclass_from_file(self):
        class MyGraph(BaseGraph):
            pass

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_TRUG, f)
            path = f.name
        try:
            g = MyGraph.from_file(path)
            assert isinstance(g, MyGraph)
        finally:
            Path(path).unlink()
