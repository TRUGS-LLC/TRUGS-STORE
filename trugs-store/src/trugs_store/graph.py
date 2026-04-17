"""BaseGraph — shared graph model base class for TRUG graphs.

Provides factory methods (from_dict, from_json, from_file) and common
accessors (get_node, get_all_nodes, get_nodes_by_type, node_ids,
get_all_edges, edge_from, edge_to, store) shared by TrugGraph and
ComputeGraph.

Domain-specific methods (hierarchy, compute flow, stale detection)
remain in the subclasses.
"""

from __future__ import annotations

import json
from pathlib import Path

from trugs_store.memory import InMemoryGraphStore


class BaseGraph:
    """Shared base class for TRUG graph models.

    Wraps InMemoryGraphStore with common factory methods and accessors
    that are identical across all graph model subclasses.
    """

    def __init__(self, store: InMemoryGraphStore) -> None:
        self._store = store

    # ── Factory methods ──────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, trug: dict) -> "BaseGraph":
        """Build graph from a parsed TRUG dictionary."""
        store = InMemoryGraphStore()
        for key, value in trug.items():
            if key not in ("nodes", "edges"):
                store.set_metadata(key, value)
        for node in trug.get("nodes", []):
            store._nodes[node["id"]] = node
        for edge in trug.get("edges", []):
            if "from_node" in edge and "from_id" not in edge:
                edge["from_id"] = edge["from_node"]
            if "to_node" in edge and "to_id" not in edge:
                edge["to_id"] = edge["to_node"]
            store._edges.append(edge)
        store._rebuild_edge_indexes()
        return cls(store)

    @classmethod
    def from_json(cls, json_string: str) -> "BaseGraph":
        """Build graph from a JSON string."""
        return cls.from_dict(json.loads(json_string))

    @classmethod
    def from_file(cls, path: str) -> "BaseGraph":
        """Build graph from a .trug.json file."""
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # ── Node accessors ───────────────────────────────────────────────────

    def get_node(self, node_id: str) -> dict | None:
        """Get a node by ID, or None if not found."""
        return self._store.get_node(node_id)

    def get_all_nodes(self) -> list[dict]:
        """Get all nodes in the graph."""
        return list(self._store._nodes.values())

    def get_nodes_by_type(self, node_type: str) -> list[dict]:
        """Get all nodes of a given type."""
        return self._store.find_nodes(type=node_type)

    def node_ids(self) -> set[str]:
        """Get the set of all node IDs."""
        return set(self._store._nodes.keys())

    # ── Edge accessors ───────────────────────────────────────────────────

    def get_all_edges(self) -> list[dict]:
        """Get all edges in the graph."""
        return list(self._store._edges)

    # ── Metadata ─────────────────────────────────────────────────────────

    @property
    def store(self) -> InMemoryGraphStore:
        """Access the underlying InMemoryGraphStore."""
        return self._store

    @staticmethod
    def edge_from(edge: dict) -> str:
        """Get source node ID from an edge dict."""
        return edge.get("from_id") or edge.get("from_node", "")

    @staticmethod
    def edge_to(edge: dict) -> str:
        """Get target node ID from an edge dict."""
        return edge.get("to_id") or edge.get("to_node", "")
