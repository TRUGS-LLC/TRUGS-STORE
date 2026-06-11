# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Self-dogfood test — TRUGS-STORE-dev's own folder.trug.json is a valid v2 TRUG.

Covers Phase 3 §"Self-dogfood" ASSERTions from TRUGS-DEVELOPMENT AAA #1756
Sub-phase 5.3:

- ASSERT TRUGS-STORE-dev/folder.trug.json SHALL VALIDATE through validate_graph
  with EMPTY violations
- ASSERT TEST suite SHALL CONTAIN test 'that READS folder.trug.json AND ASSERTS
  validation_passes

The repo's folder.trug.json declares both `project_v1` (legacy project
semantic) and `core_v2.0.0` (Hierarchy First / LEVEL_PREFIX semantics).
Per `classify_vocabulary`, v2 wins for dispatch — so `validate_graph` runs
both the v1 generic checks AND the v2 LEVEL_PREFIX hierarchy invariants.
"""

from __future__ import annotations

import json
from pathlib import Path


from trugs_store import JsonFilePersistence
from trugs_store.vocabulary import classify_vocabulary

# Locate the repo-root folder.trug.json. tests/ -> trugs-store/ -> repo root.
_REPO_FOLDER_TRUG = Path(__file__).resolve().parents[2] / "folder.trug.json"


# AGENT claude SHALL VALIDATE FILE folder.trug.json EXISTS.
def test_repo_folder_trug_exists():
    """The self-dogfood target file is present at the repo root."""
    assert _REPO_FOLDER_TRUG.is_file(), (
        f"Expected self-dogfood TRUG at {_REPO_FOLDER_TRUG}; file missing"
    )


# AGENT claude SHALL VALIDATE FILE folder.trug.json DECLARES RECORD core_v2_0_0.
def test_repo_folder_trug_declares_core_v2():
    """Self-dogfood TRUG declares `core_v2.0.0` so v2 dispatch and validation engage."""
    data = json.loads(_REPO_FOLDER_TRUG.read_text(encoding="utf-8"))
    vocabs = data.get("capabilities", {}).get("vocabularies", [])
    assert "core_v2.0.0" in vocabs, (
        f"Expected core_v2.0.0 in vocabularies, got {vocabs}"
    )
    assert classify_vocabulary(data) == "v2"


# AGENT claude SHALL VALIDATE FILE folder.trug.json PASSES validate_graph WITH EMPTY violations.
def test_repo_folder_trug_self_validates():
    """Phase 3 §Self-dogfood: store.validate_graph() returns no violations."""
    store = JsonFilePersistence().load(str(_REPO_FOLDER_TRUG))
    violations = store.validate_graph()
    assert violations == [], (
        f"Self-dogfood TRUG should validate cleanly; got "
        f"{[(v.rule, v.node_id, v.message) for v in violations]}"
    )


# AGENT claude SHALL VALIDATE FILE folder.trug.json EMITS RECORD level_directives.
def test_repo_folder_trug_emits_level_directives():
    """v2 TRUG file ships canonical level_directives at the top level."""
    data = json.loads(_REPO_FOLDER_TRUG.read_text(encoding="utf-8"))
    assert "level_directives" in data, (
        "v2 self-dogfood TRUG must ship a `level_directives` field at top level"
    )
    directives = data["level_directives"]
    assert isinstance(directives, list) and len(directives) > 0
    # First directive must match the first node's metric_level.
    assert directives[0] == data["nodes"][0]["metric_level"]


# AGENT claude SHALL VALIDATE FILE folder.trug.json STAMPS RECORD metric_level 'on EACH node.
def test_repo_folder_trug_every_node_has_metric_level():
    """Phase 3 §"Canonical re-emit": every node carries metric_level explicitly."""
    data = json.loads(_REPO_FOLDER_TRUG.read_text(encoding="utf-8"))
    missing = [n["id"] for n in data["nodes"] if not n.get("metric_level")]
    assert missing == [], f"Nodes missing metric_level: {missing}"


# AGENT claude SHALL VALIDATE FILE folder.trug.json UNDERGOES BYTE_EQUIVALENT ROUND_TRIP.
def test_repo_folder_trug_round_trip_byte_equivalent(tmp_path: Path):
    """Round-tripping the self-dogfood TRUG through load+save is byte-equivalent.

    This is the strongest form of "canonical" — the on-disk form already
    matches what `_save_v2` would emit, so future renderers + auditors can
    rely on byte stability.
    """
    pers = JsonFilePersistence()
    store = pers.load(str(_REPO_FOLDER_TRUG))
    dst = tmp_path / "roundtrip.trug.json"
    pers.save(store, str(dst))
    assert _REPO_FOLDER_TRUG.read_bytes() == dst.read_bytes(), (
        "Self-dogfood TRUG drifted on round-trip — file is NOT in canonical "
        "v2 form. Re-render via `JsonFilePersistence().save(store, path)`."
    )
