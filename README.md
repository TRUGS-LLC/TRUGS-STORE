# trugs-store

**Graph storage backends for TRUGS specifications — InMemory, PostgreSQL, JSON file persistence.**

trugs-store is the shared persistence layer for all TRUGS tooling. Every tool that reads or writes `.trug.json` files goes through this package. It supports JSON file storage for development and PostgreSQL for production scale.

## Install

```bash
pip install trugs-store

# With PostgreSQL support:
pip install trugs-store[postgres]
```

## Quick Example

```python
from trugs_store import InMemoryGraphStore, JsonFilePersistence

# Load a .trug.json file
persistence = JsonFilePersistence()
store = persistence.load("folder.trug.json")

# Query
print(store.node_count())
print(store.find_nodes(type="FUNCTION"))

# Validate against TRUGS CORE rules
violations = store.validate_graph()
for v in violations:
    print(f"{v.severity}: {v.rule} — {v.message}")
```

## Architecture

| Component | What it does |
|---|---|
| `GraphStore` protocol | PEP 544 structural interface — 22 methods across 8 categories |
| `InMemoryGraphStore` | Dict-backed store — O(1) node lookup, O(degree) edge access |
| `PostgresGraphStore` | SQL-backed store — indexed queries, transactional writes, COPY bulk insert |
| `JsonFilePersistence` | Load/save `.trug.json` files to/from `InMemoryGraphStore` |
| `PostgresPersistence` | Load/save graphs to/from PostgreSQL |
| Dual-write bridge | `write_trug()` / `read_trug()` — writes JSON + optionally PostgreSQL |

## Basic Usage

### Load and query a TRUG

```python
from trugs_store import JsonFilePersistence

p = JsonFilePersistence()
store = p.load("folder.trug.json")

# Find all FUNCTION nodes
functions = store.find_nodes(type="FUNCTION")

# Traverse outgoing edges from a node
for node, edge, depth in store.traverse("root", direction="outgoing", max_depth=2):
    print(f"  {'  ' * depth}{node['id']} via {edge['relation']}")
```

### Create a graph in memory

```python
from trugs_store import InMemoryGraphStore

store = InMemoryGraphStore()
store.set_metadata("name", "my_graph")
store.set_metadata("version", "1.0.0")

store.add_node({"id": "root", "type": "FOLDER", "properties": {},
                "parent_id": None, "contains": [], "metric_level": "KILO_FOLDER",
                "dimension": "main"})
store.add_node({"id": "child", "type": "DOCUMENT", "properties": {},
                "parent_id": None, "contains": [], "metric_level": "BASE_DOCUMENT",
                "dimension": "main"}, parent_id="root")
store.add_edge({"from_id": "root", "to_id": "child", "relation": "REFERENCES"})

print(store.node_count())  # 2
print(store.get_children("root"))  # [child node]
```

### Validate a graph

```python
violations = store.validate_graph()
if violations:
    for v in violations:
        print(f"{v.severity}: {v.rule} on {v.node_id} — {v.message}")
else:
    print("Graph is valid.")
```

## Documentation

- **TRUGS Specification:** [TRUGS-LLC/TRUGS](https://github.com/TRUGS-LLC/TRUGS) — protocol, language, validator
- **GraphStore Protocol:** [SPEC_844_graphstore_protocol.py](SPEC_844_graphstore_protocol.py) — full PEP 544 interface
- **TRUG Graph Index:** [folder.trug.json](folder.trug.json) — machine-readable structure of this repo
- **Dark Code Standard:** [TRUGS-LLC/TRUGS/REFERENCE/STANDARD_dark_code_compliance.md](https://github.com/TRUGS-LLC/TRUGS/blob/main/REFERENCE/STANDARD_dark_code_compliance.md)

## Status

**Version:** 0.1.0
**Phase:** Beta
**License:** Apache 2.0 — [TRUGS LLC](https://github.com/TRUGS-LLC)
