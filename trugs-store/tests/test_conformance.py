"""Conformance test suite for GraphStore implementations."""

import pytest
from tests.conftest import _make_node


class TestNodeRead:
    # PROCESS get_node SHALL READ RECORD node THEN RETURN RECORD result.
    def test_get_node_exists(self, populated_store):
        assert populated_store.get_node("root")["id"] == "root"

    # PROCESS get_node SHALL RETURN NONE WHEN RECORD node SHALL_NOT EXISTS.
    def test_get_node_missing_returns_none(self, store):
        assert store.get_node("x") is None

    # PROCESS get_children SHALL RETURN ALL RECORD node FROM RECORD parent.
    def test_get_children(self, populated_store):
        assert {c["id"] for c in populated_store.get_children("root")} == {"child_0", "child_1", "child_2"}

    # PROCESS get_children SHALL RETURN NONE WHEN RECORD parent CONTAINS NO RECORD node.
    def test_get_children_empty(self, populated_store):
        assert populated_store.get_children("child_0") == []

    # PROCESS find_nodes SHALL FILTER RECORD node BY DATA type.
    def test_find_nodes_by_type(self, populated_store):
        assert len(populated_store.find_nodes(type="CHILD")) == 3

    # PROCESS find_nodes SHALL FILTER RECORD node BY DATA status.
    def test_find_nodes_by_status(self, populated_store):
        r = populated_store.find_nodes(status="status_1")
        assert len(r) == 1 and r[0]["id"] == "child_1"

    # PROCESS find_nodes SHALL FILTER RECORD node BY DATA stale.
    def test_find_nodes_by_stale(self, populated_store):
        populated_store.mark_stale("child_0", "test")
        assert len(populated_store.find_nodes(stale=True)) == 1

    # PROCESS find_nodes SHALL FILTER RECORD node BY DATA dimension.
    def test_find_nodes_by_dimension(self, populated_store):
        assert len(populated_store.find_nodes(dimension="test_dim")) == 4

    # PROCESS find_nodes SHALL FILTER RECORD node BY MULTIPLE DATA criteria.
    def test_find_nodes_and_semantics(self, populated_store):
        assert len(populated_store.find_nodes(type="CHILD", dimension="test_dim")) == 3
        assert len(populated_store.find_nodes(type="CHILD", dimension="other")) == 0

    # PROCESS find_nodes SHALL RETURN ALL RECORD node WHEN NO FILTER EXISTS.
    def test_find_nodes_no_filters_returns_all(self, populated_store):
        assert len(populated_store.find_nodes()) == 4

    # PROCESS node_count SHALL AGGREGATE EACH RECORD node TO INTEGER.
    def test_node_count(self, populated_store):
        assert populated_store.node_count() == 4


class TestNodeWrite:
    # PROCESS add_node SHALL WRITE RECORD node TO DATA store.
    def test_add_node_simple(self, store):
        store.add_node(_make_node("n1"))
        assert store.get_node("n1") is not None

    # PROCESS add_node SHALL BIND RECORD node TO RECORD parent THEN VALIDATE bidirectional.
    def test_add_node_with_parent_bidirectional(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert store.get_node("c")["parent_id"] == "p"
        assert "c" in store.get_node("p")["contains"]

    # PROCESS add_node SHALL REJECT RECORD node WHEN RECORD id EQUALS EXISTING.
    def test_add_node_duplicate_raises_valueerror(self, store):
        store.add_node(_make_node("n1"))
        with pytest.raises(ValueError):
            store.add_node(_make_node("n1"))

    # PROCESS add_node SHALL REJECT RECORD node WHEN RECORD parent SHALL_NOT EXISTS.
    def test_add_node_missing_parent_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.add_node(_make_node("n1"), parent_id="ghost")

    # PROCESS add_node SHALL REJECT RECORD node WHEN RECORD parent EQUALS SELF.
    def test_add_node_self_parent_raises(self, store):
        with pytest.raises((ValueError, KeyError)):
            store.add_node(_make_node("x"), parent_id="x")

    # PROCESS update_node SHALL MERGE RECORD properties TO RECORD node.
    def test_update_node_shallow_merge(self, store):
        store.add_node(_make_node("n1", status="open", tags=["a"]))
        store.update_node("n1", {"status": "closed"})
        p = store.get_node("n1")["properties"]
        assert p["status"] == "closed" and p["tags"] == ["a"]

    # PROCESS update_node SHALL MERGE RECORD properties THEN SHALL_NOT REPLACE EXISTING DATA keys.
    def test_update_node_preserves_existing_keys(self, store):
        store.add_node(_make_node("n1", alpha=1, beta=2))
        store.update_node("n1", {"beta": 3, "gamma": 4})
        assert store.get_node("n1")["properties"] == {"alpha": 1, "beta": 3, "gamma": 4}

    # PROCESS update_node SHALL REJECT WHEN RECORD node SHALL_NOT EXISTS.
    def test_update_node_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.update_node("ghost", {"x": 1})

    # PROCESS mark_stale SHALL WRITE DATA stale TO RECORD node.
    def test_mark_stale(self, store):
        store.add_node(_make_node("n1"))
        store.mark_stale("n1", "deleted")
        p = store.get_node("n1")["properties"]
        assert p["stale"] is True and p["stale_reason"] == "deleted"

    # PROCESS clear_stale SHALL REJECT DATA stale FROM RECORD node.
    def test_clear_stale(self, store):
        store.add_node(_make_node("n1"))
        store.mark_stale("n1", "test")
        store.clear_stale("n1")
        p = store.get_node("n1")["properties"]
        assert "stale" not in p and "stale_reason" not in p

    # PROCESS delete_node SHALL REJECT RECORD node WHEN RECORD node CONTAINS NO children.
    def test_delete_node_no_children(self, populated_store):
        populated_store.delete_node("child_2")
        assert populated_store.get_node("child_2") is None

    # PROCESS delete_node SHALL REJECT WHEN RECORD node CONTAINS children AND cascade EQUALS false.
    def test_delete_node_with_children_raises_valueerror(self, populated_store):
        with pytest.raises(ValueError, match="children"):
            populated_store.delete_node("root")

    # PROCESS delete_node SHALL REJECT RECORD node AND ALL RECORD descendant WHEN cascade EQUALS true.
    def test_delete_node_cascade(self, populated_store):
        populated_store.delete_node("root", cascade=True)
        assert populated_store.node_count() == 0 and populated_store.edge_count() == 0

    # PROCESS delete_node SHALL REJECT ALL RECORD edge REFERENCES RECORD node.
    def test_delete_node_removes_edges(self, populated_store):
        before = populated_store.edge_count()
        populated_store.delete_node("child_1")
        assert populated_store.edge_count() < before

    # PROCESS delete_node SHALL REJECT RECORD node FROM RECORD parent contains.
    def test_delete_node_updates_parent_contains(self, populated_store):
        populated_store.delete_node("child_0")
        assert "child_0" not in populated_store.get_node("root")["contains"]

    # PROCESS delete_node SHALL REJECT WHEN RECORD node SHALL_NOT EXISTS.
    def test_delete_node_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.delete_node("ghost")


class TestEdgeRead:
    # PROCESS get_edges SHALL FILTER RECORD edge BY DATA from_id.
    def test_get_edges_by_from_id(self, populated_store):
        assert any(e["to_id"] == "child_1" for e in populated_store.get_edges(from_id="child_0"))

    # PROCESS get_edges SHALL FILTER RECORD edge BY DATA to_id.
    def test_get_edges_by_to_id(self, populated_store):
        assert any(e["from_id"] == "child_0" for e in populated_store.get_edges(to_id="child_1"))

    # PROCESS get_edges SHALL FILTER RECORD edge BY DATA relation.
    def test_get_edges_by_relation(self, populated_store):
        assert len(populated_store.get_edges(relation="DEPENDS_ON")) == 2

    # PROCESS get_edges SHALL FILTER RECORD edge BY MULTIPLE DATA criteria.
    def test_get_edges_and_semantics(self, populated_store):
        assert len(populated_store.get_edges(from_id="child_0", relation="DEPENDS_ON")) == 1

    # PROCESS get_edges SHALL RETURN ALL RECORD edge WHEN NO FILTER EXISTS.
    def test_get_edges_no_filters_returns_all(self, populated_store):
        assert populated_store.edge_count() == 5

    # PROCESS get_edges SHALL RETURN RECORD edge WITH DATA weight AND DATA properties.
    def test_get_edges_includes_weight_and_properties(self, populated_store):
        edges = populated_store.get_edges(from_id="child_1", relation="DEPENDS_ON")
        assert edges[0]["weight"] == 0.8 and edges[0]["properties"]["note"] == "important"

    # PROCESS get_outgoing SHALL RETURN ALL RECORD edge FROM RECORD node.
    def test_get_outgoing(self, populated_store):
        assert any(e["relation"] == "DEPENDS_ON" for e in populated_store.get_outgoing("child_0"))

    # PROCESS get_incoming SHALL RETURN ALL RECORD edge TO RECORD node.
    def test_get_incoming(self, populated_store):
        froms = {e["from_id"] for e in populated_store.get_incoming("child_1")}
        assert "child_0" in froms or "root" in froms

    # PROCESS edge_count SHALL AGGREGATE EACH RECORD edge TO INTEGER.
    def test_edge_count(self, populated_store):
        assert populated_store.edge_count() == 5


class TestEdgeWrite:
    # PROCESS add_edge SHALL WRITE RECORD edge TO DATA store.
    def test_add_edge(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.edge_count() == 1

    # PROCESS add_edge SHALL WRITE RECORD edge WITH DATA weight AND DATA properties.
    def test_add_edge_with_weight_and_properties(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "weight": 0.5, "properties": {"n": 1}})
        e = store.get_edges(from_id="a")[0]
        assert e["weight"] == 0.5 and e["properties"]["n"] == 1

    # PROCESS add_edge SHALL REJECT WHEN RECORD endpoint SHALL_NOT EXISTS.
    def test_add_edge_missing_node_raises_keyerror(self, store):
        store.add_node(_make_node("a"))
        with pytest.raises(KeyError):
            store.add_edge({"from_id": "a", "to_id": "ghost", "relation": "X"})

    # PROCESS add_edge SHALL ALLOW RECORD edge WHEN RECORD endpoint CONTAINS cross-graph prefix.
    def test_add_edge_cross_graph_skips_validation(self, store):
        store.add_node(_make_node("a"))
        store.add_edge({"from_id": "a", "to_id": "OTHER:remote", "relation": "REFS"})
        assert store.edge_count() == 1

    # PROCESS add_edge SHALL SKIP WHEN RECORD edge EQUALS EXISTING.
    def test_add_edge_duplicate_ignored(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.edge_count() == 1

    # PROCESS update_edge SHALL WRITE DATA weight TO RECORD edge.
    def test_update_edge_weight(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "weight": 0.5})
        store.update_edge("a", "b", "X", weight=0.9)
        assert store.get_edges(from_id="a")[0]["weight"] == 0.9

    # PROCESS update_edge SHALL WRITE DATA properties TO RECORD edge.
    def test_update_edge_properties(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X", "properties": {}})
        store.update_edge("a", "b", "X", properties={"k": "v"})
        assert store.get_edges(from_id="a")[0]["properties"] == {"k": "v"}

    # PROCESS update_edge SHALL REJECT WHEN RECORD edge SHALL_NOT EXISTS.
    def test_update_edge_missing_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            store.update_edge("a", "b", "X", weight=1.0)

    # PROCESS remove_edge SHALL REJECT RECORD edge FROM DATA store.
    def test_remove_edge(self, store):
        store.add_node(_make_node("a"))
        store.add_node(_make_node("b"))
        store.add_edge({"from_id": "a", "to_id": "b", "relation": "X"})
        assert store.remove_edge("a", "b", "X") is True and store.edge_count() == 0

    # PROCESS remove_edge SHALL RETURN false WHEN RECORD edge SHALL_NOT EXISTS.
    def test_remove_edge_nonexistent_returns_false(self, store):
        assert store.remove_edge("a", "b", "X") is False


class TestTraversal:
    # PROCESS traverse SHALL RETURN RECORD neighbor AT depth 1 WHEN direction EQUALS outgoing.
    def test_traverse_outgoing_depth_1(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", max_depth=1)}
        assert "child_1" in ids

    # PROCESS traverse SHALL RETURN ALL RECORD neighbor WITHIN depth 3.
    def test_traverse_outgoing_depth_3(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", max_depth=3)}
        assert "child_1" in ids and "child_2" in ids

    # PROCESS traverse SHALL RETURN RECORD neighbor WHEN direction EQUALS incoming.
    def test_traverse_incoming(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_2", direction="incoming", max_depth=1)}
        assert "child_1" in ids

    # PROCESS traverse SHALL RETURN RECORD neighbor WHEN direction EQUALS both.
    def test_traverse_both_directions(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_1", direction="both", max_depth=1)}
        assert len(ids) > 0

    # PROCESS traverse SHALL FILTER RECORD neighbor BY DATA relation.
    def test_traverse_with_relation_filter(self, populated_store):
        ids = {n["id"] for n, e, d in populated_store.traverse("child_0", direction="outgoing", relation="DEPENDS_ON", max_depth=3)}
        assert "child_1" in ids

    # PROCESS traverse SHALL RETURN lazy Iterator.
    def test_traverse_is_lazy_iterator(self, populated_store):
        assert hasattr(populated_store.traverse("child_0", max_depth=1), "__next__")

    # PROCESS traverse SHALL REJECT WHEN RECORD start SHALL_NOT EXISTS.
    def test_traverse_missing_start_raises_keyerror(self, store):
        with pytest.raises(KeyError):
            list(store.traverse("ghost"))

    # PROCESS get_neighbors SHALL RETURN ALL RECORD neighbor AT depth 1.
    def test_get_neighbors(self, populated_store):
        assert len(populated_store.get_neighbors("child_1")) > 0


class TestSubgraph:
    # PROCESS extract_subgraph SHALL RETURN RECORD store WITH ONLY requested RECORD node.
    def test_extract_subgraph_nodes(self, populated_store):
        assert populated_store.extract_subgraph(["child_0", "child_1"]).node_count() == 2

    # PROCESS extract_subgraph SHALL FILTER RECORD edge TO requested RECORD node ONLY.
    def test_extract_subgraph_edges_filtered(self, populated_store):
        sub = populated_store.extract_subgraph(["child_0", "child_1"])
        for e in sub.get_edges():
            assert e["from_id"] in ("child_0", "child_1") and e["to_id"] in ("child_0", "child_1")

    # PROCESS extract_subgraph SHALL RETURN RECORD GraphStore.
    def test_extract_subgraph_returns_graphstore(self, populated_store):
        sub = populated_store.extract_subgraph(["child_0"])
        assert sub.get_node("child_0") is not None and sub.node_count() == 1

    # PROCESS extract_subgraph SHALL SKIP RECORD node WHEN RECORD id SHALL_NOT EXISTS.
    def test_extract_subgraph_skips_missing_ids(self, populated_store):
        assert populated_store.extract_subgraph(["child_0", "ghost"]).node_count() == 1


class TestMetadata:
    # PROCESS get_metadata SHALL READ ALL RECORD metadata.
    def test_get_metadata(self, populated_store):
        assert populated_store.get_metadata()["name"] == "test_graph"

    # PROCESS set_metadata SHALL WRITE DATA key TO RECORD metadata.
    def test_set_metadata(self, store):
        store.set_metadata("name", "x")
        assert store.get_metadata()["name"] == "x"

    # PROCESS get_metadata SHALL RETURN shallow copy THEN SHALL_NOT ALLOW mutation.
    def test_metadata_shallow_copy(self, populated_store):
        m = populated_store.get_metadata()
        m["name"] = "mutated"
        assert populated_store.get_metadata()["name"] == "test_graph"


class TestValidation:
    # PROCESS validate_graph SHALL RETURN NO RECORD violation FOR VALID RECORD graph.
    def test_validate_clean_graph_no_violations(self, populated_store):
        assert len([v for v in populated_store.validate_graph() if v.severity == "error"]) == 0

    # PROCESS validate_graph SHALL DETECT RECORD violation WHEN hierarchy bidirectional broken.
    def test_validate_broken_bidirectional(self, store):
        store.set_metadata("dimensions", {"d": {"description": "d"}})
        n = _make_node("p", metric_level="KILO_P")
        n["contains"] = ["ghost"]
        store._nodes["p"] = n
        assert "hierarchy_bidirectional" in {v.rule for v in store.validate_graph()}

    # PROCESS validate_graph SHALL DETECT RECORD violation WHEN DATA dimension undeclared.
    def test_validate_undeclared_dimension(self, store):
        store.set_metadata("dimensions", {"declared": {"description": "ok"}})
        store.add_node(_make_node("n1", dimension="undeclared"))
        assert "undeclared_dimension" in {v.rule for v in store.validate_graph()}

    # PROCESS validate_graph SHALL DETECT RECORD violation WHEN RECORD edge endpoint orphaned.
    def test_validate_orphan_edge_endpoint(self, store):
        store.add_node(_make_node("a"))
        store._edges.append({"from_id": "a", "to_id": "ghost", "relation": "X"})
        store._rebuild_edge_indexes()
        assert "orphan_edge" in {v.rule for v in store.validate_graph()}

    # PROCESS validate_graph SHALL DETECT RECORD violation WHEN REQUIRED DATA field missing.
    def test_validate_missing_required_fields(self, store):
        store._nodes["bad"] = {"id": "bad", "type": "X"}
        assert "missing_required_field" in {v.rule for v in store.validate_graph()}


class TestBidirectionalInvariant:
    # PROCESS add_node SHALL WRITE RECORD contains edge WHEN RECORD parent specified.
    def test_add_node_creates_contains_edge(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert any(e["to_id"] == "c" for e in store.get_edges(from_id="p", relation="contains"))

    # PROCESS add_node SHALL WRITE RECORD child TO RECORD parent contains array.
    def test_add_node_updates_parent_contains_list(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert "c" in store.get_node("p")["contains"]

    # PROCESS add_node SHALL WRITE DATA parent_id TO RECORD child.
    def test_add_node_sets_child_parent_id(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        assert store.get_node("c")["parent_id"] == "p"

    # PROCESS delete_node SHALL REJECT RECORD child FROM RECORD parent contains array.
    def test_delete_node_cleans_parent_contains(self, store):
        store.add_node(_make_node("p", metric_level="KILO_P"))
        store.add_node(_make_node("c"), parent_id="p")
        store.delete_node("c")
        assert "c" not in store.get_node("p")["contains"]
