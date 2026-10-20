# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Graph validation covers cycles without roots and hierarchies of deep nesting."""

from trugs_store import BaseGraph


def _node(nid, parent_id, children):
    return {
        "id": nid,
        "type": "ITEM",
        "properties": {},
        "parent_id": parent_id,
        "contains": children,
        "metric_level": "BASE_ITEM",
        "dimension": "test",
    }


def _store(nodes):
    return BaseGraph.from_dict(
        {
            "name": "hierarchy",
            "version": "1.0.0",
            "type": "PROJECT",
            "dimension": "test",
            "dimensions": {"test": {"description": "Test hierarchy"}},
            "nodes": nodes,
            "edges": [],
        }
    ).store


def _check_rootless_cycle(with_root):
    nodes = [_node("a", "b", ["b"]), _node("b", "a", ["a"])]
    if with_root:
        nodes.insert(0, _node("root", None, []))
    violations = _store(nodes).validate_graph()
    assert violations
    assert all(v.rule == "hierarchy_cycle" for v in violations)
    assert all(v.node_id in {"a", "b"} for v in violations)
    assert all(
        v.message == f"Cycle detected involving node {v.node_id!r}"
        and v.severity == "error"
        for v in violations
    )


def test_rootless_cycle():
    """A closed cycle needs no root to be detected."""
    _check_rootless_cycle(False)


def test_rootless_cycle_beside_root():
    """A separate root must not hide a closed cycle."""
    _check_rootless_cycle(True)


def test_self_parent_cycle():
    """A node containing itself is a hierarchy cycle."""
    violations = _store([_node("a", "a", ["a"])]).validate_graph()
    assert [(v.node_id, v.rule, v.message, v.severity) for v in violations] == [
        ("a", "hierarchy_cycle", "Cycle detected involving node 'a'", "error")
    ]


def test_hierarchy_1100_nodes_deep():
    """A valid deep chain returns an empty list without a recursion failure."""
    depth = 1100
    nodes = [
        _node(
            str(i),
            str(i - 1) if i else None,
            [str(i + 1)] if i + 1 < depth else [],
        )
        for i in range(depth)
    ]
    assert _store(nodes).validate_graph() == []
