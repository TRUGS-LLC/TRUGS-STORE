# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""trugs-store — Graph storage backends for TRUGS specifications."""

from trugs_store._optional import OptionalDependencyError
from trugs_store.graph import BaseGraph
from trugs_store.memory import InMemoryGraphStore
from trugs_store.persistence.json_file import JsonFilePersistence
from trugs_store.persistence.dual_write import (
    write_trug,
    read_trug,
    export_trug,
    import_trug,
)
from trugs_store.protocol import GraphStore, PersistenceAdapter, Violation
from trugs_store.types import Edge, Node

__all__ = [
    "BaseGraph",
    "GraphStore",
    "OptionalDependencyError",
    "PersistenceAdapter",
    "Violation",
    "Node",
    "Edge",
    "InMemoryGraphStore",
    "JsonFilePersistence",
    "write_trug",
    "read_trug",
    "export_trug",
    "import_trug",
]

# PostgreSQL support is optional — import only if psycopg3 is installed.
# Catch ONLY the named absent-dependency sentinel (raised by the psycopg
# guards in postgres.py / persistence/postgres.py). Any other ImportError is
# a genuine break inside the postgres modules and must propagate — the old
# bare `except ImportError: pass` silently dropped the backend even with
# psycopg installed (audit #2).
try:
    from trugs_store.postgres import PostgresGraphStore  # noqa: F401  (optional re-export)
    from trugs_store.persistence.postgres import PostgresPersistence  # noqa: F401  (optional re-export)

    __all__.extend(["PostgresGraphStore", "PostgresPersistence"])
except OptionalDependencyError:
    pass
