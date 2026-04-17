"""GraphStore Protocol — PEP 544 structural interface for TRUGS graph storage.

See TRUGS_STORE/SPEC_graphstore_protocol.py for full design rationale.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable

from trugs_store.types import Edge, Node


class Violation:
    """A single TRUGS CORE validation violation."""

    __slots__ = ("node_id", "rule", "message", "severity")

    def __init__(
        self,
        node_id: str,
        rule: str,
        message: str,
        severity: str = "error",
    ) -> None:
        self.node_id = node_id
        self.rule = rule
        self.message = message
        self.severity = severity

    def __repr__(self) -> str:
        return f"Violation({self.severity}: {self.rule} on {self.node_id!r})"


@runtime_checkable
class GraphStore(Protocol):
    """Structural protocol for TRUGS graph storage backends.

    22 methods across 8 categories: Node Read (4), Node Write (5),
    Edge Read (4), Edge Write (3), Traversal (2), Subgraph (1),
    Metadata (2), Validation (1).
    """

    # Node Read
    def get_node(self, node_id: str) -> Optional[Node]: ...
    def get_children(self, parent_id: str) -> List[Node]: ...
    def find_nodes(self, *, type: Optional[str] = None, status: Optional[str] = None, stale: Optional[bool] = None, dimension: Optional[str] = None) -> List[Node]: ...
    def node_count(self) -> int: ...

    # Node Write
    def add_node(self, node: Node, *, parent_id: Optional[str] = None) -> None: ...
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None: ...
    def mark_stale(self, node_id: str, reason: str) -> None: ...
    def clear_stale(self, node_id: str) -> None: ...
    def delete_node(self, node_id: str, *, cascade: bool = False) -> None: ...

    # Edge Read
    def get_edges(self, *, from_id: Optional[str] = None, to_id: Optional[str] = None, relation: Optional[str] = None) -> List[Edge]: ...
    def get_outgoing(self, node_id: str) -> List[Edge]: ...
    def get_incoming(self, node_id: str) -> List[Edge]: ...
    def edge_count(self) -> int: ...

    # Edge Write
    def add_edge(self, edge: Edge) -> None: ...
    def update_edge(self, from_id: str, to_id: str, relation: str, *, properties: Optional[Dict[str, Any]] = None, weight: Optional[float] = None) -> None: ...
    def remove_edge(self, from_id: str, to_id: str, relation: str) -> bool: ...

    # Traversal
    def traverse(self, start_id: str, *, direction: str = "outgoing", relation: Optional[str] = None, max_depth: int = 1) -> Iterator[tuple[Node, Edge, int]]: ...
    def get_neighbors(self, node_id: str, *, direction: str = "both") -> List[Node]: ...

    # Subgraph
    def extract_subgraph(self, node_ids: List[str]) -> "GraphStore": ...

    # Metadata
    def get_metadata(self) -> Dict[str, Any]: ...
    def set_metadata(self, key: str, value: Any) -> None: ...

    # Validation
    def validate_graph(self) -> List[Violation]: ...


@runtime_checkable
class PersistenceAdapter(Protocol):
    """Separate protocol for loading/saving graph data (Sans-IO)."""

    def load(self, source: str) -> GraphStore: ...
    def save(self, store: GraphStore, destination: str) -> None: ...
