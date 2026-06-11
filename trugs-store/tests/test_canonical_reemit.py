# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for TRUGS 2.0 canonical re-emit on save.

Covers Phase 3 §"Canonical re-emit (v2 only)" ASSERTions from
TRUGS-DEVELOPMENT AAA #1756 Sub-phase 5.2:

- ASSERT v2 TRUG through load -> stamp -> save SHALL EMIT output where
  EACH node CONTAINS metric_level EXPLICITLY
- ASSERT save 'on v2 TRUG SHALL EMIT level_directive at EACH metric_level_transition
- Regression: v1 TRUGs round-trip remains byte-equivalent (no canonical-reemit drift)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


from trugs_store import JsonFilePersistence
from trugs_store.graph import BaseGraph
from trugs_store.memory import InMemoryGraphStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _v2_three_level_trug() -> Dict[str, Any]:
    """v2 TRUG with three distinct metric_level transitions: KILO -> BASE -> DECI."""
    return {
        "name": "v2_three_level",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "v2 TRUG with three SI levels for canonical-reemit tests",
        "capabilities": {
            "profiles": [],
            "extensions": [],
            "vocabularies": ["core_v2.0.0"],
        },
        "dimensions": {"d": {"description": "test", "base_level": "BASE"}},
        "nodes": [
            {
                "id": "kilo_root",
                "type": "FOLDER",
                "properties": {},
                "parent_id": None,
                "contains": ["base_child"],
                "metric_level": "KILO_FOLDER",
                "dimension": "d",
            },
            {
                "id": "base_child",
                "type": "DOCUMENT",
                "properties": {},
                "parent_id": "kilo_root",
                "contains": ["deci_grand"],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "d",
            },
            {
                "id": "deci_grand",
                "type": "COMPONENT",
                "properties": {},
                "parent_id": "base_child",
                "contains": [],
                "metric_level": "DECI_COMPONENT",
                "dimension": "d",
            },
        ],
        "edges": [],
    }


def _v2_trug_with_missing_metric_level_on_leaf() -> Dict[str, Any]:
    """v2 TRUG where the leaf is missing metric_level — should be stamped on save."""
    trug = _v2_three_level_trug()
    trug["name"] = "v2_stamp_target"
    trug["nodes"][2].pop("metric_level")
    return trug


def _v1_trug_dict() -> Dict[str, Any]:
    """Minimal v1 TRUG — round-trip must remain byte-equivalent (no canonical re-emit)."""
    return {
        "name": "v1_baseline",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "v1 TRUG — byte-stable round-trip",
        "capabilities": {
            "profiles": [],
            "extensions": [],
            "vocabularies": ["core_v1.0.0"],
        },
        "dimensions": {"d": {"description": "test", "base_level": "BASE"}},
        "nodes": [
            {
                "id": "root",
                "type": "FOLDER",
                "properties": {},
                "parent_id": None,
                "contains": ["child"],
                "metric_level": "KILO_FOLDER",
                "dimension": "d",
            },
            {
                "id": "child",
                "type": "DOCUMENT",
                "properties": {},
                "parent_id": "root",
                "contains": [],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "d",
            },
        ],
        "edges": [
            {
                "from_id": "root",
                "to_id": "child",
                "relation": "CONTAINS",
                "weight": 1.0,
                "properties": {},
            },
        ],
    }


def _roundtrip(
    trug: Dict[str, Any], tmp_path: Path, suffix: str = ""
) -> Dict[str, Any]:
    """Write trug to disk, load, save back, return the re-loaded JSON."""
    src = tmp_path / f"src{suffix}.trug.json"
    dst = tmp_path / f"dst{suffix}.trug.json"
    src.write_text(json.dumps(trug), encoding="utf-8")
    pers = JsonFilePersistence()
    store = pers.load(str(src))
    pers.save(store, str(dst))
    return json.loads(dst.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Phase 3 ASSERT — metric_level explicit on every node after save
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE EACH RECORD "v2 TRUG" 'through INTERFACE save EMITS RECORD metric_level EXPLICITLY.
def test_v2_save_emits_metric_level_on_every_node(tmp_path: Path):
    """ASSERT: v2 TRUG load -> stamp -> save -> every node has metric_level explicit."""
    output = _roundtrip(_v2_three_level_trug(), tmp_path)
    for node in output["nodes"]:
        assert "metric_level" in node, (
            f"Node {node['id']!r} missing metric_level after v2 save"
        )
        assert node["metric_level"], f"Node {node['id']!r} has falsy metric_level"


# AGENT claude SHALL VALIDATE INTERFACE save STAMPS RECORD metric_level 'on RECORD missing_node.
def test_v2_save_stamps_inherited_metric_level(tmp_path: Path):
    """A node missing metric_level on input has it stamped (inherited one step finer) on output."""
    output = _roundtrip(_v2_trug_with_missing_metric_level_on_leaf(), tmp_path)
    leaf = [n for n in output["nodes"] if n["id"] == "deci_grand"][0]
    assert leaf.get("metric_level"), (
        "Leaf node should be stamped with inherited metric_level"
    )
    # Parent BASE_DOCUMENT -> child stamped DECI_<TYPE>. type is "COMPONENT".
    assert leaf["metric_level"] == "DECI_COMPONENT"


# ---------------------------------------------------------------------------
# Phase 3 ASSERT — level_directives at each transition
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE INTERFACE save EMITS RECORD level_directive 'at EACH metric_level_transition.
def test_v2_save_emits_level_directives_at_each_transition(tmp_path: Path):
    """ASSERT: v2 save emits a level_directive at each metric_level transition."""
    output = _roundtrip(_v2_three_level_trug(), tmp_path)
    assert "level_directives" in output, "v2 save must emit `level_directives` field"
    # The fixture has nodes in canonical (coarse->fine) order:
    # KILO_FOLDER, BASE_DOCUMENT, DECI_COMPONENT -> 3 transitions, one per level.
    assert output["level_directives"] == [
        "KILO_FOLDER",
        "BASE_DOCUMENT",
        "DECI_COMPONENT",
    ]


# AGENT claude SHALL VALIDATE INTERFACE save EMITS RECORD level_directive WHEN RECORD level REPEATS.
def test_v2_save_level_directives_repeat_on_each_transition(tmp_path: Path):
    """If level_A -> level_B -> level_A, three directives are emitted (each transition counts)."""
    trug = _v2_three_level_trug()
    trug["name"] = "v2_zigzag"
    # Re-arrange: KILO, BASE, KILO (zigzag) — still legal as a list; v2 hierarchy
    # validation walks parent_id, not array order. The directive emission tracks
    # the as-saved sequence.
    trug["nodes"] = [
        {
            "id": "n1",
            "type": "FOLDER",
            "properties": {},
            "parent_id": None,
            "contains": [],
            "metric_level": "KILO_FOLDER",
            "dimension": "d",
        },
        {
            "id": "n2",
            "type": "FOLDER",
            "properties": {},
            "parent_id": None,
            "contains": [],
            "metric_level": "BASE_FOLDER",
            "dimension": "d",
        },
        {
            "id": "n3",
            "type": "FOLDER",
            "properties": {},
            "parent_id": None,
            "contains": [],
            "metric_level": "KILO_FOLDER",
            "dimension": "d",
        },
    ]
    output = _roundtrip(trug, tmp_path)
    assert output["level_directives"] == ["KILO_FOLDER", "BASE_FOLDER", "KILO_FOLDER"]


# AGENT claude SHALL VALIDATE INTERFACE save NEVER trusts STORED level_directives.
def test_v2_save_recomputes_level_directives_from_stored(tmp_path: Path):
    """`level_directives` from disk are ignored — re-derived from the current nodes."""
    trug = _v2_three_level_trug()
    trug["level_directives"] = ["GARBAGE_VALUE"]  # should be replaced
    output = _roundtrip(trug, tmp_path)
    assert "GARBAGE_VALUE" not in output["level_directives"]
    assert output["level_directives"] == [
        "KILO_FOLDER",
        "BASE_DOCUMENT",
        "DECI_COMPONENT",
    ]


# AGENT claude SHALL VALIDATE INTERFACE save EMITS empty RECORD level_directives 'when nodes EMPTY.
def test_v2_save_empty_nodes_emits_empty_level_directives(tmp_path: Path):
    """Edge case: v2 TRUG with zero nodes -> level_directives = []."""
    trug = _v2_three_level_trug()
    trug["nodes"] = []
    output = _roundtrip(trug, tmp_path)
    assert output["level_directives"] == []


# ---------------------------------------------------------------------------
# Regression — v1 round-trip unchanged (no canonical-reemit drift)
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE EACH RECORD "v1 TRUG" SHALL_NOT EMIT RECORD level_directives.
def test_v1_save_does_not_emit_level_directives(tmp_path: Path):
    """Regression: v1 round-trip must NOT add level_directives (byte-equivalence invariant)."""
    output = _roundtrip(_v1_trug_dict(), tmp_path)
    assert "level_directives" not in output


# AGENT claude SHALL VALIDATE EACH RECORD "v1 TRUG" SHALL UNDERGO ROUND_TRIP BYTE_EQUIVALENT.
def test_v1_round_trip_byte_equivalent(tmp_path: Path):
    """v1 TRUG byte-equivalent through load -> save (Phase 3 vocabulary-dispatch ASSERT)."""
    trug = _v1_trug_dict()
    src = tmp_path / "src.trug.json"
    dst = tmp_path / "dst.trug.json"
    src.write_text(
        json.dumps(trug, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    pers = JsonFilePersistence()
    pers.save(pers.load(str(src)), str(dst))
    assert src.read_bytes() == dst.read_bytes()


# ---------------------------------------------------------------------------
# Idempotence — v2 round-trip stable after first save
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE EACH RECORD "v2 TRUG" SHALL UNDERGO IDEMPOTENT ROUND_TRIP 'after FIRST save.
def test_v2_second_round_trip_idempotent(tmp_path: Path):
    """After the first save canonicalizes the TRUG, subsequent round-trips are byte-equivalent."""
    trug = _v2_three_level_trug()
    src = tmp_path / "src.trug.json"
    src.write_text(json.dumps(trug), encoding="utf-8")
    pers = JsonFilePersistence()
    # First save: canonicalize.
    dst1 = tmp_path / "dst1.trug.json"
    pers.save(pers.load(str(src)), str(dst1))
    # Second save: should reproduce dst1 exactly.
    dst2 = tmp_path / "dst2.trug.json"
    pers.save(pers.load(str(dst1)), str(dst2))
    assert dst1.read_bytes() == dst2.read_bytes()


# ---------------------------------------------------------------------------
# Stamp helper — direct unit coverage
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE INTERFACE BaseGraph._stamp_inherited_metric_levels STAMPS RECORD missing.
def test_stamp_inherited_metric_levels_handles_chain():
    """Multi-level chain converges in a single fixpoint loop."""
    store = InMemoryGraphStore()
    store.add_node(
        {
            "id": "root",
            "type": "REPO",
            "properties": {},
            "parent_id": None,
            "contains": ["mid"],
            "metric_level": "KILO_REPO",
            "dimension": "d",
        }
    )
    store.add_node(
        {
            "id": "mid",
            "type": "FOLDER",
            "properties": {},
            "parent_id": "root",
            "contains": ["leaf"],
            # missing metric_level
            "dimension": "d",
        },
        parent_id="root",
    )
    store.add_node(
        {
            "id": "leaf",
            "type": "DOCUMENT",
            "properties": {},
            "parent_id": "mid",
            "contains": [],
            # missing metric_level — depends on mid being stamped first
            "dimension": "d",
        },
        parent_id="mid",
    )
    BaseGraph._stamp_inherited_metric_levels(store)
    assert store._nodes["mid"]["metric_level"] == "HECTO_FOLDER"
    # one step finer than HECTO is DEKA (the canonical 10^1 prefix; AAA #2330 SP4)
    assert store._nodes["leaf"]["metric_level"] == "DEKA_DOCUMENT"


# AGENT claude SHALL VALIDATE INTERFACE BaseGraph._stamp_inherited_metric_levels SHALL_NOT OVERWRITE.
def test_stamp_inherited_metric_levels_does_not_overwrite_existing():
    """Existing metric_level values are preserved — stamping is fill-only."""
    store = InMemoryGraphStore()
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
            "metric_level": "MILLI_DOCUMENT",  # intentionally several levels finer
            "dimension": "d",
        },
        parent_id="root",
    )
    BaseGraph._stamp_inherited_metric_levels(store)
    assert store._nodes["child"]["metric_level"] == "MILLI_DOCUMENT"


# AGENT claude SHALL VALIDATE INTERFACE BaseGraph._stamp_inherited_metric_levels SKIPS RECORD root WHEN MISSING.
def test_stamp_inherited_metric_levels_skips_root_without_metric_level():
    """A root node missing metric_level can't be stamped — leave it; validate_graph reports it."""
    store = InMemoryGraphStore()
    store.add_node(
        {
            "id": "root",
            "type": "FOLDER",
            "properties": {},
            "parent_id": None,
            "contains": [],
            # missing metric_level
            "dimension": "d",
        }
    )
    BaseGraph._stamp_inherited_metric_levels(store)
    # No-op — missing metric_level untouched.
    assert "metric_level" not in store._nodes["root"]
