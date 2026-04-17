"""JSON file persistence — load/save .trug.json files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from trugs_store.memory import InMemoryGraphStore

_METADATA_SKIP = {"nodes", "edges"}


class JsonFilePersistence:
    """Load and save .trug.json files to/from InMemoryGraphStore."""

    def load(self, source: str) -> InMemoryGraphStore:
        path = Path(source)
        with open(path, "r", encoding="utf-8") as fh:
            data: Dict[str, Any] = json.load(fh)
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

    def save(self, store: InMemoryGraphStore, destination: str) -> None:
        path = Path(destination)
        data: Dict[str, Any] = {}
        for key, value in store.get_metadata().items():
            data[key] = value
        data["nodes"] = list(store._nodes.values())
        data["edges"] = list(store._edges)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
