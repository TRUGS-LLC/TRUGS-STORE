"""GraphStore Protocol — PEP 544 structural interface for TRUGS graph storage.

See TRUGS_STORE/SPEC_graphstore_protocol.py for full design rationale.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable

from trugs_store.types import Edge, Node


# AGENT claude SHALL DEFINE RECORD Violation AS A RECORD validation.
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


# AGENT claude SHALL DEFINE RECORD GraphStore AS A RECORD protocol.
@runtime_checkable
class GraphStore(Protocol):
    """Structural protocol for TRUGS graph storage backends.

    22 methods across 8 categories: Node Read (4), Node Write (5),
    Edge Read (4), Edge Write (3), Traversal (2), Subgraph (1),
    Metadata (2), Validation (1).
    """

    # Node Read
    # PROCESS get_node SHALL READ RECORD node THEN RETURN RECORD result.
    def get_node(self, node_id: str) -> Optional[Node]: ...
    # PROCESS get_children SHALL FILTER ALL RECORD node THEN RETURN RECORD result.
    def get_children(self, parent_id: str) -> List[Node]: ...
    # PROCESS find_nodes SHALL FILTER ALL RECORD node THEN RETURN RECORD result.
    def find_nodes(self, *, type: Optional[str] = None, status: Optional[str] = None, stale: Optional[bool] = None, dimension: Optional[str] = None) -> List[Node]: ...
    # PROCESS node_count SHALL AGGREGATE EACH RECORD node TO INTEGER DATA count.
    def node_count(self) -> int: ...

    # Node Write
    # PROCESS add_node SHALL WRITE RECORD node TO DATA store.
    def add_node(self, node: Node, *, parent_id: Optional[str] = None) -> None: ...
    # PROCESS update_node SHALL WRITE RECORD properties TO DATA node.
    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None: ...
    # PROCESS mark_stale SHALL WRITE RECORD stale TO DATA node.
    def mark_stale(self, node_id: str, reason: str) -> None: ...
    # PROCESS clear_stale SHALL WRITE RECORD stale TO DATA node.
    def clear_stale(self, node_id: str) -> None: ...
    # PROCESS delete_node SHALL REJECT RECORD node.
    def delete_node(self, node_id: str, *, cascade: bool = False) -> None: ...

    # Edge Read
    # PROCESS get_edges SHALL FILTER ALL RECORD edge THEN RETURN RECORD result.
    def get_edges(self, *, from_id: Optional[str] = None, to_id: Optional[str] = None, relation: Optional[str] = None) -> List[Edge]: ...
    # PROCESS get_outgoing SHALL READ RECORD edge THEN RETURN RECORD result.
    def get_outgoing(self, node_id: str) -> List[Edge]: ...
    # PROCESS get_incoming SHALL READ RECORD edge THEN RETURN RECORD result.
    def get_incoming(self, node_id: str) -> List[Edge]: ...
    # PROCESS edge_count SHALL AGGREGATE EACH RECORD edge TO INTEGER DATA count.
    def edge_count(self) -> int: ...

    # Edge Write
    # PROCESS add_edge SHALL WRITE RECORD edge TO DATA store.
    def add_edge(self, edge: Edge) -> None: ...
    # PROCESS update_edge SHALL WRITE RECORD properties TO DATA edge.
    def update_edge(self, from_id: str, to_id: str, relation: str, *, properties: Optional[Dict[str, Any]] = None, weight: Optional[float] = None) -> None: ...
    # PROCESS remove_edge SHALL REJECT RECORD edge.
    def remove_edge(self, from_id: str, to_id: str, relation: str) -> bool: ...

    # Traversal
    # PROCESS traverse SHALL READ RECORD node THEN RETURN ALL RECORD neighbor.
    def traverse(self, start_id: str, *, direction: str = "outgoing", relation: Optional[str] = None, max_depth: int = 1) -> Iterator[tuple[Node, Edge, int]]: ...
    # PROCESS get_neighbors SHALL READ RECORD node THEN RETURN ALL RECORD neighbor.
    def get_neighbors(self, node_id: str, *, direction: str = "both") -> List[Node]: ...

    # Subgraph
    # PROCESS extract_subgraph SHALL FILTER ALL RECORD node THEN RETURN RECORD result.
    def extract_subgraph(self, node_ids: List[str]) -> "GraphStore": ...

    # Metadata
    # PROCESS get_metadata SHALL READ RECORD metadata THEN RETURN RECORD result.
    def get_metadata(self) -> Dict[str, Any]: ...
    # PROCESS set_metadata SHALL WRITE RECORD metadata TO DATA store.
    def set_metadata(self, key: str, value: Any) -> None: ...

    # Validation
    # PROCESS validate_graph SHALL VALIDATE RECORD graph.
    def validate_graph(self) -> List[Violation]: ...


# AGENT claude SHALL DEFINE RECORD PersistenceAdapter AS A RECORD protocol.
@runtime_checkable
class PersistenceAdapter(Protocol):
    """Separate protocol for loading/saving graph data (Sans-IO)."""

    # PROCESS load SHALL READ RECORD graph THEN RETURN RECORD result.
    def load(self, source: str) -> GraphStore: ...
    # PROCESS save SHALL WRITE RECORD graph TO DATA destination.
    def save(self, store: GraphStore, destination: str) -> None: ...
