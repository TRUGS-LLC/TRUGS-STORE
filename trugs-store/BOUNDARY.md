# TRUGS-STORE ↔ TRUGS-TOOLS boundary

This document pins **who owns what** across the two foundational Python packages
of the TRUGS stack, and records the one place the boundary is easy to
misread — the **two-validator split**. It is package self-description (an L2
Tier-1 artifact), authored under
[TRUGS-DEVELOPMENT AAA #2330](https://github.com/Xepayac/TRUGS-DEVELOPMENT/blob/main/AAA/AAA_2330_phase7_trugs_store_tier1_polish.md)
(Phase 7 Repo 3/4), Sub-phase 3.

<trl>
RECORD boundary_ownership_doc SHALL RECORD store_ownership AND tools_ownership AND two_validator_split.
</trl>

## The layering, in one line

**TRUGS-TOOLS builds *on* TRUGS-STORE.** STORE is the persistence foundation —
the graph model, the storage backends, and storage-time *structural*
validation. TOOLS is everything that operates on stored graphs as
*language*: the TRL parser, the canonical CORE-16 validator, the audit
machinery, memory cognition, and the `tg` CLI. STORE depends on nothing in
TOOLS; TOOLS imports `trugs_store` directly.

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
| Type shapes | `types.py` (`Node`, `Edge`) | `TypedDict` graph element shapes |
| SQL schema | `schema.sql` | the canonical table shape (cross-stack contract; frozen) |

## TOOLS owns (TRUGS-TOOLS, builds on STORE)

The language/cognition layer — *is this valid TRL/spec, and what does it
mean?*

| Surface | Module (in `trugs_tools`) | Role |
|---|---|---|
| TRL parser | `trl.py` | compile/lint TRUG/L sentences ↔ graph |
| **CORE-16 validator** | `validate.py`, `validator.py` | the canonical 16-rule TRL/spec validator (`tg validate`) |
| Audit machinery | `analyzer.py`, `compliance_check.py`, `rules.py`, `errors.py` | Dark-Code + markdown/vocab audits |
| Memory cognition | `memory_*.py` (render, recall, reorganizer, audit, import) | the weighted-substrate memory system |
| AAA / EPIC tooling | `aaa_*.py`, `epic_sync.py` | protocol surfaces |
| Renderers | `renderer.py`, `*_renderer.py`, `trug_graph.py` | views over stored graphs |
| CLI | `cli.py`, `tg_events.py`, `tget.py`, `tupdate.py`, … | the `tg` command surface |

## The two-validator split — deliberate, not drift

There are **two** validators in the stack, and that is **intentional** — a
deliberate division of responsibility, **not** the kind of duplicate-validator
*drift* that [TRUGS-TOOLS-dev #2189](https://github.com/Xepayac/TRUGS-DEVELOPMENT/issues/2189)
collapsed (two CLI/API copies of the *same* CORE validator that had diverged).
These two answer **different questions**:

| Validator | Lives in | Answers | Question |
|---|---|---|---|
| `trugs_store.validation` (`validate_v2_hierarchy`) | **STORE** | structural | *Is this a well-formed **stored graph**?* (v2 LEVEL_PREFIX hierarchy: each parent's `metric_level` strictly coarser than its child's) |
| `trugs_tools` CORE-16 (`tg validate`) | **TOOLS** | language/spec | *Is this valid **TRL/spec**?* (the canonical 16 structural rules over the TRUG envelope) |

STORE's validator runs at **storage time** (on load/save and via
`store.validate_graph()`) and knows nothing about TRL grammar. TOOLS' CORE-16
validator runs at **author/spec time** and is the single source of truth for
"valid TRL". Neither duplicates the other; collapsing them would couple the
persistence layer to the language layer — the opposite of this boundary.

<trl>
INTERFACE store_validation SHALL CHECK RECORD structural_hierarchy.
INTERFACE store_validation SHALL_NOT IMPLEMENT RECORD core16_validation.
</trl>

## What this boundary forbids

- STORE must not grow a TRL parser or the CORE-16 validator (those are TOOLS').
- TOOLS must not fork the graph model, the backends, or `schema.sql` (those are STORE's).
- No code moves across this boundary without a deliberate decision recorded here.

## Why STORE stays its own package

STORE earns its own package because it has **four independent consumers**
(TRUGS-TOOLS, noise-chatbot, TRUGS_COMPUTATION, and the TRUGS spec repo), each
importing `trugs_store` directly. A merge into TOOLS was considered and
rejected (it would create coupling, not remove duplication — TOOLS already
cleanly extends STORE's `BaseGraph`); a rename was considered and reversed (a
*store* is where TRUGs — graphs — are stored and found, which reads true, and a
rename would cost a PyPI deprecation plus a four-consumer import migration).
See AAA #2330 Phase 1–2 for the full decision record.
