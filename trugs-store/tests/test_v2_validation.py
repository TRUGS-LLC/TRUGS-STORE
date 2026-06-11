# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for TRUGS 2.0 LEVEL_PREFIX hierarchy validation.

Covers Phase 3 §"LEVEL_PREFIX validation (v2 only)" ASSERTions from
TRUGS-DEVELOPMENT AAA #1756 Sub-phase 5.2:

- ASSERT v2 TRUG with valid_hierarchy SHALL PASS validate_graph with EMPTY violations
- ASSERT v2 TRUG where parent.metric_level DOES_NOT EXCEED child.metric_level
  SHALL PRODUCE Violation severity=ERROR
- ASSERT v1 TRUG SHALL SKIP LEVEL_PREFIX_validation
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


from trugs_store import JsonFilePersistence
from trugs_store.memory import InMemoryGraphStore
from trugs_store.validation import (
    SI_PREFIX_ORDERING,
    prefix_of,
    validate_v2_hierarchy,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _v2_trug_valid_hierarchy() -> Dict[str, Any]:
    """v2 TRUG: KILO (coarse) parent -> BASE (fine) child. Valid."""
    return {
        "name": "v2_valid",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "v2 TRUG with parent strictly coarser than child",
        "capabilities": {
            "profiles": [],
            "extensions": [],
            "vocabularies": ["core_v2.0.0"],
        },
        "dimensions": {"test_dim": {"description": "test", "base_level": "BASE"}},
        "nodes": [
            {
                "id": "root",
                "type": "FOLDER",
                "properties": {"name": "root"},
                "parent_id": None,
                "contains": ["child"],
                "metric_level": "KILO_FOLDER",
                "dimension": "test_dim",
            },
            {
                "id": "child",
                "type": "DOCUMENT",
                "properties": {"name": "child"},
                "parent_id": "root",
                "contains": [],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "test_dim",
            },
        ],
        "edges": [],
    }


def _v2_trug_inverted_hierarchy() -> Dict[str, Any]:
    """v2 TRUG: BASE (fine) parent -> KILO (coarse) child. Invalid — parent must be coarser."""
    trug = _v2_trug_valid_hierarchy()
    trug["name"] = "v2_inverted"
    trug["nodes"][0]["metric_level"] = "BASE_FOLDER"
    trug["nodes"][1]["metric_level"] = "KILO_DOCUMENT"
    return trug


def _v2_trug_equal_hierarchy() -> Dict[str, Any]:
    """v2 TRUG: KILO parent -> KILO child. Invalid — parent must STRICTLY exceed child."""
    trug = _v2_trug_valid_hierarchy()
    trug["name"] = "v2_equal"
    trug["nodes"][0]["metric_level"] = "KILO_FOLDER"
    trug["nodes"][1]["metric_level"] = "KILO_DOCUMENT"
    return trug


def _v1_trug_inverted_hierarchy() -> Dict[str, Any]:
    """v1 TRUG with same inversion as _v2_trug_inverted_hierarchy. Should SKIP v2 checks."""
    trug = _v2_trug_inverted_hierarchy()
    trug["capabilities"]["vocabularies"] = ["core_v1.0.0"]
    trug["name"] = "v1_inverted"
    return trug


def _load_into_store(trug: Dict[str, Any], tmp_path: Path) -> InMemoryGraphStore:
    p = tmp_path / f"{trug['name']}.trug.json"
    p.write_text(json.dumps(trug), encoding="utf-8")
    return JsonFilePersistence().load(str(p))


# ---------------------------------------------------------------------------
# SI_PREFIX_ORDERING — unit shape
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE RECORD SI_PREFIX_ORDERING CONTAINS RECORD count EQUALS 21.
def test_si_prefix_ordering_has_21_prefixes():
    """The TRUGS 2.0 vocabulary adds 21 SI prefixes (YOTTA..YOCTO)."""
    assert len(SI_PREFIX_ORDERING) == 21


# AGENT claude SHALL VALIDATE RECORD SI_PREFIX_ORDERING PLACES BASE 'between KILO AND DECI.
def test_si_prefix_ordering_base_position():
    """BASE sits between KILO (coarser) and DECI (finer)."""
    kilo = SI_PREFIX_ORDERING.index("KILO")
    base = SI_PREFIX_ORDERING.index("BASE")
    deci = SI_PREFIX_ORDERING.index("DECI")
    assert kilo < base < deci


# AGENT claude SHALL VALIDATE PROCESS prefix_of EXTRACTS RECORD level_prefix FROM RECORD metric_level.
def test_prefix_of_extracts_si_prefix():
    assert prefix_of("KILO_FOLDER") == "KILO"
    assert prefix_of("BASE_DOCUMENT") == "BASE"
    assert prefix_of("YOTTA_REPO") == "YOTTA"


# AGENT claude SHALL VALIDATE PROCESS prefix_of RETURNS None 'when RECORD prefix 'is UNKNOWN.
def test_prefix_of_returns_none_for_unknown():
    assert prefix_of(None) is None
    assert prefix_of("") is None
    assert prefix_of("WIBBLY_FOLDER") is None  # WIBBLY is not an SI prefix


# ---------------------------------------------------------------------------
# Phase 3 §LEVEL_PREFIX validation (v2 only) — the three ASSERTions
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE EACH RECORD "v2 TRUG" 'with valid_hierarchy PASSES validate_graph 'with EMPTY violations.
def test_v2_valid_hierarchy_passes_validate_graph(tmp_path: Path):
    """ASSERT #1: v2 TRUG with valid hierarchy → store.validate_graph() returns empty list."""
    store = _load_into_store(_v2_trug_valid_hierarchy(), tmp_path)
    violations = store.validate_graph()
    assert violations == [], (
        f"Expected no violations for valid v2 hierarchy, got: "
        f"{[(v.rule, v.node_id, v.message) for v in violations]}"
    )


# AGENT claude SHALL VALIDATE EACH RECORD "v2 TRUG" 'with parent NOT EXCEEDING child PRODUCES RECORD Violation.
def test_v2_inverted_hierarchy_produces_error_violation(tmp_path: Path):
    """ASSERT #2: parent finer than child → ERROR Violation."""
    store = _load_into_store(_v2_trug_inverted_hierarchy(), tmp_path)
    violations = store.validate_graph()
    level_prefix_violations = [
        v for v in violations if v.rule == "level_prefix_hierarchy"
    ]
    assert len(level_prefix_violations) == 1
    v = level_prefix_violations[0]
    assert v.node_id == "child"
    assert v.severity == "error"
    assert "parent must be strictly coarser than child" in v.message


# AGENT claude SHALL VALIDATE EACH RECORD "v2 TRUG" 'with parent EQUAL TO child PRODUCES RECORD Violation.
def test_v2_equal_levels_produce_error_violation(tmp_path: Path):
    """ASSERT #2 (boundary): parent at SAME level as child → ERROR Violation (strict exceedance)."""
    store = _load_into_store(_v2_trug_equal_hierarchy(), tmp_path)
    violations = store.validate_graph()
    level_prefix_violations = [
        v for v in violations if v.rule == "level_prefix_hierarchy"
    ]
    assert len(level_prefix_violations) == 1
    assert level_prefix_violations[0].severity == "error"


# AGENT claude SHALL VALIDATE EACH RECORD "v1 TRUG" SHALL SKIP PROCESS LEVEL_PREFIX_validation.
def test_v1_inverted_hierarchy_skips_level_prefix_validation(tmp_path: Path):
    """ASSERT #3: same data shape but declared v1 → NO level_prefix_hierarchy violations."""
    store = _load_into_store(_v1_trug_inverted_hierarchy(), tmp_path)
    violations = store.validate_graph()
    level_prefix_violations = [
        v for v in violations if v.rule == "level_prefix_hierarchy"
    ]
    assert level_prefix_violations == []


# AGENT claude SHALL VALIDATE PROCESS validate_v2_hierarchy IS CALLABLE DIRECTLY 'on RECORD store.
def test_validate_v2_hierarchy_callable_directly(tmp_path: Path):
    """The validator is also callable as a free function (per AAA Phase 3 INTERFACE)."""
    store = _load_into_store(_v2_trug_valid_hierarchy(), tmp_path)
    assert validate_v2_hierarchy(store) == []
    store2 = _load_into_store(_v2_trug_inverted_hierarchy(), tmp_path)
    direct = validate_v2_hierarchy(store2)
    assert len(direct) == 1
    assert direct[0].rule == "level_prefix_hierarchy"


# AGENT claude SHALL VALIDATE PROCESS validate_v2_hierarchy SKIPS RECORD node 'with UNKNOWN prefix.
def test_validate_v2_hierarchy_skips_unknown_prefixes(tmp_path: Path):
    """Nodes with non-SI prefixes (e.g. typos) are skipped — out of v2 scope."""
    trug = _v2_trug_valid_hierarchy()
    trug["nodes"][0]["metric_level"] = "WIBBLY_FOLDER"  # not an SI prefix
    store = _load_into_store(trug, tmp_path)
    violations = validate_v2_hierarchy(store)
    assert violations == []


# AGENT claude SHALL VALIDATE PROCESS validate_v2_hierarchy SKIPS RECORD node 'with MISSING metric_level.
def test_validate_v2_hierarchy_skips_missing_metric_level():
    """Nodes missing metric_level are caught by the existing missing_required_field rule."""
    store = InMemoryGraphStore()
    store.set_metadata("capabilities", {"vocabularies": ["core_v2.0.0"]})
    store.add_node(
        {
            "id": "root",
            "type": "FOLDER",
            "properties": {},
            "parent_id": None,
            "contains": ["child"],
            "metric_level": "KILO_FOLDER",
            "dimension": "d",
        }
    )
    store.add_node(
        {
            "id": "child",
            "type": "DOCUMENT",
            "properties": {},
            "parent_id": "root",
            "contains": [],
            # metric_level missing
            "dimension": "d",
        },
        parent_id="root",
    )
    violations = validate_v2_hierarchy(store)
    # validate_v2_hierarchy itself produces no violations for missing metric_level
    assert [v for v in violations if v.rule == "level_prefix_hierarchy"] == []
