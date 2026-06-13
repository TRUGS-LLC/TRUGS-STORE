# AGENT.md — trugs-store

This file teaches an LLM agent how to work in this repository.

## What This Repo Is

trugs-store is the graph persistence layer for TRUGS. It provides `InMemoryGraphStore`, `PostgresGraphStore`, `JsonFilePersistence`, and a dual-write bridge. Every tool that reads or writes `.trug.json` files depends on this package.

As of **0.2.0**, trugs-store natively supports **TRUGS 2.0** (`core_v2.0.0`): vocabulary dispatch by declared `capabilities.vocabularies`, LEVEL_PREFIX hierarchy validation in `trugs_store.validation`, inheritance stamping via `BaseGraph._stamp_inherited_metric_levels`, and canonical re-emit on save in the JSON adapter. v1 TRUGs (`core_v1.0.0`, `project_v1`) continue to validate unchanged.

**Package:** `trugs-store` (PyPI)
**License:** Apache 2.0
**Org:** [TRUGS-LLC](https://github.com/TRUGS-LLC)

## Navigation

| Path | What |
|---|---|
| `trugs-store/src/trugs_store/` | Python package source |
| `trugs-store/src/trugs_store/protocol.py` | `GraphStore` protocol — PEP 544, 22 methods |
| `trugs-store/src/trugs_store/memory.py` | `InMemoryGraphStore` — dict-backed implementation |
| `trugs-store/src/trugs_store/postgres.py` | `PostgresGraphStore` — SQL-backed implementation |
| `trugs-store/src/trugs_store/persistence/` | Load/save adapters (JSON file, PostgreSQL, dual-write) |
| `trugs-store/src/trugs_store/vocabulary.py` | v1/v2 dispatch by declared `capabilities.vocabularies` |
| `trugs-store/src/trugs_store/validation.py` | LEVEL_PREFIX hierarchy invariants for v2 TRUGs |
| `trugs-store/tests/` | Test suite (157+ tests: vocabulary dispatch, v2 validation, canonical re-emit, self-validation) |
| `SPEC_844_graphstore_protocol.py` | Full protocol specification |
| `folder.trug.json` | Machine-readable graph index of this repo |

## Development

```bash
# Install (editable + dev deps)
pip install -e trugs-store[dev]

# Run tests
pytest trugs-store/tests/ -v

# Type check
mypy trugs-store/src/trugs_store --ignore-missing-imports
```

## TRUG/L Conventions

This repo follows the [Dark Code compliance standard](https://github.com/TRUGS-LLC/TRUGS/blob/main/REFERENCE/STANDARD_dark_code_compliance.md):

- Every public `def`/`class` has a function-level TRUG/L comment above it
- Every test function has an `AGENT SHALL VALIDATE ...` comment
- `folder.trug.json` validates against TRUGS CORE rules
- When writing TRUG/L in prose, always spell it "TRUG/L" — never abbreviate

## Branching

All changes require a branch and PR. No direct commits to main. Human merges all PRs (HITM rule).
