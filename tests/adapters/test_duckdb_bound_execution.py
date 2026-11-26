"""Native and unit proof of the private local DuckDB binding boundary."""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from recon_core.adapters.duckdb import _bound_execution as binding
from recon_core.adapters.duckdb import runtime_scan_guard as guard
from recon_core.adapters.duckdb.renderer_sql import render_relation
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


@pytest.mark.parametrize(
    "mismatch", ["check", "operation", "source", "target", "session", "ended", "sidecar", "rebind"]
)
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_lease_invalidation(tmp_path: Path, duckdb: Any, mismatch: str) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute("CREATE TABLE src AS SELECT 1 AS id")
        writer.execute("CREATE TABLE dst AS SELECT 2 AS id")
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    other = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease = session.bind(
            check_id="check-1", operation="row_count_diff", source="src", target="dst"
        )
        assert lease is not None
        scope = lease.scope
        assert scope.source.schema == "main"
        assert scope.target.schema == "main"
        assert scope.source.catalog == scope.target.catalog
        session.verify_lease(lease, scope)
        if mismatch == "session":
            other.open()
            other_lease = other.bind(
                check_id="check-1", operation="row_count_diff", source="src", target="dst"
            )
            assert other_lease is not None and other_lease.scope == scope
            with pytest.raises(binding._BoundSessionError):
                session.verify_lease(other_lease, scope)
        elif mismatch == "ended":
            assert session.close() == ()
            with pytest.raises(binding._BoundSessionError):
                session.verify_lease(lease, scope)
        elif mismatch == "sidecar":
            path.with_name(f"{path.name}.wal").touch()
            try:
                with pytest.raises(binding._BoundSessionError):
                    session.verify_lease(lease, scope)
            finally:
                path.with_name(f"{path.name}.wal").unlink()
        elif mismatch == "rebind":
            with pytest.raises(binding._BoundSessionError):
                session.bind(
                    check_id="check-2", operation="row_count_diff", source="src", target="dst"
                )
        else:
            changed = binding._BindingScope(
                check_id="check-2" if mismatch == "check" else scope.check_id,
                operation="sum_diff" if mismatch == "operation" else scope.operation,
                source=scope.target if mismatch == "source" else scope.source,
                target=scope.source if mismatch == "target" else scope.target,
            )
            with pytest.raises(binding._BoundSessionError) as error:
                session.verify_lease(lease, changed)
            assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
        with pytest.raises(binding._BoundSessionError):
            session.verify_lease(lease, scope)
    finally:
        assert other.close() == ()
        assert session.close() == ()


def test_scope_refusal_cannot_be_rebound(tmp_path: Path, duckdb: Any) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute("CREATE TABLE src AS SELECT 1 AS id")
        writer.execute("CREATE VIEW dst AS SELECT * FROM src")
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease = session.bind(
            check_id="check-1", operation="row_count_diff", source="src", target="dst"
        )
        assert lease is None
        with pytest.raises(binding._BoundSessionError):
            session.bind(check_id="check-1", operation="row_count_diff", source="src", target="src")
    finally:
        assert session.close() == ()


def test_bound_query_reads_canonical_relation(tmp_path: Path, duckdb: Any) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute("CREATE TABLE src AS SELECT 17 AS id")
        writer.execute("CREATE TABLE dst AS SELECT 23 AS id")
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease = session.bind(
            check_id="check-1", operation="row_count_diff", source="src", target="dst"
        )
        assert lease is not None
        query = f"select count(*) as n from {render_relation(lease.scope.source)}"
        result = session._read_bound_query(lease, lease.scope, query)
        assert result.columns == ("n",)
        assert result.rows == ((1,),)
        path.with_name(f"{path.name}.tmp").touch()
        with pytest.raises(binding._BoundSessionError) as error:
            session._read_bound_query(lease, lease.scope, query)
        assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
    finally:
        assert session.close() == ()


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_aggregate_describe_cannot_bypass_invalidated_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "local.data"
    path.touch()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    executed: list[str] = []

    class Cursor:
        description = (("n", "NUMBER"),)

        def fetchmany(self, size: int) -> list[tuple[int]]:
            path.with_name(f"{path.name}.wal").touch()
            return [(1,)]

    class Connection:
        def execute(self, query: str) -> Cursor:
            executed.append(query)
            return Cursor()

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        binding,
        "import_module",
        lambda name: SimpleNamespace(connect=lambda *a, **kw: Connection()),
    )
    monkeypatch.setattr(binding, "_local_duckdb_catalog_names", lambda *a: frozenset({"local"}))
    monkeypatch.setattr(
        binding,
        "_resolve_local_base_table",
        lambda connection, relation, **kw: Relation(
            identifier=relation.identifier, schema="main", catalog="local"
        ),
    )
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease = session.bind(check_id="check-1", operation="sum_diff", source="src", target="dst")
        assert lease is not None
        query = 'select sum(id) as n from "local"."main"."src"'
        with pytest.raises(binding._BoundSessionError) as error:
            session._read_bound_aggregate(lease, lease.scope, query, expected_columns=("n",))
        assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
        assert executed == ["BEGIN TRANSACTION", query]
    finally:
        assert session.close() == ()
    assert executed[-1] == "ROLLBACK"


@pytest.mark.parametrize("rows", [None, [("invalid",)], [(1, None, "path")], [(1, "local", 123)]])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_malformed_catalog_evidence_is_not_scope_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: Any
) -> None:
    path = tmp_path / "local.data"
    path.touch()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None

    class Connection:
        def execute(self, query: str) -> Any:
            return SimpleNamespace(fetchall=lambda: rows)

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        binding,
        "import_module",
        lambda name: SimpleNamespace(connect=lambda *a, **kw: Connection()),
    )
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        with pytest.raises(binding._BoundSessionError) as error:
            session.bind(check_id="check-1", operation="sum_diff", source="src", target="dst")
        assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
    finally:
        assert session.close() == ()


@pytest.mark.parametrize("mode", ["relative", "absolute", "inside_symlink"])
def test_local_file_identity_preserves_canonical_path(tmp_path: Path, mode: str) -> None:
    path = tmp_path / "local.data"
    path.touch()
    authored = path.name if mode == "relative" else str(path)
    if mode == "inside_symlink":
        link = tmp_path / "link.data"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are unavailable on this platform.")
        authored = str(link)
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": authored})
    assert guard._local_file_identity(config, tmp_path) == guard._current_file_identity(path)
    assert guard._current_file_identity(path) is not None


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_mismatched_table_metadata_is_invalid_evidence() -> None:
    class Cursor:
        def fetchmany(self, size: int) -> list[tuple[str, ...]]:
            assert size == 2
            return [("local", "main", "unrelated", "BASE TABLE")]

    class Connection:
        def execute(self, query: str, parameters: list[str]) -> Cursor:
            return Cursor()

    relation = guard._duckdb_relation_name("src")
    assert relation is not None
    with pytest.raises(guard._BindingMetadataError):
        guard._resolve_local_base_table(
            Connection(), relation, local_catalog_names=frozenset({"local"})
        )


@pytest.mark.parametrize("drift", ["mtime", "replacement"])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_file_drift_invalidates_active_lease(tmp_path: Path, duckdb: Any, drift: str) -> None:
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
        lease = session.bind(
            check_id="check-1", operation="row_count_diff", source="src", target="src"
        )
        assert lease is not None
        if drift == "mtime":
            os.utime(path, ns=(identity.modified_ns, identity.modified_ns + 2000000000))
        else:
            replacement = tmp_path / "replacement"
            replacement.write_bytes(path.read_bytes())
            try:
                replacement.replace(path)
            except PermissionError:
                pytest.skip("Platform does not allow replacing an open database file.")
        with pytest.raises(binding._BoundSessionError) as error:
            session.verify_lease(lease, lease.scope)
        assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
    finally:
        assert session.close() == ()


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_quoted_relation_and_temp_shadow_keep_exact_binding(tmp_path: Path, duckdb: Any) -> None:
    path = tmp_path / "local.data"
    writer = duckdb.connect(str(path))
    try:
        writer.execute('CREATE TABLE "quoted""table" AS SELECT 17 AS id')
    finally:
        writer.close()
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    identity = guard._local_file_identity(config, tmp_path)
    assert identity is not None
    session = binding._OwnedDuckDbSession(identity)
    try:
        session.open()
        lease = session.bind(
            check_id="check-1",
            operation="row_count_diff",
            source='quoted"table',
            target='quoted"table',
        )
        assert lease is not None
        # Deliberate test-only intrusion into the otherwise unshared connection.
        session._connection.execute('CREATE TEMP TABLE "quoted""table" AS SELECT 99 AS id')
        query = f"select id from {render_relation(lease.scope.source)}"
        assert session._read_bound_query(lease, lease.scope, query).rows == ((17,),)
        assert session.resolve_relation('temp.main.quoted"table') is None
    finally:
        assert session.close() == ()


@pytest.mark.parametrize("operation", ["row_count_diff", "sum_diff"])
@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_lease_rejects_wrong_transport_family(tmp_path: Path, duckdb: Any, operation: str) -> None:
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
        lease = session.bind(check_id="check-1", operation=operation, source="src", target="src")
        assert lease is not None
        query = f"select count(*) as n from {render_relation(lease.scope.source)}"
        with pytest.raises(binding._BoundSessionError) as error:
            if operation == "row_count_diff":
                session._read_bound_aggregate(lease, lease.scope, query, expected_columns=("n",))
            else:
                session._read_bound_query(lease, lease.scope, query)
        assert error.value.diagnostic.code == "RC_RUNTIME_BINDING_PROOF_FAILED"
        with pytest.raises(binding._BoundSessionError):
            session.verify_lease(lease, lease.scope)
    finally:
        assert session.close() == ()


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_local_file_identity_refuses_stat_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "local.data"
    path.touch()
    original_stat = Path.stat

    def inaccessible(candidate: Path, *args: Any, **kwargs: Any) -> Any:
        if candidate == path:
            raise PermissionError("private-stat-error")
        return original_stat(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", inaccessible)
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    assert guard._local_file_identity(config, tmp_path) is None


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_memory_and_nonlocal_catalog_are_not_local_binding(tmp_path: Path) -> None:
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": ":memory:"})
    assert guard._local_file_identity(config, tmp_path) is None
    relation = guard._duckdb_relation_name("attached.main.src")
    assert relation is not None

    class Cursor:
        def fetchmany(self, size: int) -> list[tuple[str, ...]]:
            assert size == 2
            return [("attached", "main", "src", "BASE TABLE")]

    class Connection:
        def execute(self, query: str, parameters: list[str]) -> Cursor:
            return Cursor()

    assert (
        guard._resolve_local_base_table(
            Connection(), relation, local_catalog_names=frozenset({"local"})
        )
        is None
    )


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_nonregular_file_scope_is_refused(tmp_path: Path) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("Named pipes are unavailable on this platform.")
    path = tmp_path / "named-pipe"
    os.mkfifo(path)
    config = ConnectionConfig(name="warehouse", type="duckdb", config={"database": path.name})
    assert guard._local_file_identity(config, tmp_path) is None


@pytest.mark.regression_capture("duckdb-owned-project-binding")
def test_actual_attached_catalog_is_not_local_base_table(tmp_path: Path, duckdb: Any) -> None:
    local = tmp_path / "local.duckdb"
    external = tmp_path / "external.duckdb"
    writer = duckdb.connect(str(external))
    try:
        writer.execute("CREATE TABLE src AS SELECT 99 AS id")
    finally:
        writer.close()
    # Test-only native catalog fixture, not a supported project-run attachment.
    connection = duckdb.connect(str(local))
    try:
        connection.execute("CREATE TABLE src AS SELECT 17 AS id")
        escaped = str(external).replace("'", "''")
        connection.execute(f"ATTACH '{escaped}' AS attached")
        assert connection.execute("SELECT id FROM attached.main.src").fetchall() == [(99,)]
        catalogs = guard._local_duckdb_catalog_names(connection, local)
        assert catalogs == frozenset({"local"})
        attached = guard._duckdb_relation_name("attached.main.src")
        ambiguous = guard._duckdb_relation_name("src")
        explicit = guard._duckdb_relation_name("local.main.src")
        assert attached is not None and ambiguous is not None and explicit is not None
        assert (
            guard._resolve_local_base_table(connection, attached, local_catalog_names=catalogs)
            is None
        )
        assert (
            guard._resolve_local_base_table(connection, ambiguous, local_catalog_names=catalogs)
            is None
        )
        relation = guard._resolve_local_base_table(
            connection, explicit, local_catalog_names=catalogs
        )
        assert relation is not None
        assert connection.execute(f"SELECT id FROM {render_relation(relation)}").fetchall() == [
            (17,)
        ]
    finally:
        connection.close()
