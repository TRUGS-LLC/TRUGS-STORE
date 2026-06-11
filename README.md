# trugs-store

**Graph storage backends for TRUGS specifications — InMemory, PostgreSQL, JSON file persistence.**

trugs-store is the shared persistence layer for all TRUGS tooling. Every tool that reads or writes `.trug.json` files goes through this package. It supports JSON file storage for development and PostgreSQL for production scale.

## Install

```bash
pip install trugs-store

# With PostgreSQL support:
pip install trugs-store[postgres]
```

> The PyPI release tracks the **0.1.x** line. Internal consumers needing **TRUGS 2.0** (`core_v2.0.0`, LEVEL_PREFIX validation, canonical re-emit) install **0.2.x** directly from this repository — see [Pre-PyPI install (TRUGS 2.0)](#pre-pypi-install-trugs-20) below.

## Pre-PyPI install (TRUGS 2.0)

`trugs-store` **0.2.x** adds native `core_v2.0.0` support (per [AAA #1756](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/AAA/AAA_1756_trugs_store_2_0_hierarchy_first_adoption.md)): vocabulary dispatch on `capabilities.vocabularies`, LEVEL_PREFIX hierarchy validation, inheritance stamping, and canonical re-emit on save. v1 TRUGs (`core_v1.0.0`, `project_v1`) continue to validate unchanged — the upgrade is purely additive.

**PyPI release of 0.2.x is deferred** until in-house validation finishes (per AAA #1756 ADR-005 / HITM 2026-05-11). During that window, internal consumers install from this repository directly:

### Option A — Editable install from a worktree (plan-author dev, first-canary)

Use when you are iterating on `trugs-store` itself or running the first-canary consumer migration. Fast feedback loop; no tag ceremony.

```bash
# 1. Clone (or `git worktree add`) into a sibling directory:
git clone https://github.com/TRUGS-LLC/TRUGS-STORE-dev.git
cd TRUGS-STORE-dev
git checkout feat/1756-hierarchy-first-adoption  # the AAA #1756 ship branch

# 2. Install the package in editable mode from the worktree's subdirectory:
pip install -e ./trugs-store

# 3. Verify v2 support:
python -c "from trugs_store.vocabulary import classify_vocabulary; \
           print(classify_vocabulary({'capabilities': {'vocabularies': ['core_v2.0.0']}}))"
# -> v2
```

### Option B — Tag install (consumer rollout)

Use when you are migrating a downstream consumer and want a pinned, reproducible version. Tag-based install survives worktree churn and is the recommended pattern for sister repos in the TRUGS portfolio.

```bash
# Once a release tag (e.g. v0.2.0) is pushed to TRUGS-STORE-dev:
pip install "git+https://github.com/TRUGS-LLC/TRUGS-STORE-dev.git@v0.2.0#subdirectory=trugs-store"

# With PostgreSQL extras:
pip install "git+https://github.com/TRUGS-LLC/TRUGS-STORE-dev.git@v0.2.0#subdirectory=trugs-store[postgres]"
```

Pin the tag explicitly — never install from `@main` for production consumers, since `main` advances as further sub-phases land.

### Why not Test PyPI or local wheels?

Considered and rejected in AAA #1756 ADR-005:

- **Test PyPI** pollutes the `trugs-store` namespace and breaks the rule that PyPI carries only released versions.
- **Local wheels** (`pip install dist/trugs_store-0.2.0-py3-none-any.whl`) work mechanically but don't exercise the install-from-spec contract that downstream consumers actually use — they hide install-time mistakes that show up only over the network.

Editable (Option A) gives a tight inner loop; tag install (Option B) gives a reproducible outer loop. Both exercise the real install path.

### Verifying a v2 install

```python
from trugs_store import JsonFilePersistence
from trugs_store.vocabulary import classify_vocabulary
from trugs_store.validation import SI_PREFIX_ORDERING

# Sanity check: v2 vocabulary recognized, validator module loadable, SI prefixes present.
assert classify_vocabulary({"capabilities": {"vocabularies": ["core_v2.0.0"]}}) == "v2"
assert "BASE" in SI_PREFIX_ORDERING

# Round-trip a v2 TRUG (e.g. this repo's own folder.trug.json):
store = JsonFilePersistence().load("folder.trug.json")
assert store.validate_graph() == []  # this repo self-validates under core_v2.0.0
print("OK — trugs-store 0.2.x v2 path active")
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

**Version:** 0.2.0 (TRUGS 2.0 native — first release with `core_v2.0.0` support)
**Phase:** Beta
**License:** Apache 2.0 — [TRUGS LLC](https://github.com/TRUGS-LLC)
