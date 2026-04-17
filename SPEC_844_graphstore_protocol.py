"""GraphStore Protocol — PEP 544 structural interface for TRUGS graph storage.

Defines the canonical interface that all graph storage backends must satisfy.
Consumers include benchmark harnesses (STUDY-125), CLI mutation tools
(trugs-folder-sync), and read-only agent extractors (PERAGO executor).

Design decisions documented in ANALYSIS_graphstore_validation.md:
  1. Bidirectional auto-enforcement — add_node with parent_id auto-updates
     the parent's contains[].
  2. Persistence is separate (Sans-IO) — load/save are NOT part of this
     Protocol; they belong to a PersistenceAdapter Protocol.
  3. Query expressiveness — find_nodes accepts multiple optional filters to
     avoid N+1 client-side filtering.
  4. Subgraph extraction — returns a new GraphStore (not a plain dict).
  5. Traversal returns Iterator (lazy) to cap memory for large graphs.
  6. Permissive writes — the store does not enforce TRUGS CORE validation
     rules (metric_level ordering, dimension consistency) on every write.
     Use validate_graph() to check CORE compliance after mutations.
  7. Each write method is a self-contained unit of work. In PostgreSQL
     adapters, each method executes within its own transaction. For
     multi-step mutations that must be atomic, adapters should expose a
     context manager (e.g., ``with store.transaction():``).

TRUGS CORE field reference:
  Node: id, type, properties, metric_level, parent_id, contains, dimension
  Edge: from_id, to_id, relation  (optional: weight, properties)
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Domain value types
# ---------------------------------------------------------------------------

# Nodes and edges are plain dicts matching TRUGS CORE schema.
# Keeping them as dicts (not dataclasses) preserves compatibility with the
# existing codebase which passes raw JSON dicts everywhere.
Node = Dict[str, Any]
Edge = Dict[str, Any]


# ---------------------------------------------------------------------------
# Validation types
# ---------------------------------------------------------------------------

class Violation:
    """A single TRUGS CORE validation violation.

    Attributes:
        node_id: The node (or edge endpoint) that violates a rule.
        rule: Which CORE boundary was violated (e.g., "hierarchy_bidirectional").
        message: Human-readable description of the violation.
        severity: "error" (invalid graph) or "warning" (suspicious but allowed).
    """

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

    Any object that implements these methods with matching signatures
    satisfies the protocol — no inheritance required.

    Grouped by category:
      - Node Read
      - Node Write
      - Edge Read
      - Edge Write
      - Traversal
      - Subgraph
      - Metadata
      - Validation
    """

    # ===================================================================
    # Node Read
    # ===================================================================

    def get_node(self, node_id: str) -> Optional[Node]:
        """Return a single node by ID, or None if not found.

        Complexity: O(1) for in-memory (dict lookup), single SQL query
        for PostgreSQL.
        """
        ...

    def get_children(self, parent_id: str) -> List[Node]:
        """Return all nodes whose parent_id equals *parent_id*.

        Complexity: O(degree) for in-memory, single indexed SQL query
        for PostgreSQL.
        """
        ...

    def find_nodes(
        self,
        *,
        type: Optional[str] = None,
        status: Optional[str] = None,
        stale: Optional[bool] = None,
        dimension: Optional[str] = None,
    ) -> List[Node]:
        """Return nodes matching ALL supplied filters (AND semantics).

        Filters are optional keyword-only arguments.  Passing no filters
        returns all nodes.

        Complexity: O(N) scan for in-memory, single WHERE-clause SQL
        query for PostgreSQL.  Avoids N+1 by pushing filters to the store.
        """
        ...

    def node_count(self) -> int:
        """Return total number of nodes in the graph.

        Complexity: O(1) for both in-memory and PostgreSQL (COUNT(*) or
        maintained counter).
        """
        ...

    # ===================================================================
    # Node Write
    # ===================================================================

    def add_node(self, node: Node, *, parent_id: Optional[str] = None) -> None:
        """Insert a new node into the graph.

        If *parent_id* is provided, the store MUST:
          1. Set node["parent_id"] = parent_id.
          2. Append node["id"] to parent.contains[].
          3. Create a ("contains", parent_id -> node_id) edge.

        This enforces bidirectional consistency as an invariant of the
        store rather than leaving it to callers.

        Cycle prevention: if *parent_id* is provided, the store SHOULD
        walk up the ancestor chain (depth-limited to 100 hops) to verify
        that *node["id"]* does not already appear as an ancestor of
        *parent_id*.  If a cycle is detected, raise ValueError.

        Raises ValueError if node["id"] already exists.
        Raises KeyError if parent_id is provided but does not exist.
        Raises ValueError if adding the node would create a hierarchy cycle.

        Note: this method does NOT validate TRUGS CORE rules (metric_level
        ordering, dimension consistency).  Use validate_graph() for that.

        Transaction semantics: this method is a self-contained unit of
        work.  In PostgreSQL adapters, all three steps (insert node,
        update parent, create edge) execute within a single transaction.

        PostgreSQL implementation note: use array_append() for the
        parent.contains update — it is atomic within a single UPDATE
        statement.  Do NOT read-modify-write the array.
        """
        ...

    def update_node(self, node_id: str, properties: Dict[str, Any]) -> None:
        """Merge *properties* into an existing node's properties dict.

        Shallow merge only: top-level keys in *properties* overwrite the
        corresponding keys in the node's existing properties.  Nested
        objects are replaced entirely, not recursively merged.

        Example:
            Existing: {"metadata": {"version": 1, "author": "alice"}, "tags": ["a"]}
            update_node(id, {"metadata": {"author": "bob"}})
            Result:   {"metadata": {"author": "bob"}, "tags": ["a"]}
            Note: "version" key is lost — shallow merge replaces the
            entire "metadata" dict.  Callers needing deep merge must
            read, merge in Python, and write back.

        Only keys present in *properties* are updated; existing keys not
        in the argument are preserved (patch semantics at the top level).

        Raises KeyError if node_id does not exist.
        """
        ...

    def mark_stale(self, node_id: str, reason: str) -> None:
        """Set stale=True and stale_reason on a node's properties.

        Convenience method used heavily by folder-sync.
        Equivalent to update_node(id, {"stale": True, "stale_reason": reason})
        but expressed as a semantic operation.

        Raises KeyError if node_id does not exist.
        """
        ...

    def clear_stale(self, node_id: str) -> None:
        """Remove stale and stale_reason from a node's properties.

        Raises KeyError if node_id does not exist.
        """
        ...

    def delete_node(self, node_id: str, *, cascade: bool = False) -> None:
        """Remove a node from the graph.

        Behavior depends on *cascade*:

        cascade=False (default):
          - Raises ValueError if the node has children (non-empty contains[]).
          - Removes all edges where from_id or to_id equals node_id.
          - Removes node_id from parent.contains[] if the node has a parent.
          - Deletes the node.

        cascade=True:
          - Recursively deletes all descendants (children, grandchildren, etc.).
          - Removes all edges involving any deleted node.
          - Removes node_id from parent.contains[] if the node has a parent.
          - Deletes the node and all descendants.

        Raises KeyError if node_id does not exist.
        Raises ValueError if cascade=False and the node has children.

        Transaction semantics: the entire delete (including cascade) is
        a single unit of work.
        """
        ...

    # ===================================================================
    # Edge Read
    # ===================================================================

    def get_edges(
        self,
        *,
        from_id: Optional[str] = None,
        to_id: Optional[str] = None,
        relation: Optional[str] = None,
    ) -> List[Edge]:
        """Return edges matching ALL supplied filters (AND semantics).

        Passing no filters returns all edges.

        Returned edge dicts include all fields present in the stored edge,
        including optional ``weight`` and ``properties`` if they exist.

        Complexity: O(degree) for in-memory when from_id or to_id is
        specified (adjacency index), single SQL query for PostgreSQL.
        """
        ...

    def get_outgoing(self, node_id: str) -> List[Edge]:
        """Return all edges where from_id == node_id.

        Shorthand for get_edges(from_id=node_id).

        Complexity: O(degree) for in-memory, indexed SQL for PostgreSQL.
        """
        ...

    def get_incoming(self, node_id: str) -> List[Edge]:
        """Return all edges where to_id == node_id.

        Shorthand for get_edges(to_id=node_id).

        Complexity: O(degree) for in-memory, indexed SQL for PostgreSQL.
        """
        ...

    def edge_count(self) -> int:
        """Return total number of edges in the graph.

        Complexity: O(1).
        """
        ...

    # ===================================================================
    # Edge Write
    # ===================================================================

    def add_edge(self, edge: Edge) -> None:
        """Insert a new edge into the graph.

        The edge dict MUST contain ``from_id``, ``to_id``, and ``relation``.
        It MAY also contain ``weight`` (float, 0.0-1.0) and ``properties``
        (dict).

        Endpoint validation: the store MUST validate that both from_id
        and to_id reference existing nodes, UNLESS the ID contains a
        colon (``:``) indicating a cross-graph reference (e.g.,
        "FOLDER_NAME:node_id").  Cross-graph endpoints are stored as-is
        without validation.

        Duplicate edges (same from_id, to_id, relation) are silently
        ignored.  If the duplicate has different weight or properties,
        the existing edge is NOT updated — use update_edge() for that.

        Raises KeyError if a local endpoint (no colon) does not exist.
        """
        ...

    def update_edge(
        self,
        from_id: str,
        to_id: str,
        relation: str,
        *,
        properties: Optional[Dict[str, Any]] = None,
        weight: Optional[float] = None,
    ) -> None:
        """Update an existing edge's weight and/or properties.

        Only the supplied keyword arguments are applied:
          - If *properties* is provided, it replaces the edge's properties
            dict entirely (not merged).
          - If *weight* is provided, it replaces the edge's weight.

        This avoids the non-atomic delete-then-recreate pattern.

        Raises KeyError if no edge with (from_id, to_id, relation) exists.
        """
        ...

    def remove_edge(
        self, from_id: str, to_id: str, relation: str
    ) -> bool:
        """Remove a specific edge.  Returns True if an edge was removed.

        Complexity: O(degree) for in-memory, single SQL DELETE for
        PostgreSQL.
        """
        ...

    # ===================================================================
    # Traversal
    # ===================================================================

    def traverse(
        self,
        start_id: str,
        *,
        direction: str = "outgoing",
        relation: Optional[str] = None,
        max_depth: int = 1,
    ) -> Iterator[tuple[Node, Edge, int]]:
        """Yield (node, edge, depth) tuples via BFS from *start_id*.

        Args:
            start_id: Node to begin traversal from.
            direction: "outgoing", "incoming", or "both".
            relation: If set, only follow edges of this relation type.
            max_depth: Maximum hops from start_id (inclusive).

        Returns an Iterator (lazy) to avoid materialising the full
        frontier for large graphs.  Callers needing a list can wrap
        with list().

        Complexity per step: O(degree) for in-memory, recursive CTE or
        repeated single-hop queries for PostgreSQL.

        Raises KeyError if start_id does not exist.
        """
        ...

    def get_neighbors(
        self,
        node_id: str,
        *,
        direction: str = "both",
    ) -> List[Node]:
        """Return immediate neighbor nodes (depth=1 traversal).

        Shorthand for materialising traverse(node_id, direction=direction,
        max_depth=1) and extracting just the nodes.

        Complexity: O(degree).
        """
        ...

    # ===================================================================
    # Subgraph
    # ===================================================================

    def extract_subgraph(self, node_ids: List[str]) -> "GraphStore":
        """Return a new GraphStore containing only the specified nodes
        and any edges where both endpoints are in node_ids.

        Node IDs that do not exist in the store are silently skipped.

        The returned store is a fully functional GraphStore (same
        protocol), enabling recursive composition and testing.

        Complexity: O(|node_ids| + |edges|) for in-memory, single SQL
        query with IN clause for PostgreSQL.
        """
        ...

    # ===================================================================
    # Metadata
    # ===================================================================

    def get_metadata(self) -> Dict[str, Any]:
        """Return top-level graph metadata (name, version, description,
        dimensions, capabilities, etc.).

        The returned dict is a shallow copy; mutations do not affect
        the store.
        """
        ...

    def set_metadata(self, key: str, value: Any) -> None:
        """Update a single top-level metadata field.

        Used by folder-sync to update version and description from
        pyproject.toml.
        """
        ...

    # ===================================================================
    # Validation
    # ===================================================================

    def validate_graph(self) -> List[Violation]:
        """Check the graph against TRUGS CORE invariants.

        Returns a list of Violation objects.  An empty list means the
        graph is fully CORE-compliant.

        Checks performed:
          1. Bidirectional hierarchy — if node.parent_id = X, then
             X.contains includes node.id, and vice versa.
          2. Hierarchy is a DAG — no cycles in parent/child chains.
          3. Dimension consistency — parent and child share the same
             dimension (CORE Boundary 4).
          4. Metric level ordering — parent metric_level >= child
             metric_level within the same dimension (CORE Boundary 4).
          5. Dimension declaration — every node.dimension is declared
             in graph metadata["dimensions"] (CORE Boundary 3).
          6. Edge endpoint existence — from_id and to_id reference
             existing nodes (skips cross-graph refs with ':').
          7. Required node fields — every node has id, type, properties,
             parent_id, contains, metric_level, dimension.
          8. Required edge fields — every edge has from_id, to_id,
             relation.

        This method is read-only and does not modify the graph.

        Complexity: O(N + E) where N = nodes, E = edges.
        """
        ...


# ---------------------------------------------------------------------------
# Persistence Adapter — separate from GraphStore (Sans-IO)
# ---------------------------------------------------------------------------

@runtime_checkable
class PersistenceAdapter(Protocol):
    """Separate protocol for loading/saving graph data.

    Keeping persistence out of GraphStore follows the Sans-IO pattern:
    graph logic operates on the in-memory GraphStore without knowing
    whether data came from a JSON file, PostgreSQL, or a test fixture.

    Implementors:
      - JsonFilePersistence: load/save from folder.trug.json
      - PostgresPersistence: load/save from SQL tables

    For PostgresPersistence, *source* is a graph_id string that scopes
    all queries to the ``graphs``, ``nodes``, and ``edges`` tables where
    ``graph_id`` matches.  Each loaded GraphStore operates on exactly one
    graph.  To work with multiple graphs, load each one separately.

    Bulk loading: PostgresPersistence.load() SHOULD use the PostgreSQL
    COPY protocol (via psycopg3) for graphs with >1000 nodes, as this
    is orders of magnitude faster than individual INSERTs.
    """

    def load(self, source: str) -> GraphStore:
        """Load graph data from *source* and return a populated GraphStore.

        The meaning of *source* is backend-specific:
          - file path for JsonFilePersistence
          - graph_id for PostgresPersistence
        """
        ...

    def save(self, store: GraphStore, destination: str) -> None:
        """Persist the current state of *store* to *destination*."""
        ...
