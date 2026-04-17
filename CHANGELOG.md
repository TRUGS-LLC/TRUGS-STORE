# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-16

### Added
- `InMemoryGraphStore` — dict-backed GraphStore with O(1) node lookup, O(degree) edge access
- `PostgresGraphStore` — SQL-backed GraphStore with indexed queries, transactional writes, COPY bulk insert
- `JsonFilePersistence` — load/save `.trug.json` files to/from `InMemoryGraphStore`
- `PostgresPersistence` — load/save graphs to/from PostgreSQL with schema management
- Dual-write bridge (`write_trug`, `read_trug`, `export_trug`, `import_trug`) — JSON + optional PostgreSQL
- `GraphStore` protocol — PEP 544 structural interface, 22 methods across 8 categories
- `PersistenceAdapter` protocol — load/save abstraction
- `Violation` class — structured validation errors
- `BaseGraph` — shared factory methods (`from_dict`, `from_json`, `from_file`) and accessors
- TRUGS CORE graph validation (hierarchy, cycles, dimensions, required fields, edge validity)
- 116 tests (InMemory round-trip, conformance, integration, dual-write, benchmarks)
- CI workflow (pytest + mypy on every PR)
- Apache 2.0 license under TRUGS LLC

### Notes
- PostgreSQL support requires `pip install trugs-store[postgres]` (psycopg3)
- Schema created automatically via `PostgresPersistence.ensure_schema()`
- Migrated from `Xepayac/TRUGS-STORE` to `TRUGS-LLC/TRUGS-STORE` for public release
