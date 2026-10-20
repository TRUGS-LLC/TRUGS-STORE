# TRUGS-STORE ↔ TRUGS-TOOLS boundary

This document pins **who owns what** across the two foundational Python packages
of the TRUGS stack, and records the one place the boundary is easy to
misread — the **two-validator split**. It is package self-description.

<trl>
PROCESS boundary_documentation SHALL WRITE RECORD store_ownership THEN WRITE RECORD tools_ownership THEN WRITE RECORD two_validator_split.
</trl>

## The layering, in one line

**TRUGS-TOOLS builds *on* TRUGS-STORE.** STORE is the persistence foundation —
the graph model, the storage backends, and storage-time *structural*
validation. TOOLS operates on graphs as *language*: the TRL parser, the
canonical CORE-16 validator, the audit machinery, and the `trug` CLI.
STORE depends on nothing in TOOLS; TOOLS imports `trugs_store` directly.

## STORE owns (this package)

The persistence layer — *is this a well-formed stored graph, and how is it
stored and retrieved?*

| Surface | Module | Role |
|---|---|---|
| Graph model | `graph.py` (`BaseGraph`) | shared factory methods + accessors |
| In-memory backend | `memory.py` (`InMemoryGraphStore`) | dict-backed store |
| Postgres backend | `postgres.py` (`PostgresGraphStore`) | SQL-backed store |
| JSON-file persistence | `persistence/json_file.py` | load/save `.trug.json` ↔ in-memory |
| Postgres persistence | `persistence/postgres.py` | load/save ↔ PostgreSQL + schema mgmt |
| Dual-write bridge | `persistence/dual_write.py` | JSON + optional Postgres co-write |
| Storage interface | `protocol.py` (`GraphStore`, `PersistenceAdapter`, `Violation`) | PEP 544 contracts |
| **Structural** validation | `validation.py` | v2 LEVEL_PREFIX hierarchy invariants |
| Vocabulary dispatch | `vocabulary.py` | v1/v2 load/save dispatch on declared vocabulary |
| Type shapes | `types.py` (`Node`, `Edge`) | `Dict[str, Any]` aliases for graph elements |
| SQL schema | `schema.sql` | the canonical table shape (cross-stack contract; frozen) |

## TOOLS owns (TRUGS-TOOLS, builds on STORE)

The language layer in trugs-tools 2.4.0 — *is this valid TRL/spec, and what does it
mean?*

| Surface | Module (in `trugs_tools`) | Role |
|---|---|---|
| TRL parser | `trl.py` | compile, decompile and lint TRUG/L |
| **CORE-16 validator** | `validate.py`, `validator.py` | canonical 16-rule TRUG validation (`trug validate`); the library wrapper delegates to it |
| Graph analysis | `trug_graph.py`, `analyzer.py` | hierarchy and edge accessors over STORE's `BaseGraph`; structural graph analysis |
| Structural warnings | `rules.py` | supplementary unreachable/dead-node warnings |
| Validation results | `errors.py` | validation errors, warnings and result formatting |
| Compliance checks | `compliance_check.py` | Dark Code compliance checks |
| Markdown and vocabulary audits | `audit/extract_trl.py`, `audit/vocab_scan.py` | extract and compile TRL blocks; scan their vocabulary |
| CLI | `lang_cli.py`, `tget.py`, `tupdate.py`, `tdelete.py`, `tunlink.py` | the `trug` command surface and explicit-file graph-node operations |

## The two-validator split — deliberate, not drift

There are **two** validators in the stack, and that is **intentional** — a
deliberate division of responsibility, distinct from duplicate-validator
*drift* caused by divergent CLI/API copies of the *same* CORE validator.
These two answer **different questions**:

| Validator | Lives in | Answers | Question |
|---|---|---|---|
| `trugs_store.validation` (`validate_v2_hierarchy`) | **STORE** | structural | *Is this a well-formed **stored graph**?* (v2 LEVEL_PREFIX hierarchy: each parent's `metric_level` strictly coarser than its child's) |
| `trugs_tools` CORE-16 (`trug validate`) | **TOOLS** | language/spec | *Is this valid **TRL/spec**?* (the canonical 16 structural rules over the TRUG envelope) |

STORE's structural checks are available via `store.validate_graph()` and
know nothing about TRL grammar. JSON v2 load also invokes the hierarchy checker
without rejecting violations; PostgreSQL load defers checks to the consumer.
Neither save path invokes validation; v2 saves stamp inherited metric levels.
TOOLS' CORE-16
validator runs at **author/spec time** and is the single source of truth for
"valid TRL". Neither duplicates the other; collapsing them would couple the
persistence layer to the language layer — the opposite of this boundary.

<trl>
PROCESS store_validation SHALL VALIDATE RECORD structural_hierarchy.
PROCESS store_validation SHALL_NOT IMPLEMENT RECORD core16_validation.
</trl>

## What this boundary forbids

- STORE must not grow a TRL parser or the CORE-16 validator (those are TOOLS').
- TOOLS must not fork the graph model, the backends, or `schema.sql` (those are STORE's).
- No code moves across this boundary without a deliberate decision recorded here.

## Why STORE stays its own package

STORE provides persistence independently of the language tooling; TRUGS-TOOLS
imports `trugs_store` directly. A merge into TOOLS was considered and
rejected (it would create coupling, not remove duplication — TOOLS already
cleanly extends STORE's `BaseGraph`); a rename was considered and reversed (a
*store* is where TRUGs — graphs — are stored and found, which reads true, and a
rename would cost a PyPI deprecation plus an import migration).
