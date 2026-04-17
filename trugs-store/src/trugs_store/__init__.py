"""trugs-store — Graph storage backends for TRUGS specifications."""

from trugs_store.graph import BaseGraph
from trugs_store.memory import InMemoryGraphStore
from trugs_store.persistence.json_file import JsonFilePersistence
from trugs_store.persistence.dual_write import write_trug, read_trug, export_trug, import_trug
from trugs_store.protocol import GraphStore, PersistenceAdapter, Violation
from trugs_store.types import Edge, Node

__all__ = [
    "BaseGraph",
    "GraphStore",
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

# PostgreSQL support is optional — import only if psycopg3 is installed
try:
    from trugs_store.postgres import PostgresGraphStore
    from trugs_store.persistence.postgres import PostgresPersistence
    __all__.extend(["PostgresGraphStore", "PostgresPersistence"])
except ImportError:
    pass
