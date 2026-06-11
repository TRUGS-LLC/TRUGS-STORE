# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""BaseGraph — shared graph model base class for TRUG graphs.

Provides factory methods (from_dict, from_json, from_file) and common
accessors (get_node, get_all_nodes, get_nodes_by_type, node_ids,
get_all_edges, edge_from, edge_to, store) shared by TrugGraph and
ComputeGraph.

Domain-specific methods (hierarchy, compute flow, stale detection)
remain in the subclasses.

Also exposes the internal `_stamp_inherited_metric_levels(store)` utility
used by v2-path dispatch in `JsonFilePersistence._save_v2` and
`PostgresPersistence._save_v2` (AAA #1756 ADR-002 — internal, not in
`__all__`, not part of the public API).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from trugs_store.memory import InMemoryGraphStore
from trugs_store.validation import SI_PREFIX_ORDERING, prefix_of


class BaseGraph:
    """Shared base class for TRUG graph models.

    Wraps InMemoryGraphStore with common factory methods and accessors
    that are identical across all graph model subclasses.

    <trl>
    AGENT claude SHALL DEFINE RECORD BaseGraph AS A RECORD graph.
    </trl>
    """

    def __init__(self, store: InMemoryGraphStore) -> None:
        self._store = store

    # ── Factory methods ──────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, trug: Dict[str, Any]) -> "BaseGraph":
        """Build graph from a parsed TRUG dictionary.

        <trl>
        PROCESS from_dict SHALL READ RECORD trug THEN RETURN RECORD graph.
        </trl>
        """
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
        """Build graph from a JSON string.

        <trl>
        PROCESS from_json SHALL READ RECORD json THEN RETURN RECORD graph.
        </trl>
        """
        return cls.from_dict(json.loads(json_string))

    @classmethod
    def from_file(cls, path: str) -> "BaseGraph":
        """Build graph from a .trug.json file.

        <trl>
        PROCESS from_file SHALL READ RECORD file THEN RETURN RECORD graph.
        </trl>
        """
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # ── Node accessors ───────────────────────────────────────────────────

    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID, or None if not found.

        <trl>
        PROCESS get_node SHALL READ RECORD node THEN RETURN RECORD result.
        </trl>
        """
        return self._store.get_node(node_id)

    def get_all_nodes(self) -> List[Dict[str, Any]]:
        """Get all nodes in the graph.

        <trl>
        PROCESS get_all_nodes SHALL READ ALL RECORD node THEN RETURN RECORD result.
        </trl>
        """
        return list(self._store._nodes.values())

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Get all nodes of a given type.

        <trl>
        PROCESS get_nodes_by_type SHALL FILTER ALL RECORD node THEN RETURN RECORD result.
        </trl>
        """
        return self._store.find_nodes(type=node_type)

    def node_ids(self) -> set[str]:
        """Get the set of all node IDs.

        <trl>
        PROCESS node_ids SHALL READ ALL RECORD node THEN RETURN RECORD result.
        </trl>
        """
        return set(self._store._nodes.keys())

    # ── Edge accessors ───────────────────────────────────────────────────

    def get_all_edges(self) -> List[Dict[str, Any]]:
        """Get all edges in the graph.

        <trl>
        PROCESS get_all_edges SHALL READ ALL RECORD edge THEN RETURN RECORD result.
        </trl>
        """
        return list(self._store._edges)

    # ── Metadata ─────────────────────────────────────────────────────────

    @property
    def store(self) -> InMemoryGraphStore:
        """Access the underlying InMemoryGraphStore.

        <trl>
        PROCESS store SHALL READ RECORD store THEN RETURN RECORD result.
        </trl>
        """
        return self._store

    @staticmethod
    def edge_from(edge: Dict[str, Any]) -> str:
        """Get source node ID from an edge dict.

        <trl>
        PROCESS edge_from SHALL READ RECORD edge THEN RETURN RECORD result.
        </trl>
        """
        result: str = edge.get("from_id") or edge.get("from_node", "")
        return result

    @staticmethod
    def edge_to(edge: Dict[str, Any]) -> str:
        """Get target node ID from an edge dict.

        <trl>
        PROCESS edge_to SHALL READ RECORD edge THEN RETURN RECORD result.
        </trl>
        """
        result: str = edge.get("to_id") or edge.get("to_node", "")
        return result

    # ── v2 internal helpers (ADR-002) ────────────────────────────────────

    # PROCESS _stamp_inherited_metric_levels SHALL WRITE RECORD metric_level TO DATA node.
    @staticmethod
    def _stamp_inherited_metric_levels(store: InMemoryGraphStore) -> None:
        """Stamp `metric_level` on v2 nodes missing it, inherited one step finer from parent.

        Per AAA #1756 Phase 3 INTERFACE / ADR-002. For every node missing
        `metric_level` whose parent has a metric_level with a recognized
        SI prefix, stamp `<finer_prefix>_<NODE_TYPE>` where `finer_prefix`
        is one step finer than the parent's prefix in `SI_PREFIX_ORDERING`.

        Iterates to fixpoint so multi-level chains (grandparent stamped
        first, then parent, then child) all converge. Internal — not
        exposed in `__all__`; called only from v2-path persistence
        adapters during save.
        """
        changed = True
        while changed:
            changed = False
            for node in store._nodes.values():
                if node.get("metric_level"):
                    continue
                parent_id = node.get("parent_id")
                if not parent_id:
                    continue
                parent = store._nodes.get(parent_id)
                if parent is None:
                    continue
                parent_prefix = prefix_of(parent.get("metric_level"))
                if parent_prefix is None:
                    continue
                parent_idx = SI_PREFIX_ORDERING.index(parent_prefix)
                if parent_idx + 1 >= len(SI_PREFIX_ORDERING):
                    # parent at YOCTO — no finer level to inherit
                    continue
                finer_prefix = SI_PREFIX_ORDERING[parent_idx + 1]
                node_type = str(node.get("type") or "NODE")
                node["metric_level"] = f"{finer_prefix}_{node_type}"
                changed = True
