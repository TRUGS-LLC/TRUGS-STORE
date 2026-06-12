# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [2.0.0] — 2026-06-12

Tier-1 release polish for the TRUGS v2.0 launch — [TRUGS-DEVELOPMENT AAA #2330](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/AAA/AAA_2330_phase7_trugs_store_tier1_polish.md) (Phase 7 Repo 3/4), Sub-phases 1–4 — L1 baseline, L2 structural cleanups, L3 TRL contracts, the STORE↔TOOLS boundary doc, and L4 self-validation. **No public-API change** (the `GraphStore` protocol, package name, and `schema.sql` are all unchanged). One small behavior change: the SI-prefix correctness fix below (`DECA` → `DEKA`).

**Version note:** published as **2.0.0** in lockstep with `trugs-tools`/`trugs-folder` 2.0.0 (the TRUGS 2.0 commons kit, per the v2 package manifest). The `[0.2.0]` entry below was repo-internal and never published to PyPI; PyPI jumps 0.1.0 → 2.0.0.

### Added
- **Commons-kit metadata (TRUGS-DEVELOPMENT AAA #2416 SP5):** `Documentation` and
  `Changelog` URL keys on the package metadata. `trugs-store` 2.0.0 ships as the
  storage tier of the TRUGS 2.0 commons kit — `trugs-tools` 2.0 (`trug`) and
  `trugs-folder` 2.0 (`trug-a-folder`) both sit on it.

### Fixed
- **SI-prefix lexicon drift (`DECA` → `DEKA`, SP4):** `validation.py`'s `SI_PREFIX_ORDERING` spelled the 10^1 prefix `"DECA"`, while the canonical v2 lexicon and the CORE-16 validator use `"DEKA"`. Consequence: `prefix_of("DEKA_…")` returned `None`, so `validate_v2_hierarchy` **silently skipped** the hierarchy check on canonically-spelled nodes (and `_stamp_inherited_metric_levels` stamped `DECA_*`). Now the store recognizes `DEKA` and the shipped `folder.trug.json` validates **non-vacuously**. (Behavior change: nodes that previously passed by being skipped are now actually checked.)

### Changed
- `ruff format` + `ruff check` applied across the package; both are now **hard** CI gates (previously soft `continue-on-error`).
- `folder.trug.json` corrected to validate clean under the v2 CORE-16 validator and folder-governance check: `DECA_COMPONENT` → `DEKA_COMPONENT` (the valid SI prefix) and edge relations lowercased (`CONTAINS`/`IMPLEMENTS` → `contains`/`implements`).
- CI hardened against env-dependent silent-skip ([store-dev#16](https://github.com/TRUGS-LLC/TRUGS-STORE-dev/issues/16) / AAA #1756 AF-3): the `postgres-tests` job now fails loudly if `TRUGS_TEST_DSN` is unset or the gated tests no-op.
- **L3 TRL contracts (SP2):** every concrete public class and function/method now carries a `<trl>` contract block in its docstring (Protocol method stubs excluded — their interface contract lives on the `GraphStore` class docstring). `validation.py` gained a scope-documenting contract recording that it is STORE's *structural* validator, deliberately distinct from the CORE-16 TRL validator in TRUGS-TOOLS.

### Added
- **`BOUNDARY.md` (SP3):** package self-description pinning what STORE owns vs what TRUGS-TOOLS owns, and recording the two-validator split (STORE structural vs TOOLS CORE-16) as a deliberate division — not the #2189 drift. Linked from the README.
- `tests/test_ci_meta.py` — structural CI-contract guard that parses `.github/workflows/ci.yml` and asserts the env-dependent tests can never silent-skip; `pyyaml` added to the `dev` extra.
- `tests/test_l3_contracts.py` — AST scanner enforcing the L3 contract (every public surface carries a `<trl>` block).
- `tests/test_round_trip.py` — `store ∘ retrieve = identity` across in-memory / JSON-file / Postgres backends (the load-bearing L3 behavioral law); its Postgres leg is added to the CI must-run gated set.
- `tests/test_boundary_doc.py` — smoke checks that `BOUNDARY.md` records ownership + the deliberate two-validator split.
- `tests/test_l4_self_validation.py` — the shipped `folder.trug.json` validates **non-vacuously** under the v2 lexicon (every node's prefix recognized; 0 violations) — the L4 self-validation gate + a regression guard for the `DECA`/`DEKA` drift.

### Removed
- Empty `src/trugs_store/persistence/__init__.py` — the persistence subpackage is now an implicit namespace package; public imports unchanged.
- `PROPOSAL/` — planning docs must not ship in a public-bound repo (ADR-007); the one live doc (a TRUGS 2.0 integration-readiness assessment, since overtaken) was archived to TRUGS-DEVELOPMENT `zzz_ARCHIVE/`.

## [0.2.0] - 2026-05-11

Native support for **TRUGS 2.0** (`core_v2.0.0`) — additive, fully backward compatible. v1 TRUGs (`core_v1.0.0`, `project_v1`) validate unchanged. See [TRUGS-DEVELOPMENT AAA #1756](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/AAA/AAA_1756_trugs_store_2_0_hierarchy_first_adoption.md) for the full design.

### Added
- `trugs_store.vocabulary` — `classify_vocabulary(metadata)` dispatches load/save on declared `capabilities.vocabularies`. Returns `"v1"` for `core_v1.0.0` / `project_v1` / no declaration; `"v2"` when `core_v2.0.0` is present (v2 wins on mixed declarations).
- `trugs_store.validation` — LEVEL_PREFIX hierarchy invariants for v2 TRUGs. Exports `SI_PREFIX_ORDERING` (the 21 SI prefixes, YOTTA coarsest → YOCTO finest), `prefix_of(metric_level)`, and `validate_v2_hierarchy(store)` emitting `Violation(rule="level_prefix_hierarchy", severity="error")` when a parent node's `metric_level` does NOT strictly EXCEED its child's in `SI_PREFIX_ORDERING`.
- `BaseGraph._stamp_inherited_metric_levels(store)` (internal, ADR-002) — fills missing `metric_level` on v2 nodes by inheriting one step finer from the parent's SI prefix. Runs only on v2-path dispatch.
- `JsonFilePersistence` v2 path:
  - `_load_v2` calls `validate_v2_hierarchy(store)` as a side effect; violations also surface through `store.validate_graph()`.
  - `_save_v2` stamps inherited metric levels, emits every node with `metric_level` explicit, and writes a top-level `level_directives` field listing each `metric_level` at every transition in node order.
- `PostgresPersistence` v2 path — same dispatch + stamping on save; validation surfaces through `store.validate_graph()` on the consumer side. Postgres schema unchanged.
- `InMemoryGraphStore.validate_graph` now dispatches on declared vocabulary; when `core_v2.0.0` is declared, appends `validate_v2_hierarchy(self)` violations to the v1 generic checks. v1 TRUGs SKIP the LEVEL_PREFIX checks.
- Self-dogfood: TRUGS-STORE-dev's own `folder.trug.json` declares `core_v2.0.0` and self-validates clean. Round-trip is byte-equivalent.
- New tests: `tests/test_v2_validation.py` (11), `tests/test_canonical_reemit.py` (12), `tests/test_self_validation.py` (6). Total: 157 collected, 134 passing in standard CI (23 Postgres tests need a live DB).

### Notes
- **PyPI publish deferred** until in-house validation completes. During that window, internal consumers install from this repository directly — see [README §"Pre-PyPI install (TRUGS 2.0)"](README.md#pre-pypi-install-trugs-20) for both editable and tag-install patterns.
- GraphStore Protocol shape unchanged (22 methods, 8 categories). Public API signatures byte-stable across the 0.1.x → 0.2.x bump.
- Postgres schema unchanged — no migration required.
- mypy `--strict` clean across all 12 source files.
- First-canary consumer migrated: `TRUGS-DEVELOPMENT/AGENT/memory/memory.trug.json` now declares `["core_v1.0.0", "core_v2.0.0"]` and round-trips through trugs-store at 0.2.0 without error. Clean-shell `tg memory recall` against the older trugs-store 0.1.0 still works — backward compat proven through the mixed-vocabulary declaration.

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
