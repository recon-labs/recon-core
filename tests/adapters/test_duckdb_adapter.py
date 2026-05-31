import tomllib
from pathlib import Path

from recon_core.adapters import CapabilitySupport, ConnectionConfig, Relation
from recon_core.adapters.duckdb import DuckDbAdapterFactory, DuckDbSqlRenderer


def test_duckdb_optional_extra_is_declared() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert "duckdb" in pyproject["project"]["optional-dependencies"]
    assert pyproject["project"]["optional-dependencies"]["duckdb"] == ["duckdb>=1.0"]


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
    assert (
        result.adapter.capabilities().support_for("row_count") is CapabilitySupport.NOT_IMPLEMENTED
    )


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
