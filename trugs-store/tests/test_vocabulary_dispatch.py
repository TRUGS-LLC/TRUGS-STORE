# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Tests for TRUGS 2.0 vocabulary recognition + dispatch scaffold.

Covers Phase 3 §"Vocabulary dispatch" ASSERTions from
TRUGS-DEVELOPMENT AAA #1756 Sub-phase 5.1:

- ASSERT JsonFilePersistence.load SHALL RECOGNIZE core_v2.0.0
- ASSERT JsonFilePersistence.load SHALL RECOGNIZE core_v1.0.0
- ASSERT JsonFilePersistence.load SHALL RECOGNIZE project_v1
- ASSERT EACH "v1 TRUG" SHALL UNDERGO ROUND_TRIP byte-equivalent

Sub-phase 5.1 v2 path is a stub (passes through to v1). v2-specific
behavior (LEVEL_PREFIX validation, canonical re-emit) lands in 5.2.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trugs_store import JsonFilePersistence
from trugs_store.vocabulary import classify_vocabulary


# ---------------------------------------------------------------------------
# classify_vocabulary — pure-function unit tests
# ---------------------------------------------------------------------------


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary RECOGNIZES core_v1_0_0.
def test_classify_vocabulary_recognizes_core_v1_0_0():
    metadata = {"capabilities": {"vocabularies": ["core_v1.0.0"]}}
    assert classify_vocabulary(metadata) == "v1"


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary RECOGNIZES core_v2_0_0.
def test_classify_vocabulary_recognizes_core_v2_0_0():
    metadata = {"capabilities": {"vocabularies": ["core_v2.0.0"]}}
    assert classify_vocabulary(metadata) == "v2"


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary RECOGNIZES project_v1.
def test_classify_vocabulary_recognizes_project_v1():
    metadata = {"capabilities": {"vocabularies": ["project_v1"]}}
    assert classify_vocabulary(metadata) == "v1"


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary DEFAULTS_TO v1 'when RECORD vocabularies 'is MISSING.
def test_classify_vocabulary_defaults_to_v1_when_missing():
    """No capabilities field at all — additive guarantee, default v1."""
    assert classify_vocabulary({}) == "v1"


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary DEFAULTS_TO v1 'when RECORD vocabularies 'is EMPTY.
def test_classify_vocabulary_defaults_to_v1_when_empty():
    """capabilities.vocabularies is an empty list — default v1."""
    assert classify_vocabulary({"capabilities": {"vocabularies": []}}) == "v1"


# AGENT claude SHALL VALIDATE PROCESS classify_vocabulary RETURNS v2 'when ANY vocabularies CONTAINS core_v2_0_0.
def test_classify_vocabulary_v2_wins_when_mixed():
    """A TRUG can declare both v1 and v2 vocabularies; v2 dispatch wins."""
    metadata = {"capabilities": {"vocabularies": ["core_v1.0.0", "core_v2.0.0"]}}
    assert classify_vocabulary(metadata) == "v2"


# ---------------------------------------------------------------------------
# JsonFilePersistence — dispatch integration + v1 round-trip byte-equivalence
# ---------------------------------------------------------------------------


def _v1_trug_dict() -> dict:
    """Minimal v1 TRUG: declares core_v1.0.0 + has nodes + edges."""
    return {
        "name": "test_v1",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "v1 TRUG fixture for dispatch tests",
        "capabilities": {
            "profiles": [],
            "extensions": [],
            "vocabularies": ["core_v1.0.0"],
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
        "edges": [
            {
                "from_id": "root",
                "to_id": "child",
                "relation": "CONTAINS",
                "weight": 1.0,
                "properties": {},
            }
        ],
    }


def _v2_trug_dict() -> dict:
    """Minimal v2 TRUG: declares core_v2.0.0 (otherwise structurally identical)."""
    trug = _v1_trug_dict()
    trug["capabilities"]["vocabularies"] = ["core_v2.0.0"]
    trug["name"] = "test_v2"
    trug["description"] = "v2 TRUG fixture for dispatch tests"
    return trug


def _project_v1_trug_dict() -> dict:
    """Minimal TRUG declaring legacy `project_v1` vocabulary."""
    trug = _v1_trug_dict()
    trug["capabilities"]["vocabularies"] = ["project_v1"]
    trug["name"] = "test_project_v1"
    return trug


# AGENT claude SHALL VALIDATE INTERFACE JsonFilePersistence.load DISPATCHES 'on RECORD vocabulary FOR core_v1_0_0.
def test_load_dispatches_v1_for_core_v1_0_0(tmp_path: Path):
    p = tmp_path / "v1.trug.json"
    p.write_text(json.dumps(_v1_trug_dict()), encoding="utf-8")
    store = JsonFilePersistence().load(str(p))
    assert store.node_count() == 2


# AGENT claude SHALL VALIDATE INTERFACE JsonFilePersistence.load DISPATCHES 'on RECORD vocabulary FOR core_v2_0_0.
def test_load_dispatches_v2_for_core_v2_0_0(tmp_path: Path):
    """In Sub-phase 5.1, v2 dispatch is a stub passing through to v1.
    Behavior should be byte-equivalent to v1 path."""
    p = tmp_path / "v2.trug.json"
    p.write_text(json.dumps(_v2_trug_dict()), encoding="utf-8")
    store = JsonFilePersistence().load(str(p))
    assert store.node_count() == 2


# AGENT claude SHALL VALIDATE INTERFACE JsonFilePersistence.load DISPATCHES 'on RECORD vocabulary FOR project_v1.
def test_load_dispatches_v1_for_project_v1(tmp_path: Path):
    p = tmp_path / "project_v1.trug.json"
    p.write_text(json.dumps(_project_v1_trug_dict()), encoding="utf-8")
    store = JsonFilePersistence().load(str(p))
    assert store.node_count() == 2


# AGENT claude SHALL VALIDATE EACH "v1 TRUG" SHALL UNDERGO ROUND_TRIP BYTE_EQUIVALENT.
@pytest.mark.parametrize(
    "vocab_label,trug_factory",
    [
        ("core_v1.0.0", _v1_trug_dict),
        ("project_v1", _project_v1_trug_dict),
    ],
)
def test_v1_trug_round_trips_byte_equivalent(tmp_path: Path, vocab_label, trug_factory):
    """A v1 TRUG written then re-read then re-written produces byte-identical
    output to a clean re-write — no drift introduced by the dispatch wiring."""
    src = tmp_path / "src.trug.json"
    src.write_text(
        json.dumps(trug_factory(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    persistence = JsonFilePersistence()
    store = persistence.load(str(src))

    # Round-trip: save → reload → save again, verify two saves produce same bytes
    rt1 = tmp_path / "rt1.trug.json"
    persistence.save(store, str(rt1))

    store2 = persistence.load(str(rt1))
    rt2 = tmp_path / "rt2.trug.json"
    persistence.save(store2, str(rt2))

    assert rt1.read_bytes() == rt2.read_bytes(), (
        f"Round-trip not byte-equivalent for {vocab_label}: "
        "JsonFilePersistence load → save introduced drift on the v1 path."
    )


# AGENT claude SHALL VALIDATE EACH "v2 TRUG" SHALL UNDERGO ROUND_TRIP BYTE_EQUIVALENT 'in 5.1_stub_mode.
def test_v2_trug_round_trips_byte_equivalent_in_stub_mode(tmp_path: Path):
    """In Sub-phase 5.1, v2 path is a stub — round-trip should also be stable.
    (v2-specific re-emit lands in 5.2; this test guards against drift in 5.1.)"""
    src = tmp_path / "src.trug.json"
    src.write_text(
        json.dumps(_v2_trug_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    persistence = JsonFilePersistence()
    store = persistence.load(str(src))

    rt1 = tmp_path / "rt1.trug.json"
    persistence.save(store, str(rt1))

    store2 = persistence.load(str(rt1))
    rt2 = tmp_path / "rt2.trug.json"
    persistence.save(store2, str(rt2))

    assert rt1.read_bytes() == rt2.read_bytes(), (
        "v2 stub round-trip drift in Sub-phase 5.1 — dispatch is supposed to "
        "be a passthrough; any drift means the stub introduced behavior."
    )
