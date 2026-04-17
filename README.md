# TRUGS_STORE

Canonical graph I/O for all `.trug.json` access — the single persistence layer for reading and writing TRUG graphs.

## Purpose

trugs-store is the shared contract between Python tools (trugs-tools) and Go services (PORT). All graph persistence goes through this package. It supports JSON file storage now and PostgreSQL for production scale.

## Architecture

- **GraphStore protocol** — abstract interface for graph persistence
- **JSON backend** — file-based storage for development and small deployments
- **PostgreSQL backend** — relational storage for 10K+ nodes, concurrent writers, PORT
- **Dual-write bridge** — writes to both JSON and PostgreSQL during migration

## Key Files

| File | Purpose |
|------|---------|
| `trugs-store/src/trugs_store/graph_store.py` | GraphStore protocol definition |
| `trugs-store/src/trugs_store/persistence/json_store.py` | JSON file backend |
| `trugs-store/src/trugs_store/persistence/pg_store.py` | PostgreSQL backend |
| `trugs-store/src/trugs_store/persistence/dual_write.py` | Dual-write bridge |
| `SPEC_844_graphstore_protocol.py` | Protocol specification |

## Installation

```bash
pip install -e TRUGS_STORE/trugs-store/
```

## Status

CODING — JSON and PostgreSQL backends shipped, dual-write bridge active, nightly GitHub mirror exports (Phase 6 complete).
