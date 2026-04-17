"""In-memory GraphStore implementation backed by Python dicts."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any, Dict, Iterator, List, Optional

from trugs_store.protocol import Violation
from trugs_store.types import Edge, Node

_MAX_ANCESTOR_DEPTH = 100


class InMemoryGraphStore:
    """Dict-based GraphStore — O(1) node lookup, O(degree) edge access."""

    def __init__(self) -> None:
        self._nodes: Dict[str, Node] = {}
        self._edges: List[Edge] = []
        self._outgoing: Dict[str, List[int]] = {}
        self._incoming: Dict[str, List[int]] = {}
        self._metadata: Dict[str, Any] = {}

    # === Node Read ===

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._nodes.get(node_id)

    def get_children(self, parent_id: str) -> List[Node]:
        return [n for n in self._nodes.values() if n.get("parent_id") == parent_id]

    def find_nodes(self, *, type: Optional[str] = None, status: Optional[str] = None, stale: Optional[bool] = None, dimension: Optional[str] = None) -> List[Node]:
        result = list(self._nodes.values())
        if type is not None:
            result = [n for n in result if n.get("type") == type]
        if status is not None:
            result = [n for n in result if n.get("properties", {}).get("status") == status]
        if stale is not None:
            result = [n for n in result if n.get("properties", {}).get("stale", False) is stale]
        if dimension is not None:
            result = [n for n in result if n.get("dimension") == dimension]
        return result

    def node_count(self) -> int:
        return len(self._nodes)

    # === Node Write ===

    def add_node(self, node: Node, *, parent_id: Optional[str] = None) -> None:
        nid = node["id"]
        if nid in self._nodes:
            raise ValueError(f"Node {nid!r} already exists")
        if parent_id is not None:
            if parent_id not in self._nodes:
                raise KeyError(f"Parent {parent_id!r} does not exist")
            ancestor = parent_id
            for _ in range(_MAX_ANCESTOR_DEPTH):
                if ancestor == nid:
                    raise ValueError(f"Adding {nid!r} under {parent_id!r} would create a cycle")
                p = self._nodes.get(ancestor)
                if p is None:
                    break
                ancestor = p.get("parent_id")
                if ancestor is None:
                    break
            node["parent_id"] = parent_id
            parent = self._nodes[parent_id]
            contains = parent.get("contains", [])
            if nid not in contains:
                contains.append(nid)
            parent["contains"] = contains
            self._add_edge_internal({"from_id": parent_id, "to_id": nid, "relation": "contains"})
        self._nodes[nid] = node

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"Node {node_id!r} does not exist")
        self._nodes[node_id].setdefault("properties", {}).update(properties)

    def mark_stale(self, node_id: str, reason: str) -> None:
        self.update_node(node_id, {"stale": True, "stale_reason": reason})

    def clear_stale(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"Node {node_id!r} does not exist")
        props = self._nodes[node_id].get("properties", {})
        props.pop("stale", None)
        props.pop("stale_reason", None)

    def delete_node(self, node_id: str, *, cascade: bool = False) -> None:
        if node_id not in self._nodes:
            raise KeyError(f"Node {node_id!r} does not exist")
        node = self._nodes[node_id]
        children = node.get("contains", [])
        if children and not cascade:
            raise ValueError(f"Node {node_id!r} has children {children}; use cascade=True")
        to_delete: set[str] = set()
        if cascade:
            queue = deque([node_id])
            while queue:
                nid = queue.popleft()
                if nid in to_delete:
                    continue
                to_delete.add(nid)
                n = self._nodes.get(nid)
                if n:
                    queue.extend(n.get("contains", []))
        else:
            to_delete.add(node_id)
        pid = node.get("parent_id")
        if pid and pid in self._nodes:
            parent = self._nodes[pid]
            contains = parent.get("contains", [])
            if node_id in contains:
                contains.remove(node_id)
        self._edges = [e for e in self._edges if e["from_id"] not in to_delete and e["to_id"] not in to_delete]
        self._rebuild_edge_indexes()
        for nid in to_delete:
            self._nodes.pop(nid, None)

    # === Edge Read ===

    def get_edges(self, *, from_id: Optional[str] = None, to_id: Optional[str] = None, relation: Optional[str] = None) -> List[Edge]:
        if from_id is not None and to_id is None and relation is None:
            return [self._edges[i] for i in self._outgoing.get(from_id, [])]
        if to_id is not None and from_id is None and relation is None:
            return [self._edges[i] for i in self._incoming.get(to_id, [])]
        result = self._edges
        if from_id is not None:
            result = [e for e in result if e["from_id"] == from_id]
        if to_id is not None:
            result = [e for e in result if e["to_id"] == to_id]
        if relation is not None:
            result = [e for e in result if e["relation"] == relation]
        return result

    def get_outgoing(self, node_id: str) -> List[Edge]:
        return [self._edges[i] for i in self._outgoing.get(node_id, [])]

    def get_incoming(self, node_id: str) -> List[Edge]:
        return [self._edges[i] for i in self._incoming.get(node_id, [])]

    def edge_count(self) -> int:
        return len(self._edges)

    # === Edge Write ===

    def add_edge(self, edge: Edge) -> None:
        fid, tid = edge["from_id"], edge["to_id"]
        if ":" not in fid and fid not in self._nodes:
            raise KeyError(f"from_id {fid!r} does not exist")
        if ":" not in tid and tid not in self._nodes:
            raise KeyError(f"to_id {tid!r} does not exist")
        self._add_edge_internal(edge)

    def update_edge(self, from_id: str, to_id: str, relation: str, *, properties: Optional[Dict[str, Any]] = None, weight: Optional[float] = None) -> None:
        for edge in self._edges:
            if edge["from_id"] == from_id and edge["to_id"] == to_id and edge["relation"] == relation:
                if properties is not None:
                    edge["properties"] = properties
                if weight is not None:
                    edge["weight"] = weight
                return
        raise KeyError(f"Edge ({from_id!r}, {to_id!r}, {relation!r}) does not exist")

    def remove_edge(self, from_id: str, to_id: str, relation: str) -> bool:
        for i, edge in enumerate(self._edges):
            if edge["from_id"] == from_id and edge["to_id"] == to_id and edge["relation"] == relation:
                self._edges.pop(i)
                self._rebuild_edge_indexes()
                return True
        return False

    # === Traversal ===

    def traverse(self, start_id: str, *, direction: str = "outgoing", relation: Optional[str] = None, max_depth: int = 1) -> Iterator[tuple[Node, Edge, int]]:
        if start_id not in self._nodes:
            raise KeyError(f"Start node {start_id!r} does not exist")
        visited = {start_id}
        queue: deque[tuple[str, int]] = deque([(start_id, 0)])
        while queue:
            current_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            edges: List[Edge] = []
            if direction in ("outgoing", "both"):
                edges.extend(self.get_outgoing(current_id))
            if direction in ("incoming", "both"):
                edges.extend(self.get_incoming(current_id))
            for edge in edges:
                if relation is not None and edge["relation"] != relation:
                    continue
                neighbor_id = edge["to_id"] if edge["from_id"] == current_id else edge["from_id"]
                if neighbor_id in visited:
                    continue
                neighbor = self._nodes.get(neighbor_id)
                if neighbor is None:
                    continue
                visited.add(neighbor_id)
                yield (neighbor, edge, depth + 1)
                queue.append((neighbor_id, depth + 1))

    def get_neighbors(self, node_id: str, *, direction: str = "both") -> List[Node]:
        return [node for node, _e, _d in self.traverse(node_id, direction=direction, max_depth=1)]

    # === Subgraph ===

    def extract_subgraph(self, node_ids: List[str]) -> "GraphStore":
        id_set = set(node_ids)
        sub = InMemoryGraphStore()
        sub._metadata = deepcopy(self._metadata)
        for nid in node_ids:
            node = self._nodes.get(nid)
            if node is not None:
                sub._nodes[nid] = deepcopy(node)
        for edge in self._edges:
            if edge["from_id"] in id_set and edge["to_id"] in id_set:
                sub._edges.append(deepcopy(edge))
        sub._rebuild_edge_indexes()
        return sub

    # === Metadata ===

    def get_metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)

    def set_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    # === Validation ===

    def validate_graph(self) -> List[Violation]:
        violations: List[Violation] = []
        declared_dims = set(self._metadata.get("dimensions", {}).keys())

        for nid, node in self._nodes.items():
            for field in ("id", "type", "properties", "parent_id", "contains", "metric_level", "dimension"):
                if field not in node:
                    violations.append(Violation(nid, "missing_required_field", f"Node {nid!r} missing required field {field!r}"))
            pid = node.get("parent_id")
            if pid is not None:
                parent = self._nodes.get(pid)
                if parent is None:
                    violations.append(Violation(nid, "hierarchy_orphan", f"Node {nid!r} references parent {pid!r} which does not exist"))
                elif nid not in parent.get("contains", []):
                    violations.append(Violation(nid, "hierarchy_bidirectional", f"Node {nid!r} has parent_id={pid!r} but parent.contains does not include it"))
            for child_id in node.get("contains", []):
                child = self._nodes.get(child_id)
                if child is None:
                    violations.append(Violation(nid, "hierarchy_bidirectional", f"Node {nid!r} contains {child_id!r} which does not exist"))
                elif child.get("parent_id") != nid:
                    violations.append(Violation(nid, "hierarchy_bidirectional", f"Node {nid!r} contains {child_id!r} but child.parent_id != {nid!r}"))
            dim = node.get("dimension")
            if dim and declared_dims and dim not in declared_dims:
                violations.append(Violation(nid, "undeclared_dimension", f"Node {nid!r} uses dimension {dim!r} which is not declared"))
            if pid is not None:
                parent = self._nodes.get(pid)
                if parent and node.get("dimension") != parent.get("dimension"):
                    violations.append(Violation(nid, "dimension_mismatch", f"Node {nid!r} dimension {node.get('dimension')!r} != parent {pid!r} dimension {parent.get('dimension')!r}"))

        # Cycle detection
        visited: set[str] = set()
        path: set[str] = set()
        def _detect_cycle(nid: str) -> None:
            if nid in path:
                violations.append(Violation(nid, "hierarchy_cycle", f"Cycle detected involving node {nid!r}"))
                return
            if nid in visited:
                return
            visited.add(nid)
            path.add(nid)
            for child_id in self._nodes.get(nid, {}).get("contains", []):
                if child_id in self._nodes:
                    _detect_cycle(child_id)
            path.discard(nid)
        for nid, node in self._nodes.items():
            if node.get("parent_id") is None:
                _detect_cycle(nid)

        # Edge validation
        for edge in self._edges:
            fid, tid = edge.get("from_id", ""), edge.get("to_id", "")
            if not fid or not tid or "relation" not in edge:
                violations.append(Violation(fid or "unknown", "missing_edge_field", f"Edge missing required field(s): {edge}"))
                continue
            if ":" not in fid and fid not in self._nodes:
                violations.append(Violation(fid, "orphan_edge", f"Edge from_id {fid!r} does not exist"))
            if ":" not in tid and tid not in self._nodes:
                violations.append(Violation(tid, "orphan_edge", f"Edge to_id {tid!r} does not exist"))

        return violations

    # === Internal ===

    def _add_edge_internal(self, edge: Edge) -> None:
        fid, tid, rel = edge["from_id"], edge["to_id"], edge["relation"]
        for existing in self._edges:
            if existing["from_id"] == fid and existing["to_id"] == tid and existing["relation"] == rel:
                return
        idx = len(self._edges)
        self._edges.append(edge)
        self._outgoing.setdefault(fid, []).append(idx)
        self._incoming.setdefault(tid, []).append(idx)

    def _rebuild_edge_indexes(self) -> None:
        self._outgoing.clear()
        self._incoming.clear()
        for i, edge in enumerate(self._edges):
            self._outgoing.setdefault(edge["from_id"], []).append(i)
            self._incoming.setdefault(edge["to_id"], []).append(i)
