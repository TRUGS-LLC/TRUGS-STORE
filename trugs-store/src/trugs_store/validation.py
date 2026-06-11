# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""LEVEL_PREFIX hierarchy invariant rules for v2 TRUGs.

Per TRUGS-DEVELOPMENT AAA #1756 Sub-phase 5.2 — Phase 3 §"LEVEL_PREFIX
validation (v2 only)" ASSERTions. Invoked from
`InMemoryGraphStore.validate_graph` when the TRUG declares `core_v2.0.0`,
and directly from `JsonFilePersistence._load_v2` / `PostgresPersistence._load_v2`.

The single load-bearing invariant: in `SI_PREFIX_ORDERING`, each
`parent_node.metric_level` must EXCEED `child_node.metric_level`
(parent strictly coarser than child). Violations are emitted as
`Violation(rule="level_prefix_hierarchy", severity="error")`.

Scope contract — this module is STORE's *structural* validator (is a stored
graph well-formed: LEVEL_PREFIX hierarchy?). It is deliberately distinct from
the CORE-16 TRL/spec validator (`tg validate`), which lives in TRUGS-TOOLS and
answers a different question (is this valid TRL?). The two-validator split is
intentional, not the #2189 drift; see BOUNDARY.md (authored in SP3).

<trl>
INTERFACE store_validation SHALL CHECK RECORD structural_hierarchy ACROSS ALL v2_node.
INTERFACE store_validation SHALL_NOT IMPLEMENT RECORD core16_validation.
</trl>
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from trugs_store.protocol import Violation

if TYPE_CHECKING:
    from trugs_store.memory import InMemoryGraphStore


# AGENT claude SHALL DEFINE RECORD SI_PREFIX_ORDERING AS A RECORD constant.
# Per AAA #1756 Phase 3 §Domain comparators: total ordering over the 21
# SI prefixes; YOTTA is coarsest, YOCTO finest. EXCEEDS in SI_PREFIX_ORDERING
# means "earlier in this tuple" (lower index).
#
# The 10^1 prefix is spelled "DEKA" (NOT "DECA") — the canonical TRUGS v2
# lexicon spelling, matching the CORE-16 validator (`tg validate`) and the
# folder-governance check. Using "DECA" here is a silent-correctness bug:
# `prefix_of("DEKA_…")` would return None and the hierarchy check would skip
# canonically-spelled nodes. (AAA #2330 SP4 — HITM-confirmed 2026-06-08.)
SI_PREFIX_ORDERING: tuple[str, ...] = (
    "YOTTA",
    "ZETTA",
    "EXA",
    "PETA",
    "TERA",
    "GIGA",
    "MEGA",
    "KILO",
    "HECTO",
    "DEKA",
    "BASE",
    "DECI",
    "CENTI",
    "MILLI",
    "MICRO",
    "NANO",
    "PICO",
    "FEMTO",
    "ATTO",
    "ZEPTO",
    "YOCTO",
)

_PREFIX_INDEX: dict[str, int] = {p: i for i, p in enumerate(SI_PREFIX_ORDERING)}


def prefix_of(metric_level: Optional[str]) -> Optional[str]:
    """Extract the LEVEL_PREFIX from a metric_level token.

    `metric_level` is conventionally `<PREFIX>_<NAME>` (e.g.
    `KILO_FOLDER`, `BASE_DOCUMENT`). Returns the prefix if it is one of
    the 21 SI prefixes, else None.

    <trl>
    AGENT claude SHALL DEFINE FUNCTION prefix_of AS A RECORD pure_function. PROCESS prefix_of SHALL READ RECORD metric_level THEN RETURN RECORD prefix.
    </trl>
    """
    if not metric_level:
        return None
    head = metric_level.split("_", 1)[0]
    return head if head in _PREFIX_INDEX else None


def validate_v2_hierarchy(store: "InMemoryGraphStore") -> List[Violation]:
    """LEVEL_PREFIX hierarchy invariants for v2 TRUGs.

    Returns a `Violation(severity="error")` for every parent->child edge
    where the parent's metric_level prefix does not strictly EXCEED the
    child's in `SI_PREFIX_ORDERING`. Nodes whose metric_level is missing
    or whose prefix is not in the SI ordering are skipped here — the
    former is caught by the existing `missing_required_field` rule in
    `validate_graph`; the latter is out-of-scope for v2 (only canonical
    SI-prefix metric_levels are validated).

    <trl>
    AGENT claude SHALL DEFINE FUNCTION validate_v2_hierarchy AS A RECORD validator. PROCESS validate_v2_hierarchy SHALL READ RECORD store THEN RETURN ALL RECORD violation.
    </trl>
    """
    violations: List[Violation] = []
    for node_id, node in store._nodes.items():
        parent_id = node.get("parent_id")
        if not parent_id:
            continue
        parent = store._nodes.get(parent_id)
        if parent is None:
            # caught by hierarchy_orphan in InMemoryGraphStore.validate_graph
            continue
        child_prefix = prefix_of(node.get("metric_level"))
        parent_prefix = prefix_of(parent.get("metric_level"))
        if child_prefix is None or parent_prefix is None:
            continue
        # parent EXCEEDS child in SI_PREFIX_ORDERING iff parent_index < child_index
        if _PREFIX_INDEX[parent_prefix] >= _PREFIX_INDEX[child_prefix]:
            violations.append(
                Violation(
                    node_id,
                    "level_prefix_hierarchy",
                    f"Node {node_id!r} (metric_level={node.get('metric_level')!r}, "
                    f"prefix={child_prefix}) is at or above the level of parent "
                    f"{parent_id!r} (prefix={parent_prefix}) in SI_PREFIX_ORDERING — "
                    f"parent must be strictly coarser than child",
                    severity="error",
                )
            )
    return violations
