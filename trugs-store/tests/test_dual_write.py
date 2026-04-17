"""Tests for dual I/O persistence — JSON + optional PostgreSQL."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from trugs_store.persistence.dual_write import write_trug, read_trug, export_trug, import_trug


# AGENT claude SHALL DEFINE RECORD sample_trug AS A RECORD fixture.
@pytest.fixture
def sample_trug():
    """A minimal valid TRUG dict."""
    return {
        "name": "Test Folder",
        "version": "1.0.0",
        "type": "PROJECT",
        "description": "test",
        "nodes": [
            {
                "id": "root",
                "type": "FOLDER",
                "parent_id": None,
                "properties": {"name": "test"},
                "contains": ["child1"],
                "metric_level": "KILO_FOLDER",
                "dimension": "folder_structure",
            },
            {
                "id": "child1",
                "type": "DOCUMENT",
                "parent_id": "root",
                "properties": {"name": "README.md"},
                "contains": [],
                "metric_level": "BASE_DOCUMENT",
                "dimension": "folder_structure",
            },
        ],
        "edges": [
            {
                "from_id": "root",
                "to_id": "child1",
                "relation": "contains",
                "weight": 1.0,
                "properties": {},
            },
        ],
    }


class TestWriteTrugJsonOnly:
    """Tests for JSON write path (no DB)."""

    # PROCESS write_trug SHALL WRITE VALID RECORD json TO DATA file.
    def test_writes_valid_json(self, tmp_path, sample_trug):
        out = tmp_path / "TEST_FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        assert out.exists()
        content = out.read_text()
        assert content.endswith("\n")
        loaded = json.loads(content)
        assert loaded["name"] == "Test Folder"
        assert len(loaded["nodes"]) == 2
        assert len(loaded["edges"]) == 1

    # PROCESS write_trug SHALL WRITE RECORD json WITH indent=2 AND trailing newline.
    def test_json_matches_original_format(self, tmp_path, sample_trug):
        """Output must match json.dump(indent=2) + trailing newline."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        expected = json.dumps(sample_trug, indent=2, ensure_ascii=False) + "\n"
        assert out.read_text() == expected

    # PROCESS write_trug SHALL_NOT WRITE warning WHEN DATA dsn SHALL_NOT EXISTS.
    def test_no_dsn_no_warning(self, tmp_path, sample_trug, capsys):
        """When PORT_DSN is unset, no warning should be printed."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        with patch.dict(os.environ, {}, clear=True):
            # Ensure PORT_DSN is not set
            os.environ.pop("PORT_DSN", None)
            write_trug(sample_trug, out)

        captured = capsys.readouterr()
        assert "dual-write" not in captured.err

    # PROCESS write_trug SHALL ACCEPT DATA path AS STRING.
    def test_string_path(self, tmp_path, sample_trug):
        """Path can be a string."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, str(out))
        assert out.exists()


class TestWriteTrugWithPostgres:
    """Tests for dual-write with real PostgreSQL."""

    # AGENT claude SHALL DEFINE RECORD dsn AS A RECORD fixture.
    @pytest.fixture
    def dsn(self):
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set — skipping PostgreSQL tests")
        return dsn

    # PROCESS write_trug SHALL WRITE RECORD trug TO DATA file AND DATA database.
    def test_dual_write_populates_db(self, tmp_path, sample_trug, dsn):
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence

        out = tmp_path / "TEST_FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)

        # Verify JSON written
        assert out.exists()

        # Verify DB populated
        conn = psycopg.connect(dsn)
        try:
            pg = PostgresPersistence(conn)
            graphs = pg.list_graphs()
            graph_ids = [g["graph_id"] for g in graphs]
            assert "TEST_FOLDER" in graph_ids

            # Verify node/edge counts match
            store = pg.load("TEST_FOLDER")
            assert store.node_count() == 2
            assert store.edge_count() == 1

            # Cleanup
            pg.delete_graph("TEST_FOLDER")
            conn.commit()
        finally:
            conn.close()

    # PROCESS write_trug SHALL DERIVE DATA graph_id FROM RECORD parent folder name.
    def test_graph_id_from_parent_folder(self, tmp_path, sample_trug, dsn):
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence

        out = tmp_path / "MY_PROJECT" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)

        conn = psycopg.connect(dsn)
        try:
            pg = PostgresPersistence(conn)
            graphs = pg.list_graphs()
            graph_ids = [g["graph_id"] for g in graphs]
            assert "MY_PROJECT" in graph_ids

            pg.delete_graph("MY_PROJECT")
            conn.commit()
        finally:
            conn.close()

    # PROCESS write_trug SHALL REPLACE RECORD graph IN DATA database ON second WRITE.
    def test_overwrite_replaces_graph(self, tmp_path, sample_trug, dsn):
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence

        out = tmp_path / "REPLACE_TEST" / "folder.trug.json"
        out.parent.mkdir()

        # First write
        write_trug(sample_trug, out, db_dsn=dsn)

        # Second write with different data
        sample_trug["nodes"].append({
            "id": "child2",
            "type": "DOCUMENT",
            "parent_id": "root",
            "properties": {"name": "SPEC.md"},
            "contains": [],
            "metric_level": "BASE_DOCUMENT",
            "dimension": "folder_structure",
        })
        write_trug(sample_trug, out, db_dsn=dsn)

        conn = psycopg.connect(dsn)
        try:
            pg = PostgresPersistence(conn)
            store = pg.load("REPLACE_TEST")
            assert store.node_count() == 3  # replaced, not appended

            pg.delete_graph("REPLACE_TEST")
            conn.commit()
        finally:
            conn.close()


class TestWriteTrugResilience:
    """Tests for error resilience."""

    # PROCESS write_trug SHALL WRITE RECORD json THEN LOG warning WHEN DATA database FAILS.
    def test_bad_dsn_logs_warning_json_still_written(self, tmp_path, sample_trug, caplog):
        import logging
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        with caplog.at_level(logging.WARNING):
            write_trug(sample_trug, out, db_dsn="host=localhost port=99999 dbname=nonexistent")

        # JSON should still be written
        assert out.exists()
        loaded = json.loads(out.read_text())
        assert loaded["name"] == "Test Folder"

        # Warning should be logged via logging (not print)
        assert any("dual-write" in r.message.lower() or "DB write failed" in r.message for r in caplog.records)

    # PROCESS write_trug SHALL READ DATA PORT_DSN FROM environment WHEN DATA dsn EQUALS NONE.
    def test_env_var_dsn(self, tmp_path, sample_trug):
        """PORT_DSN env var is read when db_dsn kwarg is None."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()

        with patch.dict(os.environ, {"PORT_DSN": "host=localhost port=99999 dbname=nonexistent"}):
            write_trug(sample_trug, out)

        # JSON still written despite bad DSN
        assert out.exists()


class TestReadTrugJsonOnly:
    """Tests for JSON-only read path (no DB)."""

    # PROCESS read_trug SHALL READ RECORD trug FROM DATA json file.
    def test_reads_from_json(self, tmp_path, sample_trug):
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        result = read_trug(out)
        assert result["name"] == "Test Folder"
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    # PROCESS read_trug SHALL READ FROM DATA json WHEN DATA dsn SHALL_NOT EXISTS.
    def test_no_dsn_reads_json(self, tmp_path, sample_trug, capsys):
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PORT_DSN", None)
            result = read_trug(out)

        assert result["name"] == "Test Folder"
        captured = capsys.readouterr()
        assert "PORT read" not in captured.err

    # PROCESS read_trug SHALL REJECT WHEN DATA file SHALL_NOT EXISTS.
    def test_file_not_found_raises(self, tmp_path):
        missing = tmp_path / "FOLDER" / "folder.trug.json"
        with pytest.raises(FileNotFoundError):
            read_trug(missing)


class TestReadTrugWithPostgres:
    """Tests for reading from PostgreSQL."""

    # AGENT claude SHALL DEFINE RECORD dsn AS A RECORD fixture.
    @pytest.fixture
    def dsn(self):
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set — skipping PostgreSQL tests")
        return dsn

    # PROCESS read_trug SHALL READ RECORD trug FROM DATA database WHEN DATA dsn EXISTS.
    def test_read_from_db(self, tmp_path, sample_trug, dsn):
        """Write to DB, then read back — result matches original."""
        out = tmp_path / "READ_TEST" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)

        result = read_trug(out, db_dsn=dsn)
        assert result["name"] == "Test Folder"
        assert result["version"] == "1.0.0"
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

        # Verify node content
        node_ids = {n["id"] for n in result["nodes"]}
        assert node_ids == {"root", "child1"}

        # Cleanup
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("READ_TEST")
        conn.commit()
        conn.close()

    # PROCESS read_trug SHALL RETURN RECORD metadata AFTER database round-trip.
    def test_read_preserves_metadata(self, tmp_path, sample_trug, dsn):
        """Metadata fields (dimensions, capabilities) survive round-trip."""
        sample_trug["dimensions"] = {
            "folder_structure": {"base_level": "BASE", "description": "test"}
        }
        sample_trug["capabilities"] = {
            "extensions": [], "vocabularies": ["project_v1"], "profiles": []
        }

        out = tmp_path / "META_TEST" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)

        result = read_trug(out, db_dsn=dsn)
        assert "dimensions" in result
        assert result["dimensions"]["folder_structure"]["base_level"] == "BASE"
        assert "capabilities" in result
        assert "project_v1" in result["capabilities"]["vocabularies"]

        # Cleanup
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("META_TEST")
        conn.commit()
        conn.close()

    # PROCESS read_trug SHALL RETURN IDENTICAL RECORD data FROM DATA database AND DATA json.
    def test_db_json_output_identical(self, tmp_path, sample_trug, dsn):
        """DB read and JSON read produce identical node/edge data."""
        out = tmp_path / "COMPARE_TEST" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)

        db_result = read_trug(out, db_dsn=dsn)
        json_result = read_trug(out)  # no DSN → JSON

        # Compare nodes by ID
        db_nodes = {n["id"]: n for n in db_result["nodes"]}
        json_nodes = {n["id"]: n for n in json_result["nodes"]}
        assert db_nodes.keys() == json_nodes.keys()

        for nid in db_nodes:
            assert db_nodes[nid]["type"] == json_nodes[nid]["type"]
            assert db_nodes[nid]["properties"] == json_nodes[nid]["properties"]
            assert db_nodes[nid]["parent_id"] == json_nodes[nid]["parent_id"]

        # Compare edges
        db_edges = {(e["from_id"], e["to_id"], e["relation"]) for e in db_result["edges"]}
        json_edges = {(e["from_id"], e["to_id"], e["relation"]) for e in json_result["edges"]}
        assert db_edges == json_edges

        # Cleanup
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("COMPARE_TEST")
        conn.commit()
        conn.close()


class TestReadTrugResilience:
    """Tests for read error resilience — loud failure when PORT_DSN set."""

    # PROCESS read_trug SHALL REJECT WHEN DATA database connection FAILS.
    def test_bad_dsn_raises(self, tmp_path, sample_trug):
        """When PORT_DSN is set and DB fails → raise, don't silently fall back."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        with pytest.raises(Exception):
            read_trug(out, db_dsn="host=localhost port=99999 dbname=nonexistent")

    # PROCESS read_trug SHALL REJECT WHEN RECORD graph SHALL_NOT EXISTS IN DATA database.
    def test_missing_graph_raises(self, tmp_path, sample_trug):
        """Graph not in DB → raises KeyError (loud failure)."""
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set")

        out = tmp_path / "NOT_IN_DB" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        with pytest.raises(KeyError):
            read_trug(out, db_dsn=dsn)

    # PROCESS read_trug SHALL REJECT WHEN DATA PORT_DSN env FAILS.
    def test_env_var_dsn_raises_on_failure(self, tmp_path, sample_trug):
        """PORT_DSN env var is used — bad DSN raises instead of fallback."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        with patch.dict(os.environ, {"PORT_DSN": "host=localhost port=99999 dbname=nonexistent"}):
            with pytest.raises(Exception):
                read_trug(out)

    # PROCESS read_trug SHALL READ DATA json WITHOUT error WHEN DATA dsn SHALL_NOT EXISTS.
    def test_no_dsn_reads_json_not_error(self, tmp_path, sample_trug):
        """No PORT_DSN = JSON-only mode, not an error (ADR-5)."""
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PORT_DSN", None)
            result = read_trug(out)

        assert result["name"] == "Test Folder"

    # PROCESS read_trug SHALL READ FROM DATA database WHEN DATA json file SHALL_NOT EXISTS.
    def test_json_missing_db_has_graph(self, tmp_path, sample_trug):
        """JSON file doesn't exist but DB has the graph → reads from DB."""
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set")

        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence

        out = tmp_path / "DB_ONLY_TEST" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)
        out.unlink()
        assert not out.exists()

        result = read_trug(out, db_dsn=dsn)
        assert result["name"] == "Test Folder"
        assert len(result["nodes"]) == 2

        # Cleanup
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("DB_ONLY_TEST")
        conn.commit()
        conn.close()

    # PROCESS read_trug SHALL REJECT WHEN DATA json AND DATA database BOTH SHALL_NOT EXISTS.
    def test_json_missing_no_db_raises(self, tmp_path):
        """JSON file doesn't exist and no DB → raises FileNotFoundError."""
        missing = tmp_path / "NOWHERE" / "folder.trug.json"
        missing.parent.mkdir()
        with pytest.raises(FileNotFoundError):
            read_trug(missing)


class TestExportTrug:
    """Tests for export_trug — DB → JSON file."""

    # AGENT claude SHALL DEFINE RECORD dsn AS A RECORD fixture.
    @pytest.fixture
    def dsn(self):
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set")
        return dsn

    # PROCESS export_trug SHALL READ RECORD graph FROM DATA database THEN WRITE TO DATA json file.
    def test_export_writes_json(self, tmp_path, sample_trug, dsn):
        out = tmp_path / "EXPORT_TEST" / "folder.trug.json"
        out.parent.mkdir()
        write_trug(sample_trug, out, db_dsn=dsn)
        out.unlink()  # Remove JSON
        assert not out.exists()

        result = export_trug(out, db_dsn=dsn)
        assert result is True
        assert out.exists()

        loaded = json.loads(out.read_text())
        assert loaded["name"] == "Test Folder"
        assert len(loaded["nodes"]) == 2

        # Cleanup
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("EXPORT_TEST")
        conn.commit()
        conn.close()

    # PROCESS export_trug SHALL RETURN false WHEN RECORD graph SHALL_NOT EXISTS.
    def test_export_missing_graph_returns_false(self, tmp_path, dsn):
        out = tmp_path / "NOT_IN_DB" / "folder.trug.json"
        out.parent.mkdir()

        result = export_trug(out, db_dsn=dsn)
        assert result is False
        assert not out.exists()

    # PROCESS export_trug SHALL REJECT WHEN DATA dsn SHALL_NOT EXISTS.
    def test_export_no_dsn_raises(self, tmp_path):
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PORT_DSN", None)
            with pytest.raises(RuntimeError, match="PORT_DSN not set"):
                export_trug(out)

    # PROCESS export_trug SHALL REJECT WITH RuntimeError WHEN DATA database FAILS.
    def test_export_bad_dsn_raises_runtime_error(self, tmp_path, sample_trug):
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        with pytest.raises(RuntimeError, match="DB read failed"):
            export_trug(out, db_dsn="host=localhost port=99999 dbname=nonexistent")


class TestImportTrug:
    """Tests for import_trug — JSON file → DB."""

    # AGENT claude SHALL DEFINE RECORD dsn AS A RECORD fixture.
    @pytest.fixture
    def dsn(self):
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set")
        return dsn

    # PROCESS import_trug SHALL READ DATA json file THEN WRITE RECORD graph TO DATA database.
    def test_import_populates_db(self, tmp_path, sample_trug, dsn):
        out = tmp_path / "IMPORT_TEST" / "folder.trug.json"
        out.parent.mkdir()
        # Write JSON only (no db_dsn)
        with open(out, "w") as f:
            json.dump(sample_trug, f, indent=2)
            f.write("\n")

        result = import_trug(out, db_dsn=dsn)
        assert result is True

        # Verify DB has the data
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        pg = PostgresPersistence(conn)
        store = pg.load("IMPORT_TEST")
        assert store.node_count() == 2
        assert store.edge_count() == 1

        pg.delete_graph("IMPORT_TEST")
        conn.commit()
        conn.close()

    # PROCESS import_trug SHALL REJECT WHEN DATA dsn SHALL_NOT EXISTS.
    def test_import_no_dsn_raises(self, tmp_path, sample_trug):
        out = tmp_path / "FOLDER" / "folder.trug.json"
        out.parent.mkdir()
        with open(out, "w") as f:
            json.dump(sample_trug, f)

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("PORT_DSN", None)
            with pytest.raises(RuntimeError, match="PORT_DSN not set"):
                import_trug(out)

    # PROCESS import_trug SHALL REJECT WHEN DATA file SHALL_NOT EXISTS.
    def test_import_missing_file_raises(self, tmp_path):
        missing = tmp_path / "FOLDER" / "folder.trug.json"
        missing.parent.mkdir()
        dsn = os.environ.get("TEST_DSN")
        if not dsn:
            pytest.skip("TEST_DSN not set")
        with pytest.raises(FileNotFoundError):
            import_trug(missing, db_dsn=dsn)

    # PROCESS import_trug AND export_trug SHALL PRESERVE RECORD data AFTER round-trip.
    def test_import_export_round_trip(self, tmp_path, sample_trug, dsn):
        """Import JSON → export from DB → JSON matches original."""
        out = tmp_path / "ROUNDTRIP" / "folder.trug.json"
        out.parent.mkdir()
        with open(out, "w") as f:
            json.dump(sample_trug, f, indent=2, ensure_ascii=False)
            f.write("\n")
        original = out.read_text()

        import_trug(out, db_dsn=dsn)
        out.unlink()
        export_trug(out, db_dsn=dsn)

        exported = out.read_text()

        # Compare node/edge content (key order may differ)
        orig_data = json.loads(original)
        exp_data = json.loads(exported)
        orig_ids = {n["id"] for n in orig_data["nodes"]}
        exp_ids = {n["id"] for n in exp_data["nodes"]}
        assert orig_ids == exp_ids

        orig_edges = {(e["from_id"], e["to_id"], e["relation"]) for e in orig_data["edges"]}
        exp_edges = {(e["from_id"], e["to_id"], e["relation"]) for e in exp_data["edges"]}
        assert orig_edges == exp_edges

        # Cleanup
        import psycopg
        from trugs_store.persistence.postgres import PostgresPersistence
        conn = psycopg.connect(dsn)
        PostgresPersistence(conn).delete_graph("ROUNDTRIP")
        conn.commit()
        conn.close()
