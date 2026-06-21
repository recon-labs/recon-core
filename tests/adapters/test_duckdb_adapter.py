import ast
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

from recon_core.adapters import CapabilitySupport, ConnectionConfig, QueryResult, Relation
from recon_core.adapters.duckdb import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
    AdapterLifecycleError,
    DuckDbAdapter,
    DuckDbAdapterFactory,
    DuckDbSqlRenderer,
)
from recon_core.adapters.duckdb import adapter as duckdb_adapter_module
from recon_core.adapters.duckdb import renderer as duckdb_renderer_module
from recon_core.adapters.duckdb import renderer_operations as duckdb_renderer_operations_module
from recon_core.adapters.duckdb import renderer_sql as duckdb_renderer_sql_module


def test_duckdb_optional_extra_is_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "duckdb" in pyproject["project"]["optional-dependencies"]
    assert pyproject["project"]["optional-dependencies"]["duckdb"] == ["duckdb>=1.0"]


def test_duckdb_renderer_imports_remain_compatible() -> None:
    from recon_core.adapters.duckdb import DuckDbSqlRenderer as PackageRenderer
    from recon_core.adapters.duckdb.adapter import DuckDbSqlRenderer as AdapterModuleRenderer
    from recon_core.adapters.duckdb.renderer import DuckDbSqlRenderer as RendererModuleRenderer

    assert PackageRenderer is RendererModuleRenderer
    assert AdapterModuleRenderer is RendererModuleRenderer
    assert PackageRenderer().adapter_type == "duckdb"


def test_duckdb_renderer_modules_do_not_import_optional_duckdb_dependency() -> None:
    for module in (
        duckdb_renderer_module,
        duckdb_renderer_operations_module,
        duckdb_renderer_sql_module,
    ):
        module_path = getattr(module, "__file__", None)
        assert module_path is not None

        imported_modules = _imported_modules_from(Path(module_path))

        assert "duckdb" not in imported_modules
        assert not any(
            imported_module.startswith("duckdb.") for imported_module in imported_modules
        )


def test_duckdb_factory_reports_missing_optional_dependency() -> None:
    factory = DuckDbAdapterFactory(dependency_available=lambda: False)

    result = factory.create(ConnectionConfig(name="warehouse", type="duckdb"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DEPENDENCY_MISSING"
    ]
    assert result.diagnostics[0].hint is not None
    assert "recon-core[duckdb]" in result.diagnostics[0].hint


def test_duckdb_factory_creates_adapter_when_dependency_is_available() -> None:
    factory = DuckDbAdapterFactory(dependency_available=lambda: True)

    result = factory.create(ConnectionConfig(name="warehouse", type="duckdb"))

    assert result.succeeded
    assert result.adapter is not None
    assert result.adapter.adapter_type == "duckdb"
    assert result.adapter.capabilities().support_for("relations") is CapabilitySupport.FULL
    assert result.adapter.capabilities().support_for("queries") is CapabilitySupport.UNSUPPORTED
    assert result.adapter.capabilities().support_for("row_count") is CapabilitySupport.FULL
    assert result.adapter.capabilities().support_for("aggregate") is CapabilitySupport.FULL
    assert result.adapter.capabilities().support_for("key_diff") is CapabilitySupport.FULL


def test_duckdb_adapter_connect_execute_and_close_use_rendered_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCursor:
        description = (("answer",), ("label",))

        def fetchall(self) -> list[tuple[int, str]]:
            return [(1, "ok")]

    class FakeConnection:
        def __init__(self) -> None:
            self.queries: list[str] = []
            self.closed = False

        def execute(self, query: str) -> FakeCursor:
            self.queries.append(query)
            return FakeCursor()

        def close(self) -> None:
            self.closed = True

    opened_connections: list[FakeConnection] = []
    opened_databases: list[str] = []

    def connect(database: str) -> FakeConnection:
        opened_databases.append(database)
        connection = FakeConnection()
        opened_connections.append(connection)
        return connection

    monkeypatch.setattr(
        duckdb_adapter_module,
        "import_module",
        lambda module_name: SimpleNamespace(connect=connect),
    )
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"database": "local.duckdb"},
        )
    )

    adapter.connect()
    result = adapter.execute("select 1 as answer, 'ok' as label")
    adapter.close()

    assert opened_databases == ["local.duckdb"]
    assert opened_connections[0].queries == ["select 1 as answer, 'ok' as label"]
    assert opened_connections[0].closed
    assert result == QueryResult(columns=("answer", "label"), rows=((1, "ok"),), row_count=1)


def test_duckdb_adapter_connection_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def connect(database: str) -> object:
        raise RuntimeError(f"password=super-secret database={database}")

    monkeypatch.setattr(
        duckdb_adapter_module,
        "import_module",
        lambda module_name: SimpleNamespace(connect=connect),
    )
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"database": "/tmp/private-super-secret.duckdb"},
        )
    )

    with pytest.raises(AdapterLifecycleError) as exc_info:
        adapter.connect()

    diagnostic = exc_info.value.diagnostic
    diagnostic_text = f"{diagnostic.message} {diagnostic.hint}"

    assert diagnostic.code == ADAPTER_CONNECTION_FAILED
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password=" not in diagnostic_text
    assert "/tmp/private-super-secret.duckdb" not in diagnostic_text


def test_duckdb_adapter_query_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingConnection:
        def execute(self, query: str) -> object:
            raise RuntimeError(f"Binder Error near {query} with token super-secret")

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        duckdb_adapter_module,
        "import_module",
        lambda module_name: SimpleNamespace(connect=lambda database: FailingConnection()),
    )
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"database": ":memory:", "password": "super-secret"},
        )
    )

    adapter.connect()
    with pytest.raises(AdapterLifecycleError) as exc_info:
        adapter.execute("select 'super-secret' as token")

    diagnostic = exc_info.value.diagnostic
    diagnostic_text = f"{diagnostic.message} {diagnostic.hint}"

    assert diagnostic.code == ADAPTER_QUERY_FAILED
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
    assert "select 'super-secret' as token" not in diagnostic_text
    assert "Binder Error" not in diagnostic_text


def test_duckdb_adapter_close_failure_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingCloseConnection:
        def execute(self, query: str) -> object:
            return SimpleNamespace(description=(), fetchall=lambda: [])

        def close(self) -> None:
            raise RuntimeError("close leaked super-secret")

    monkeypatch.setattr(
        duckdb_adapter_module,
        "import_module",
        lambda module_name: SimpleNamespace(connect=lambda database: FailingCloseConnection()),
    )
    adapter = DuckDbAdapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="duckdb",
            config={"database": ":memory:", "password": "super-secret"},
        )
    )

    adapter.connect()
    with pytest.raises(AdapterLifecycleError) as exc_info:
        adapter.close()

    diagnostic = exc_info.value.diagnostic
    diagnostic_text = f"{diagnostic.message} {diagnostic.hint}"

    assert diagnostic.code == ADAPTER_CLOSE_FAILED
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_duckdb_renderer_quotes_identifiers_and_relations_deterministically() -> None:
    renderer = DuckDbSqlRenderer()

    assert renderer.quote_identifier('customer"orders') == '"customer""orders"'
    assert renderer.render_relation(Relation(identifier="customers")) == '"customers"'
    assert (
        renderer.render_relation(Relation(schema="qa", identifier="customers"))
        == '"qa"."customers"'
    )
    assert (
        renderer.render_relation(Relation(catalog="warehouse", schema="qa", identifier="customers"))
        == '"warehouse"."qa"."customers"'
    )


def _imported_modules_from(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported_modules.add(node.module)
    return imported_modules
