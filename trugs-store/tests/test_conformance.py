"""Conformance test suite for GraphStore implementations."""

import pytest
from tests.conftest import _make_node


class TestNodeRead:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_node_exists(self, populated_store):
        assert populated_store.get_node("root")["id"] == "root"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_node_missing_returns_none(self, store):
        assert store.get_node("x") is None

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_children(self, populated_store):
        assert {c["id"] for c in populated_store.get_children("root")} == {"child_0", "child_1", "child_2"}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_children_empty(self, populated_store):
        assert populated_store.get_children("child_0") == []

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_by_type(self, populated_store):
        assert len(populated_store.find_nodes(type="CHILD")) == 3

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_by_status(self, populated_store):
        r = populated_store.find_nodes(status="status_1")
        assert len(r) == 1 and r[0]["id"] == "child_1"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_by_stale(self, populated_store):
        populated_store.mark_stale("child_0", "test")
        assert len(populated_store.find_nodes(stale=True)) == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_by_dimension(self, populated_store):
        assert len(populated_store.find_nodes(dimension="test_dim")) == 4

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_and_semantics(self, populated_store):
        assert len(populated_store.find_nodes(type="CHILD", dimension="test_dim")) == 3
        assert len(populated_store.find_nodes(type="CHILD", dimension="other")) == 0

    # AGENT SHALL VALIDATE DATA conformance.
    def test_find_nodes_no_filters_returns_all(self, populated_store):
        assert len(populated_store.find_nodes()) == 4

    # AGENT SHALL VALIDATE DATA conformance.
    def test_node_count(self, populated_store):
        assert populated_store.node_count() == 4


class TestNodeWrite:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_simple(self, store):
        store.add_node(_make_node("n1"))
        assert store.get_node("n1") is not None

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_with_parent_bidirectional(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert store.get_node("c")["parent_id"] == "p"
        assert "c" in store.get_node("p")["contains"]

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_duplicate_raises_valueerror(self, store):
        store.add_node(_make_node("n1"))
        with pytest.raises(ValueError):
            store.add_node(_make_node("n1"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_missing_parent_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.add_node(_make_node("n1"), parent_id="ghost")

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_self_parent_raises(self, store):
        with pytest.raises((ValueError, KeyError)):
            store.add_node(_make_node("x"), parent_id="x")

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_node_shallow_merge(self, store):
        store.add_node(_make_node("n1", status="open", tags=["a"]))
        store.update_node("n1", {"status": "closed"})
        p = store.get_node("n1")["properties"]
        assert p["status"] == "closed" and p["tags"] == ["a"]

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_node_preserves_existing_keys(self, store):
        store.add_node(_make_node("n1", alpha=1, beta=2))
        store.update_node("n1", {"beta": 3, "gamma": 4})
        assert store.get_node("n1")["properties"] == {"alpha": 1, "beta": 3, "gamma": 4}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_node_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.update_node("ghost", {"x": 1})

    # AGENT SHALL VALIDATE DATA conformance.
    def test_mark_stale(self, store):
        store.add_node(_make_node("n1"))
        store.mark_stale("n1", "deleted")
        p = store.get_node("n1")["properties"]
        assert p["stale"] is True and p["stale_reason"] == "deleted"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_clear_stale(self, store):
        store.add_node(_make_node("n1"))
        store.mark_stale("n1", "test")
        store.clear_stale("n1")
        p = store.get_node("n1")["properties"]
        assert "stale" not in p and "stale_reason" not in p

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_no_children(self, populated_store):
        populated_store.delete_node("child_2")
        assert populated_store.get_node("child_2") is None

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_with_children_raises_valueerror(self, populated_store):
        with pytest.raises(ValueError, match="children"):
            populated_store.delete_node("root")

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_cascade(self, populated_store):
        populated_store.delete_node("root", cascade=True)
        assert populated_store.node_count() == 0 and populated_store.edge_count() == 0

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_removes_edges(self, populated_store):
        before = populated_store.edge_count()
        populated_store.delete_node("child_1")
        assert populated_store.edge_count() < before

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_updates_parent_contains(self, populated_store):
        populated_store.delete_node("child_0")
        assert "child_0" not in populated_store.get_node("root")["contains"]

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.delete_node("ghost")


class TestEdgeRead:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_by_from_id(self, populated_store):
        assert any(e["to_id"] == "child_1" for e in populated_store.get_edges(from_id="child_0"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_by_to_id(self, populated_store):
        assert any(e["from_id"] == "child_0" for e in populated_store.get_edges(to_id="child_1"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_by_relation(self, populated_store):
        assert len(populated_store.get_edges(relation="DEPENDS_ON")) == 2

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_and_semantics(self, populated_store):
        assert len(populated_store.get_edges(from_id="child_0", relation="DEPENDS_ON")) == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_no_filters_returns_all(self, populated_store):
        assert populated_store.edge_count() == 5

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_edges_includes_weight_and_properties(self, populated_store):
        edges = populated_store.get_edges(from_id="child_1", relation="DEPENDS_ON")
        assert edges[0]["weight"] == 0.8 and edges[0]["properties"]["note"] == "important"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_outgoing(self, populated_store):
        assert any(e["relation"] == "DEPENDS_ON" for e in populated_store.get_outgoing("child_0"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_incoming(self, populated_store):
        froms = {e["from_id"] for e in populated_store.get_incoming("child_1")}
        assert "child_0" in froms or "root" in froms

    # AGENT SHALL VALIDATE DATA conformance.
    def test_edge_count(self, populated_store):
        assert populated_store.edge_count() == 5


class TestEdgeWrite:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_edge(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.edge_count() == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_edge_with_weight_and_properties(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "weight": 0.5, "properties": {"n": 1}})
        e = store.get_edges(from_id="a")[0]
        assert e["weight"] == 0.5 and e["properties"]["n"] == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_edge_missing_node_raises_keyerror(self, store):
        store.add_node(_make_node("a"))
        with pytest.raises(KeyError):
            store.add_edge({"from_id": "a", "to_id": "ghost", "relation": "X"})

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_edge_cross_graph_skips_validation(self, store):
        store.add_node(_make_node("a"))
        store.add_edge({"from_id": "a", "to_id": "OTHER:remote", "relation": "REFS"})
        assert store.edge_count() == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_edge_duplicate_ignored(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.edge_count() == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_edge_weight(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "weight": 0.5})
        store.update_edge("a", "b", "X", weight=0.9)
        assert store.get_edges(from_id="a")[0]["weight"] == 0.9

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_edge_properties(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "properties": {}})
        store.update_edge("a", "b", "X", properties={"k": "v"})
        assert store.get_edges(from_id="a")[0]["properties"] == {"k": "v"}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_update_edge_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.update_edge("a", "b", "X", weight=1.0)

    # AGENT SHALL VALIDATE DATA conformance.
    def test_remove_edge(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.remove_edge("a", "b", "X") is True and store.edge_count() == 0

    # AGENT SHALL VALIDATE DATA conformance.
    def test_remove_edge_nonexistent_returns_false(self, store):
        assert store.remove_edge("a", "b", "X") is False


class TestTraversal:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_outgoing_depth_1(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", max_depth=1)}
        assert "child_1" in ids

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_outgoing_depth_3(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", max_depth=3)}
        assert "child_1" in ids and "child_2" in ids

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_incoming(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_2", direction="incoming", max_depth=1)}
        assert "child_1" in ids

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_both_directions(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_1", direction="both", max_depth=1)}
        assert len(ids) > 0

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_with_relation_filter(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", relation="DEPENDS_ON", max_depth=3)}
        assert "child_1" in ids

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_is_lazy_iterator(self, populated_store):
        assert hasattr(populated_store.traverse("child_0", max_depth=1), "__next__")

    # AGENT SHALL VALIDATE DATA conformance.
    def test_traverse_missing_start_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            list(store.traverse("ghost"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_neighbors(self, populated_store):
        assert len(populated_store.get_neighbors("child_1")) > 0


class TestSubgraph:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_extract_subgraph_nodes(self, populated_store):
        assert populated_store.extract_subgraph(["child_0", "child_1"]).node_count() == 2

    # AGENT SHALL VALIDATE DATA conformance.
    def test_extract_subgraph_edges_filtered(self, populated_store):
        sub = populated_store.extract_subgraph(["child_0", "child_1"])
        for e in sub.get_edges():
            assert e["from_id"] in ("child_0", "child_1") and e["to_id"] in ("child_0", "child_1")

    # AGENT SHALL VALIDATE DATA conformance.
    def test_extract_subgraph_returns_graphstore(self, populated_store):
        sub = populated_store.extract_subgraph(["child_0"])
        assert sub.get_node("child_0") is not None and sub.node_count() == 1

    # AGENT SHALL VALIDATE DATA conformance.
    def test_extract_subgraph_skips_missing_ids(self, populated_store):
        assert populated_store.extract_subgraph(["child_0", "ghost"]).node_count() == 1


class TestMetadata:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_get_metadata(self, populated_store):
        assert populated_store.get_metadata()["name"] == "test_graph"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_set_metadata(self, store):
        store.set_metadata("name", "x")
        assert store.get_metadata()["name"] == "x"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_metadata_shallow_copy(self, populated_store):
        m = populated_store.get_metadata()
        m["name"] = "mutated"
        assert populated_store.get_metadata()["name"] == "test_graph"


class TestValidation:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_validate_clean_graph_no_violations(self, populated_store):
        assert len([v for v in populated_store.validate_graph() if v.severity == "error"]) == 0

    # AGENT SHALL VALIDATE DATA conformance.
    def test_validate_broken_bidirectional(self, store):
        store.set_metadata("dimensions", {"d": {"description": "d"}})
        n = _make_node("p", metric_level="KILO_P")
        n["contains"] = ["ghost"]
        store._nodes["p"] = n
        assert "hierarchy_bidirectional" in {v.rule for v in store.validate_graph()}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_validate_undeclared_dimension(self, store):
        store.set_metadata("dimensions", {"declared": {"description": "ok"}})
        store.add_node(_make_node("n1", dimension="undeclared"))
        assert "undeclared_dimension" in {v.rule for v in store.validate_graph()}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_validate_orphan_edge_endpoint(self, store):
        store.add_node(_make_node("a"))
        store._edges.append({"from_id": "a", "to_id": "ghost", "relation": "X"})
        store._rebuild_edge_indexes()
        assert "orphan_edge" in {v.rule for v in store.validate_graph()}

    # AGENT SHALL VALIDATE DATA conformance.
    def test_validate_missing_required_fields(self, store):
        store._nodes["bad"] = {"id": "bad", "type": "X"}
        assert "missing_required_field" in {v.rule for v in store.validate_graph()}


class TestBidirectionalInvariant:
    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_creates_contains_edge(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert any(e["to_id"] == "c" for e in store.get_edges(from_id="p", relation="contains"))

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_updates_parent_contains_list(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert "c" in store.get_node("p")["contains"]

    # AGENT SHALL VALIDATE DATA conformance.
    def test_add_node_sets_child_parent_id(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert store.get_node("c")["parent_id"] == "p"

    # AGENT SHALL VALIDATE DATA conformance.
    def test_delete_node_cleans_parent_contains(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        store.delete_node("c")
        assert "c" not in store.get_node("p")["contains"]
