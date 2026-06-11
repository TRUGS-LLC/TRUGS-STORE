# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""JSON file persistence — load/save .trug.json files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from trugs_store.graph import BaseGraph
from trugs_store.memory import InMemoryGraphStore
from trugs_store.validation import validate_v2_hierarchy
from trugs_store.vocabulary import classify_vocabulary

_METADATA_SKIP = {"nodes", "edges"}


class JsonFilePersistence:
    """Load and save .trug.json files to/from InMemoryGraphStore.

    Recognizes the TRUG's declared vocabulary (`capabilities.vocabularies`)
    and dispatches load/save to the v1 or v2 path. v1 TRUGs round-trip
    byte-equivalent through load → save (additive guarantee per TRUGS-LLC
    Spec Evolution Addendum §1.2). v2-specific behavior — LEVEL_PREFIX
    validation, inheritance stamping, canonical re-emit — lands in
    AAA #1756 Sub-phase 5.2; in 5.1 the v2 dispatch path is a stub that
    behaves identically to v1.

    <trl>
    AGENT claude SHALL DEFINE RECORD JsonFilePersistence AS A RECORD persistence.
    </trl>
    """

    def load(self, source: str) -> InMemoryGraphStore:
        """<trl>
        PROCESS load SHALL READ RECORD file THEN DISPATCH 'on RECORD vocabulary THEN RETURN RECORD store.
        </trl>
        """
        path = Path(source)
        with open(path, "r", encoding="utf-8") as fh:
            data: Dict[str, Any] = json.load(fh)
        if classify_vocabulary(data) == "v2":
            return self._load_v2(data)
        return self._load_v1(data)

    def save(self, store: InMemoryGraphStore, destination: str) -> None:
        """<trl>
        PROCESS save SHALL WRITE RECORD store TO DATA file 'with DISPATCH 'on RECORD vocabulary.
        </trl>
        """
        if classify_vocabulary(store.get_metadata()) == "v2":
            self._save_v2(store, destination)
        else:
            self._save_v1(store, destination)

    # PROCESS _load_v1 SHALL READ DATA legacy_trug THEN RETURN RECORD store.
    def _load_v1(self, data: Dict[str, Any]) -> InMemoryGraphStore:
        store = InMemoryGraphStore()
        for key, value in data.items():
            if key not in _METADATA_SKIP:
                store.set_metadata(key, value)
        for node in data.get("nodes", []):
            store._nodes[node["id"]] = node
        for edge in data.get("edges", []):
            store._edges.append(edge)
        store._rebuild_edge_indexes()
        return store

    # PROCESS _load_v2 SHALL READ DATA hierarchy_first_trug THEN RETURN RECORD store.
    # Hydrates the store via the v1 path (data shape is unchanged) and
    # then invokes `validate_v2_hierarchy` per AAA #1756 Phase 3 §"LEVEL_PREFIX
    # validation (v2 only)". Violations surface through `store.validate_graph()`
    # (which now dispatches on declared vocabulary) — the load does not raise
    # on violations; consumers decide how to react.
    def _load_v2(self, data: Dict[str, Any]) -> InMemoryGraphStore:
        store = self._load_v1(data)
        validate_v2_hierarchy(store)
        return store

    # PROCESS _save_v1 SHALL WRITE RECORD store TO DATA file.
    def _save_v1(self, store: InMemoryGraphStore, destination: str) -> None:
        path = Path(destination)
        data: Dict[str, Any] = {}
        for key, value in store.get_metadata().items():
            data[key] = value
        data["nodes"] = list(store._nodes.values())
        data["edges"] = list(store._edges)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    # PROCESS _save_v2 SHALL WRITE RECORD store TO DATA file 'with canonical_reemit.
    # Canonical re-emit per AAA #1756 Phase 3 §"Canonical re-emit (v2 only)":
    #   1. Stamp inherited metric_level on any node missing it (ADR-002).
    #   2. Emit every node with metric_level explicit.
    #   3. Emit `level_directives` — an ordered list of metric_level values
    #      marking each transition in the node array (the JSON analogue of
    #      a TRL `level_directive` line per mem-9cab9a23 / trl_vocabulary.md).
    def _save_v2(self, store: InMemoryGraphStore, destination: str) -> None:
        BaseGraph._stamp_inherited_metric_levels(store)
        nodes = list(store._nodes.values())
        path = Path(destination)
        data: Dict[str, Any] = {}
        for key, value in store.get_metadata().items():
            if key == "level_directives":
                # Recomputed below — never trust the stored value.
                continue
            data[key] = value
        data["level_directives"] = self._compute_level_directives(nodes)
        data["nodes"] = nodes
        data["edges"] = list(store._edges)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    # PROCESS _compute_level_directives SHALL READ ALL RECORD node THEN RETURN RECORD directives.
    @staticmethod
    def _compute_level_directives(nodes: List[Dict[str, Any]]) -> List[str]:
        """Scan nodes in order; emit each metric_level value at each transition."""
        directives: List[str] = []
        prev: Any = None
        for node in nodes:
            level = node.get("metric_level")
            if level and level != prev:
                directives.append(str(level))
                prev = level
        return directives
