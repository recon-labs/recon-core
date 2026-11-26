"""Native and unit proof of the private local DuckDB binding boundary."""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.adapters.duckdb import runtime_scan_guard as guard
from recon_core.adapters.models import Relation
from recon_core.profiles import ConnectionConfig


@pytest.fixture
def duckdb() -> Any:
    if os.environ.get("RECON_REQUIRE_DUCKDB_TESTS") == "1":
        try:
            return importlib.import_module("duckdb")
        except ImportError:
            pytest.fail("Required binding tests need .[dev,duckdb].", pytrace=False)
    return pytest.importorskip("duckdb")


@pytest.mark.regression_capture("key-safety-duckdb-identifier-case-metadata")
@pytest.mark.parametrize(
    ("identifier", "expected"),
    [("MiXeD", "mixed"), ("Ä", "Ä"), ("ä", "ä"), ("Straße", "straße")],
)
def test_binding_identifier_key_is_ascii_only(identifier: str, expected: str) -> None:
    assert guard._duckdb_identifier_key(identifier) == expected


@pytest.mark.regression_capture("key-safety-duckdb-identifier-case-metadata")
@pytest.mark.parametrize("identifier", ["Ä", "ä"])
def test_qualified_relation_binding_preserves_distinct_unicode_tables(
    tmp_path: Path, duckdb: Any, identifier: str
) -> None:
    database = tmp_path / "local.data"
    connection = duckdb.connect(str(database))
    try:
        connection.execute('CREATE TABLE "Ä" AS SELECT 1 AS id')
        connection.execute('CREATE TABLE "ä" AS SELECT 2 AS id')
        assert connection.execute('SELECT id FROM "Ä"').fetchall() == [(1,)]
        assert connection.execute('SELECT id FROM "ä"').fetchall() == [(2,)]
    finally:
        connection.close()

    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": "local.data"})
    status = guard.bounded_local_duckdb_scan_status(
        config,
        source_relation=identifier,
        target_relation=identifier,
        project_root=tmp_path,
    )
    assert status.local_dev
    assert status.bounded, "Distinct identifiers must not be collapsed by Unicode folding."


@pytest.mark.parametrize("kind", ["missing", "directory", "wal", "tmp", "symlink_escape"])
def test_file_scope_admission(tmp_path: Path, kind: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    path = project / "local.data"
    if kind == "directory":
        path.mkdir()
    elif kind in {"wal", "tmp"}:
        path.touch()
        path.with_name(f"{path.name}.{kind}").touch()
    elif kind == "symlink_escape":
        outside = tmp_path / "outside.data"
        outside.touch()
        try:
            path.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are unavailable on this platform.")
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    assert guard._local_file_identity(config, project) is None
    if kind == "missing":
        assert not path.exists()


def test_file_identity_detects_size_and_replacement(tmp_path: Path) -> None:
    path = tmp_path / "local.data"
    path.write_bytes(b"a")
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    assert guard._current_file_identity(path) == identity
    path.write_bytes(b"ab")
    assert guard._current_file_identity(path) != identity
    replacement = tmp_path / "replacement"
    replacement.write_bytes(b"a")
    replacement.replace(path)
    assert guard._current_file_identity(path) != identity


def test_qualified_relation_binding_and_owned_cleanup(tmp_path: Path, duckdb: Any) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute('CREATE TABLE "MiXeD" AS SELECT 1 AS id')
        writer.execute("CREATE SCHEMA other")
        writer.execute('CREATE TABLE other."MiXeD" AS SELECT 2 AS id')
        writer.execute('CREATE VIEW "v" AS SELECT * FROM "MiXeD"')
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        assert session.resolve_relation("mixed") is None
        assert session.resolve_relation("v") is None
        assert session.resolve_relation("absent") is None
        main = session.resolve_relation("MAIN.mixed")
        other = session.resolve_relation("other.mixed")
        assert main is not None and main.catalog is not None
        assert main == Relation(identifier="MiXeD", schema="main", catalog=main.catalog)
        assert other == Relation(identifier="MiXeD", schema="other", catalog=main.catalog)
        assert session.resolve_relation(f"{main.catalog}.main.mixed") == main
        assert session.resolve_relation("wrong.main.mixed") is None
        with pytest.raises(Exception, match="(?i)(configuration|read.only)"):
            duckdb.connect(str(path))
    finally:
        assert session.close() == ()
    assert session.released
    with pytest.raises(binding._BoundSessionError):
        session.resolve_relation("main.mixed")
    writer = duckdb.connect(str(path))
    try:
        assert writer.execute("SELECT count(*) FROM main.mixed").fetchall() == [(1,)]
        assert writer.execute("SELECT id FROM other.mixed").fetchall() == [(2,)]
    finally:
        writer.close()


def test_owned_session_refuses_new_sidecar(tmp_path: Path, duckdb: Any) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute("CREATE TABLE src AS SELECT 1 AS id")
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        assert session.resolve_relation("src") is not None
        path.with_name(f"{path.name}.tmp").touch()
        with pytest.raises(binding._BoundSessionError, match="binding could not be verified"):
            session.resolve_relation("src")
        path.with_name(f"{path.name}.tmp").unlink()
        with pytest.raises(binding._BoundSessionError):
            session.resolve_relation("src")
    finally:
        assert session.close() == ()
    assert session.released


@pytest.mark.parametrize(
    ("failure", "expected_queries", "released", "cleanup_count"),
    [
        ("begin", ["BEGIN TRANSACTION"], True, 0),
        ("rollback", ["BEGIN TRANSACTION", "ROLLBACK"], True, 1),
        ("close", ["BEGIN TRANSACTION", "ROLLBACK"], False, 1),
        ("both", ["BEGIN TRANSACTION", "ROLLBACK"], False, 2),
    ],
)
def test_owned_session_cleanup_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
    expected_queries: list[str],
    released: bool,
    cleanup_count: int,
) -> None:
    path = tmp_path / "local.data"
    path.touch()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    queries: list[str] = []
    closes: list[bool] = []

    class Connection:
        def execute(self, query: str) -> None:
            queries.append(query)
            if query == "BEGIN TRANSACTION" and failure == "begin":
                raise RuntimeError("sensitive-native-error")
            if query == "ROLLBACK" and failure in {"rollback", "both"}:
                raise RuntimeError("sensitive-native-error")

        def close(self) -> None:
            closes.append(True)
            if failure in {"close", "both"}:
                raise RuntimeError("sensitive-native-error")

    def connect(database: str, *, read_only: bool) -> Connection:
        assert database == str(path)
        assert read_only
        return Connection()

    monkeypatch.setattr(binding, "import_module", lambda name: SimpleNamespace(connect=connect))
    session = binding._OwnedDuckDbSession(identity)
    try:
        if failure == "begin":
            with pytest.raises(binding._BoundSessionError) as error:
                session.open()
            assert error.value.diagnostic.code == "RC_ADAPTER_CONNECTION_FAILED"
            assert "sensitive-native-error" not in str(error.value)
        else:
            session.open()
    finally:
        diagnostics = session.close()
    assert queries == expected_queries
    assert closes == [True]
    assert session.released is released
    assert len(diagnostics) == cleanup_count
    assert all(diagnostic.code == "RC_ADAPTER_CLOSE_FAILED" for diagnostic in diagnostics)
    assert all("sensitive-native-error" not in str(diagnostic) for diagnostic in diagnostics)
    assert session.close() == diagnostics
    assert closes == [True]
