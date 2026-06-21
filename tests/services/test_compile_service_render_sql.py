from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from recon_core.adapters import (
    AdapterRegistry,
    Relation,
    RenderedSql,
)
from recon_core.adapters.duckdb import DuckDbAdapterFactory, DuckDbSqlRenderer
from recon_core.services import CompileService
from recon_core.services.results import ExitCategory
from tests.services._compile_service_fixtures import (
    CapabilityRaisingDuckDbAdapterFactory,
    CaseVariantLeakyAdapterFactory,
    CodeLeakyAdapterFactory,
    ConnectionDiagnosticAdapterFactory,
    DecimalShortNumericTextLeakyAdapterFactory,
    DiagnosticAdapterFactory,
    DsnFragmentLeakyAdapterFactory,
    EmbeddedCodeLeakyAdapterFactory,
    EmbeddedConfigKeyCodeLeakyAdapterFactory,
    EmbeddedNumericCodeLeakyAdapterFactory,
    EmptyAdapterFactory,
    FakeAdapterFactory,
    FormattedNumericTextLeakyAdapterFactory,
    IntegerEquivalentQuotedDecimalTextLeakyAdapterFactory,
    InvalidCapabilityDuckDbAdapterFactory,
    InvalidResolutionAdapterFactory,
    LeakyAdapterFactory,
    LeakyApiAdapterFactory,
    LeakyRenderPhaseAdapterFactory,
    MalformedDiagnosticFieldsAdapterFactory,
    MalformedDiagnosticsAdapterFactory,
    MessageAndResourceTypeLeakyAdapterFactory,
    MismatchedAdapterTypeAdapterFactory,
    MissingApiVersionAdapterFactory,
    NonStringAdapterTypeAdapterFactory,
    NumericCodeLeakyAdapterFactory,
    NumericFieldLeakyAdapterFactory,
    NumericValueLeakyAdapterFactory,
    RaisingAdapterFactory,
    RaisingAdapterTypeAdapterFactory,
    ResourceTypeLeakyAdapterFactory,
    ShortNumericAdapterTypeAdapterFactory,
    ShortNumericFieldLeakyAdapterFactory,
    ShortNumericTextLeakyAdapterFactory,
    StepCapabilityUnsupportedDuckDbAdapterFactory,
    _assert_blocked_artifact_includes_messages,
    _assert_distinct_connection_diagnostic_messages,
    _assert_render_sql_blocked_artifact,
    _public_diagnostic_and_rendering_output,
    write_contract,
    write_profiles,
    write_project,
)


def test_render_sql_compile_requires_profiles_file(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)

    result = CompileService(start_path=tmp_path, render_sql=True).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering profile configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_PROFILE_FILE_NOT_FOUND"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_sql").exists()


@pytest.mark.parametrize(
    "connection_type",
    [
        pytest.param("\"{{ env_var('SECRET_ADAPTER_TYPE') }}\"", id="jinja-env-var"),
        pytest.param('"{% if true %}duckdb{% endif %}"', id="jinja-statement"),
        pytest.param('"{# duckdb #}"', id="jinja-comment"),
        pytest.param("env_var('SECRET_ADAPTER_TYPE')", id="bare-env-var"),
    ],
)
def test_render_sql_compile_rejects_templated_adapter_type_without_leaking_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    connection_type: str,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    monkeypatch.setenv("SECRET_ADAPTER_TYPE", "super-secret-adapter")
    write_profiles(tmp_path, connection_type=connection_type)

    result = CompileService(start_path=tmp_path, render_sql=True).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.resource_name} {diagnostic.hint}"
        for diagnostic in result.diagnostics
    )
    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering profile configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_CONFIG_INVALID_PROFILE_CONFIG",
        "RC_CONFIG_INVALID_PROFILE_CONFIG",
    ]
    assert "super-secret-adapter" not in diagnostic_text
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_resolves_adapter_before_sql_rendering(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="unsupported_engine")

    result = CompileService(start_path=tmp_path, render_sql=True).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_UNKNOWN_TYPE",
        "RC_ADAPTER_UNKNOWN_TYPE",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message="Unknown adapter type `unsupported_engine`.",
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_UNKNOWN_TYPE")
    _assert_blocked_artifact_includes_messages(
        tmp_path,
        {
            "Connection `legacy`: Unknown adapter type `unsupported_engine`.",
            "Connection `warehouse`: Unknown adapter type `unsupported_engine`.",
        },
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_missing_duckdb_optional_dependency(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: False))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DEPENDENCY_MISSING",
        "RC_ADAPTER_DEPENDENCY_MISSING",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message="DuckDB adapter dependency is not installed.",
    )
    assert all(
        diagnostic.hint is not None and "recon-core[duckdb]" in diagnostic.hint
        for diagnostic in result.diagnostics
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_DEPENDENCY_MISSING")
    _assert_blocked_artifact_includes_messages(
        tmp_path,
        {
            "Connection `legacy`: DuckDB adapter dependency is not installed.",
            "Connection `warehouse`: DuckDB adapter dependency is not installed.",
        },
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_rejects_factory_result_with_adapter_and_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="diagnostic_adapter")
    registry = AdapterRegistry()
    registry.register("diagnostic_adapter", DiagnosticAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter factory for type `diagnostic_adapter` returned an invalid resolution result."
        ),
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_keeps_distinct_connection_setup_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="connection_diagnostic")
    registry = AdapterRegistry()
    registry.register("connection_diagnostic", ConnectionDiagnosticAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_CONNECTION_SETUP_FAILED",
        "RC_TEST_CONNECTION_SETUP_FAILED",
    ]
    assert {diagnostic.message for diagnostic in result.diagnostics} == {
        "Connection `legacy` setup failed.",
        "Connection `warehouse` setup failed.",
    }
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_CONNECTION_SETUP_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_adapter_setup_and_render_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(
        tmp_path,
        name="setup_contract",
        file_name="setup_contract.yml",
        source_connection="broken",
        target_connection="broken",
    )
    write_contract(
        tmp_path,
        name="query_contract",
        file_name="query_contract.yml",
        source_connection="valid",
        target_connection="valid",
        source_query="select * from qa.customer_source",
    )
    profiles_path = tmp_path / "connections" / "profiles.yml"
    profiles_path.parent.mkdir()
    profiles_path.write_text(
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          broken:
            type: setup_failed
            database: broken.duckdb
          valid:
            type: duckdb
            database: local.duckdb
""".lstrip(),
        encoding="utf-8",
    )
    registry = AdapterRegistry()
    registry.register("setup_failed", ConnectionDiagnosticAdapterFactory())
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    setup_checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "setup_contract.yml").read_text(encoding="utf-8")
    )
    query_checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "query_contract.yml").read_text(encoding="utf-8")
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_TEST_CONNECTION_SETUP_FAILED",
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED",
    }
    assert {
        diagnostic["code"]
        for check in setup_checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_TEST_CONNECTION_SETUP_FAILED"}
    assert {
        diagnostic["code"]
        for check in query_checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_empty_adapter_resolution_result(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="empty")
    registry = AdapterRegistry()
    registry.register("empty", EmptyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message="Adapter factory for type `empty` returned an invalid resolution result.",
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_invalid_adapter_resolution_result(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="invalid_resolution")
    registry = AdapterRegistry()
    registry.register("invalid_resolution", InvalidResolutionAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter factory for type `invalid_resolution` returned an invalid resolution result."
        ),
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_malformed_adapter_resolution_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="malformed_diagnostics")
    registry = AdapterRegistry()
    registry.register("malformed_diagnostics", MalformedDiagnosticsAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter factory for type `malformed_diagnostics` returned an invalid "
            "resolution result."
        ),
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_malformed_adapter_resolution_diagnostic_fields(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="malformed_diagnostic_fields")
    registry = AdapterRegistry()
    registry.register(
        "malformed_diagnostic_fields",
        MalformedDiagnosticFieldsAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter factory for type `malformed_diagnostic_fields` returned an invalid "
            "resolution result."
        ),
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_adapter_factory_exceptions(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="raising", include_password=True)
    registry = AdapterRegistry()
    registry.register("raising", RaisingAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED",
        "RC_ADAPTER_RESOLUTION_FAILED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message="Adapter factory for type `raising` failed.",
    )
    assert "ValueError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_RESOLUTION_FAILED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_adapter_api_compatibility_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="leaky_api", include_password=True)
    registry = AdapterRegistry()
    registry.register("leaky_api", LeakyApiAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_API_VERSION_UNSUPPORTED",
        "RC_ADAPTER_API_VERSION_UNSUPPORTED",
    ]
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_API_VERSION_UNSUPPORTED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_rejects_adapter_type_metadata_that_differs_from_profile_type(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="fake_duck")
    registry = AdapterRegistry()
    registry.register("fake_duck", MismatchedAdapterTypeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_TYPE_MISMATCH",
        "RC_ADAPTER_TYPE_MISMATCH",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter factory for profile type `fake_duck` returned adapter metadata "
            "that does not match the profile connection type."
        ),
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_TYPE_MISMATCH")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_non_string_adapter_type_metadata(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="numeric_adapter_type")
    registry = AdapterRegistry()
    registry.register("numeric_adapter_type", NonStringAdapterTypeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_METADATA_INVALID",
        "RC_ADAPTER_METADATA_INVALID",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter `NonStringAdapterTypeAdapter` does not declare a valid `adapter_type`."
        ),
    )
    assert all(
        diagnostic.resource_name == "NonStringAdapterTypeAdapter"
        for diagnostic in result.diagnostics
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_METADATA_INVALID")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_raising_adapter_type_metadata(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="raising_adapter_type", include_password=True)
    registry = AdapterRegistry()
    registry.register("raising_adapter_type", RaisingAdapterTypeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_METADATA_INVALID",
        "RC_ADAPTER_METADATA_INVALID",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter `RaisingAdapterTypeAdapter` does not declare a valid `adapter_type`."
        ),
    )
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_METADATA_INVALID")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_adapter_resolution_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="leaky", include_password=True)
    registry = AdapterRegistry()
    registry.register("leaky", LeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_LEAK",
        "RC_TEST_ADAPTER_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "password" not in diagnostic_text
    assert "local.duckdb" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_adapter_resolution_dsn_fragment_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="dsn_fragment_leaky",
        database="duckdb://user:super-secret@host/db",
    )
    registry = AdapterRegistry()
    registry.register("dsn_fragment_leaky", DsnFragmentLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_DSN_FRAGMENT_LEAK",
        "RC_TEST_ADAPTER_DSN_FRAGMENT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "super-secret" not in public_output
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_DSN_FRAGMENT_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_adapter_resolution_diagnostic_codes(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="code_leaky", include_password=True)
    registry = AdapterRegistry()
    registry.register("code_leaky", CodeLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "super-secret" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_numeric_adapter_resolution_diagnostic_codes(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="numeric_code_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register("numeric_code_leaky", NumericCodeLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "12" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_embedded_adapter_resolution_diagnostic_codes(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="embedded_code_leaky", include_password=True)
    registry = AdapterRegistry()
    registry.register("embedded_code_leaky", EmbeddedCodeLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "super-secret" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_separatorless_config_key_diagnostic_codes(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="embedded_key_code_leaky",
        include_password=True,
    )
    registry = AdapterRegistry()
    registry.register(
        "embedded_key_code_leaky",
        EmbeddedConfigKeyCodeLeakyAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "RCPASSWORDLEAK" not in public_output
    assert "password" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_embedded_numeric_adapter_resolution_diagnostic_codes(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="embedded_numeric_code_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register(
        "embedded_numeric_code_leaky",
        EmbeddedNumericCodeLeakyAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "12" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_missing_adapter_api_version(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="missing_api")
    registry = AdapterRegistry()
    registry.register("missing_api", MissingApiVersionAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_API_VERSION_UNSUPPORTED",
        "RC_ADAPTER_API_VERSION_UNSUPPORTED",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message=(
            "Adapter `missing_api` does not declare a valid supported "
            "adapter API version; Recon Core requires `1`."
        ),
    )
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_API_VERSION_UNSUPPORTED")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_non_string_adapter_resolution_values(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="numeric_leaky",
        include_password=True,
        password="123456",
    )
    registry = AdapterRegistry()
    registry.register("numeric_leaky", NumericValueLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_NUMERIC_LEAK",
        "RC_TEST_ADAPTER_NUMERIC_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "123456" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_NUMERIC_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_numeric_diagnostic_fields(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="numeric_field_leaky",
        include_password=True,
        password="123456",
    )
    registry = AdapterRegistry()
    registry.register("numeric_field_leaky", NumericFieldLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_NUMERIC_FIELD_LEAK",
        "RC_TEST_ADAPTER_NUMERIC_FIELD_LEAK",
    ]
    assert all(diagnostic.line is None for diagnostic in result.diagnostics)
    assert all(diagnostic.column is None for diagnostic in result.diagnostics)
    assert all(
        diagnostic["line"] is None and diagnostic["column"] is None
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    )
    assert "123456" not in yaml.safe_dump(
        {
            "service": [diagnostic.to_dict() for diagnostic in result.diagnostics],
            "artifact": checks_artifact,
        },
        sort_keys=False,
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_NUMERIC_FIELD_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_short_numeric_diagnostic_fields(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="short_numeric_field_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register("short_numeric_field_leaky", ShortNumericFieldLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_SHORT_NUMERIC_FIELD_LEAK",
        "RC_TEST_ADAPTER_SHORT_NUMERIC_FIELD_LEAK",
    ]
    assert all(diagnostic.line is None for diagnostic in result.diagnostics)
    assert all(diagnostic.column is None for diagnostic in result.diagnostics)
    assert all(
        diagnostic["line"] is None and diagnostic["column"] is None
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    )
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_SHORT_NUMERIC_FIELD_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_short_numeric_text_and_resource_fields(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="short_numeric_text_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register("short_numeric_text_leaky", ShortNumericTextLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_SHORT_NUMERIC_TEXT_LEAK",
        "RC_TEST_ADAPTER_SHORT_NUMERIC_TEXT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "12" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_SHORT_NUMERIC_TEXT_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_decimal_short_numeric_text_and_resource_fields(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="decimal_short_numeric_text_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register(
        "decimal_short_numeric_text_leaky",
        DecimalShortNumericTextLeakyAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_DECIMAL_SHORT_NUMERIC_TEXT_LEAK",
        "RC_TEST_ADAPTER_DECIMAL_SHORT_NUMERIC_TEXT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "12.0" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_DECIMAL_SHORT_NUMERIC_TEXT_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_integer_equivalent_text_for_quoted_decimal_profile_values(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="integer_equivalent_quoted_decimal_text_leaky",
        port='"12.0"',
    )
    registry = AdapterRegistry()
    registry.register(
        "integer_equivalent_quoted_decimal_text_leaky",
        IntegerEquivalentQuotedDecimalTextLeakyAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_INTEGER_EQUIVALENT_QUOTED_DECIMAL_TEXT_LEAK",
        "RC_TEST_ADAPTER_INTEGER_EQUIVALENT_QUOTED_DECIMAL_TEXT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "endpoint 12" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_INTEGER_EQUIVALENT_QUOTED_DECIMAL_TEXT_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


@pytest.mark.parametrize(
    "emitted_port",
    ["+12", "1.2e1"],
)
def test_render_sql_compile_sanitizes_integer_equivalent_formatted_text_variants(
    tmp_path: Path,
    emitted_port: str,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="formatted_numeric_text_leaky",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register(
        "formatted_numeric_text_leaky",
        FormattedNumericTextLeakyAdapterFactory(emitted_port=emitted_port),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert f"endpoint {emitted_port}" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_env_var_rendered_numeric_string_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RECON_TEST_PORT", "12.0")
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="formatted_numeric_text_leaky",
        port="\"{{ env_var('RECON_TEST_PORT') }}\"",
    )
    registry = AdapterRegistry()
    registry.register(
        "formatted_numeric_text_leaky",
        FormattedNumericTextLeakyAdapterFactory(emitted_port="1.2e1"),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "endpoint 1.2e1" not in public_output
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_FORMATTED_NUMERIC_TEXT_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_short_numeric_adapter_type_mismatch(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="short_numeric_adapter_type",
        port=12,
    )
    registry = AdapterRegistry()
    registry.register("short_numeric_adapter_type", ShortNumericAdapterTypeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_TYPE_MISMATCH",
        "RC_ADAPTER_TYPE_MISMATCH",
    ]
    assert "12" not in public_output
    _assert_render_sql_blocked_artifact(tmp_path, "RC_ADAPTER_TYPE_MISMATCH")
    assert all("adapter_type" not in check["rendering"] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_preserves_capability_code_with_non_secret_config_key(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    profiles_path = tmp_path / "connections" / "profiles.yml"
    profiles_path.parent.mkdir()
    profiles_path.write_text(
        """
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: fake
            adapter: generic
            database: local.duckdb
          warehouse:
            type: fake
            adapter: generic
            database: local.duckdb
""".lstrip(),
        encoding="utf-8",
    )
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    public_output = _public_diagnostic_and_rendering_output(result, checks_artifact)

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED" not in public_output
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_CAPABILITY_UNSUPPORTED"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_case_variant_adapter_resolution_diagnostics(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="case_leaky",
        include_password=True,
        password="SuperSecret",
    )
    registry = AdapterRegistry()
    registry.register("case_leaky", CaseVariantLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_CASE_VARIANT_LEAK",
        "RC_TEST_ADAPTER_CASE_VARIANT_LEAK",
    ]
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "PASSWORD" not in diagnostic_text
    assert "supersecret" not in diagnostic_text
    assert "DATABASE" not in diagnostic_text
    assert "LOCAL.DUCKDB" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_CASE_VARIANT_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_resource_type_only_adapter_resolution_leak(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="resource_type_leaky",
        include_password=True,
        password="SuperSecret",
    )
    registry = AdapterRegistry()
    registry.register("resource_type_leaky", ResourceTypeLeakyAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_RESOURCE_TYPE_LEAK",
        "RC_TEST_ADAPTER_RESOURCE_TYPE_LEAK",
    ]
    assert {diagnostic.resource_type for diagnostic in result.diagnostics} == {"adapter"}
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "PASSWORD" not in diagnostic_text
    assert "supersecret" not in diagnostic_text
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_RESOURCE_TYPE_LEAK")
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_replaces_resource_type_when_message_triggers_sanitization(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(
        tmp_path,
        connection_type="message_and_resource_type_leaky",
        include_password=True,
        password="SuperSecret",
    )
    registry = AdapterRegistry()
    registry.register(
        "message_and_resource_type_leaky",
        MessageAndResourceTypeLeakyAdapterFactory(),
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_TEST_ADAPTER_MESSAGE_AND_RESOURCE_TYPE_LEAK",
        "RC_TEST_ADAPTER_MESSAGE_AND_RESOURCE_TYPE_LEAK",
    ]
    assert {diagnostic.resource_type for diagnostic in result.diagnostics} == {"adapter"}
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "PASSWORD" not in diagnostic_text
    assert "supersecret" not in diagnostic_text
    _assert_render_sql_blocked_artifact(
        tmp_path,
        "RC_TEST_ADAPTER_MESSAGE_AND_RESOURCE_TYPE_LEAK",
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


@pytest.mark.regression_capture("compile-diagnostic-render-sql-precedence")
def test_render_sql_compile_reports_compile_validation_before_profile_errors(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path, include_grain=False)

    result = CompileService(start_path=tmp_path, render_sql=True).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert (
        result.message
        == "Compile completed with 1 diagnostic. Wrote compiled artifacts for 1 contract."
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    ]
    assert checks_artifact["checks"] == []
    assert not (tmp_path / "target" / "compiled_sql").exists()


@pytest.mark.regression_capture("compile-diagnostic-render-sql-precedence")
def test_render_sql_compile_marks_renderable_checks_blocked_when_compile_validation_fails(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path, name="valid_contract", file_name="valid_contract.yml")
    write_contract(
        tmp_path,
        name="invalid_contract",
        file_name="invalid_contract.yml",
        include_grain=False,
    )

    result = CompileService(start_path=tmp_path, render_sql=True).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "valid_contract.yml").read_text(encoding="utf-8")
    )

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    ]
    assert {check["rendering"]["status"] for check in checks_artifact["checks"]} == {"blocked"}
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_writes_sql_artifacts_and_rendering_metadata(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    compiled_contracts_dir = tmp_path / "target" / "compiled_contracts"
    compiled_checks_dir = tmp_path / "target" / "compiled_checks"
    compiled_sql_dir = tmp_path / "target" / "compiled_sql"
    checks_artifact = yaml.safe_load(
        (compiled_checks_dir / "customer_revenue.yml").read_text(encoding="utf-8")
    )
    row_count_check = next(
        check for check in checks_artifact["checks"] if check["name"] == "row_count_diff"
    )

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == (
        f"Compiled 1 contract. Wrote artifacts to {compiled_contracts_dir}, "
        f"{compiled_checks_dir}, and {compiled_sql_dir}."
    )
    assert result.diagnostics == ()
    assert (compiled_contracts_dir / "customer_revenue.yml").is_file()
    assert all(check["rendering"]["status"] == "rendered" for check in checks_artifact["checks"])
    assert all(
        check["rendering"]["adapter_type"] == "duckdb" for check in checks_artifact["checks"]
    )
    assert row_count_check["rendering"]["sql_paths"] == [
        "compiled_sql/customer_revenue/"
        "check.ecommerce_recon.customer_revenue.row_count_diff/00-row_count-source.sql",
        "compiled_sql/customer_revenue/"
        "check.ecommerce_recon.customer_revenue.row_count_diff/01-row_count-target.sql",
        "compiled_sql/customer_revenue/"
        "check.ecommerce_recon.customer_revenue.row_count_diff/02-compare_counts.sql",
    ]
    assert (tmp_path / "target" / row_count_check["rendering"]["sql_paths"][0]).read_text(
        encoding="utf-8"
    ) == ('select count(*) as row_count\nfrom "qa"."customer_source"\n')


def test_render_sql_compile_blocks_distinct_connection_contexts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, use_distinct_databases=True)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    ]
    assert all(check["rendering"]["status"] == "blocked" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_marks_query_endpoints_blocked_without_sql_artifacts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path, source_query="select * from qa.customer_source")
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    ]
    assert all(check["rendering"]["status"] == "blocked" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_marks_other_checks_blocked_when_any_rendering_fails(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path, name="valid_contract", file_name="valid_contract.yml")
    write_contract(
        tmp_path,
        name="query_contract",
        file_name="query_contract.yml",
        source_query="select * from qa.customer_source",
    )
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    valid_checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "valid_contract.yml").read_text(encoding="utf-8")
    )
    query_checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "query_contract.yml").read_text(encoding="utf-8")
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"
    ]
    assert all(
        check["rendering"]
        == {
            "status": "blocked",
            "sql_paths": [],
            "adapter_type": "duckdb",
        }
        for check in valid_checks_artifact["checks"]
    )
    assert {
        diagnostic["code"]
        for check in valid_checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_RENDERING_OUTPUT_SUPPRESSED"}
    assert all(
        check["rendering"]
        == {
            "status": "blocked",
            "sql_paths": [],
            "adapter_type": "duckdb",
        }
        for check in query_checks_artifact["checks"]
    )
    assert {
        diagnostic["code"]
        for check in query_checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {"RC_ADAPTER_QUERY_ENDPOINT_UNSUPPORTED"}
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_marks_adapter_renderer_blocks_without_sql_artifacts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, connection_type="fake")
    registry = AdapterRegistry()
    registry.register("fake", FakeAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert all(check["rendering"]["status"] == "blocked" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_capability_declaration_failure_artifacts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, include_password=True)
    registry = AdapterRegistry()
    registry.register("duckdb", CapabilityRaisingDuckDbAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact_text = (
        tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    ).read_text(encoding="utf-8")
    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"
    }
    assert "ValueError" in diagnostic_text
    assert "ValueError" in checks_artifact_text
    assert "super-secret" not in diagnostic_text
    assert "super-secret" not in checks_artifact_text
    assert "password" not in diagnostic_text
    assert "password" not in checks_artifact_text
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_reports_invalid_capability_support_state(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", InvalidCapabilityDuckDbAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact_text = (
        tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    ).read_text(encoding="utf-8")

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert "RC_ADAPTER_CAPABILITY_UNSUPPORTED" in {
        diagnostic.code for diagnostic in result.diagnostics
    }
    assert "invalid support state" in checks_artifact_text
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_enforces_rendered_step_required_capabilities(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", StepCapabilityUnsupportedDuckDbAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact_text = (
        tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    ).read_text(encoding="utf-8")

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    }
    assert "cte_support" in checks_artifact_text
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_marks_renderer_failures_without_sql_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    class BrokenDuckDbSqlRenderer:
        adapter_type = "duckdb"

        def render_operation(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("render_plan should be used by the service")

        def render_plan(self, *args: object, **kwargs: object) -> tuple[object, ...]:
            raise ValueError("broken renderer")

        def quote_identifier(self, identifier: str) -> str:
            return identifier

        def render_relation(self, relation: object) -> str:
            return str(relation)

    monkeypatch.setattr(
        "recon_core.services._compile_render_sql.DuckDbSqlRenderer",
        BrokenDuckDbSqlRenderer,
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_OPERATION_RENDER_FAILED"
    }
    assert all(check["rendering"]["status"] == "failed" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_sanitizes_renderer_failure_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    class SecretLeakingDuckDbSqlRenderer(DuckDbSqlRenderer):
        def render_plan(
            self,
            operations: tuple[Mapping[str, Any], ...],
            *,
            source_relation: Relation,
            target_relation: Relation,
        ) -> tuple[RenderedSql, ...]:
            raise ValueError("password=super-secret")

    monkeypatch.setattr(
        "recon_core.services._compile_render_sql.DuckDbSqlRenderer",
        SecretLeakingDuckDbSqlRenderer,
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact_text = (
        tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    ).read_text(encoding="utf-8")
    diagnostic_text = "\n".join(
        f"{diagnostic.message} {diagnostic.hint}" for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert "ValueError" in diagnostic_text
    assert "ValueError" in checks_artifact_text
    assert "super-secret" not in diagnostic_text
    assert "super-secret" not in checks_artifact_text
    assert "password" not in diagnostic_text
    assert "password" not in checks_artifact_text
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_marks_empty_renderer_output_failed_without_sql_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    class EmptyDuckDbSqlRenderer:
        adapter_type = "duckdb"

        def render_operation(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("render_plan should be used by the service")

        def render_plan(self, *args: object, **kwargs: object) -> tuple[RenderedSql, ...]:
            return ()

        def quote_identifier(self, identifier: str) -> str:
            return identifier

        def render_relation(self, relation: object) -> str:
            return str(relation)

    monkeypatch.setattr(
        "recon_core.services._compile_render_sql.DuckDbSqlRenderer",
        EmptyDuckDbSqlRenderer,
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_RENDERED_SQL_EMPTY"
    }
    assert all(check["rendering"]["status"] == "failed" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


@pytest.mark.parametrize(
    "rendered_sql",
    [
        pytest.param((cast(RenderedSql, object()),), id="non-rendered-sql-step"),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="../outside",
                ),
            ),
            id="path-like-step-name",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="same",
                ),
                RenderedSql(
                    sql="select 2",
                    operation_type="row_count",
                    step_name="same",
                ),
            ),
            id="duplicate-step-name",
        ),
        pytest.param(
            (
                RenderedSql(
                    sql="select 1",
                    operation_type="row_count",
                    step_name="Same",
                ),
                RenderedSql(
                    sql="select 2",
                    operation_type="row_count",
                    step_name="same",
                ),
            ),
            id="case-insensitive-duplicate-step-name",
        ),
    ],
)
def test_render_sql_compile_marks_malformed_renderer_output_failed_without_crashing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rendered_sql: tuple[object, ...],
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    class MalformedDuckDbSqlRenderer:
        adapter_type = "duckdb"

        def render_operation(self, *args: object, **kwargs: object) -> object:
            raise AssertionError("render_plan should be used by the service")

        def render_plan(self, *args: object, **kwargs: object) -> tuple[RenderedSql, ...]:
            return cast(tuple[RenderedSql, ...], rendered_sql)

        def quote_identifier(self, identifier: str) -> str:
            return identifier

        def render_relation(self, relation: object) -> str:
            return str(relation)

    monkeypatch.setattr(
        "recon_core.services._compile_render_sql.DuckDbSqlRenderer",
        MalformedDuckDbSqlRenderer,
    )

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_OPERATION_RENDER_FAILED"
    }
    assert all(check["rendering"]["status"] == "failed" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_rejects_secret_bearing_adapter_metadata_mismatch(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path, include_password=True)
    registry = AdapterRegistry()
    registry.register("duckdb", LeakyRenderPhaseAdapterFactory())

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    checks_artifact_text = (
        tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    ).read_text(encoding="utf-8")
    diagnostic_text = "\n".join(
        " ".join(
            value
            for value in (
                diagnostic.message,
                diagnostic.resource_type,
                diagnostic.resource_name,
                diagnostic.path,
                diagnostic.hint,
            )
            if value is not None
        )
        for diagnostic in result.diagnostics
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering adapter configuration failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {"RC_ADAPTER_TYPE_MISMATCH"}
    assert "super-secret" not in diagnostic_text
    assert "super-secret" not in checks_artifact_text
    assert "password" not in diagnostic_text
    assert "password" not in checks_artifact_text
    assert all("adapter_type" not in check["rendering"] for check in checks_artifact["checks"])
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_render_sql_compile_writes_no_sql_when_compiled_artifact_path_is_invalid(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))
    target_path = tmp_path / "target"
    target_path.mkdir()
    (target_path / "compiled_contracts").write_text("not a directory\n", encoding="utf-8")

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert not (target_path / "compiled_sql").exists()


def test_render_sql_compile_removes_sql_when_yaml_artifact_write_fails_after_rendering(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))
    stale_contract_artifact_dir = (
        tmp_path / "target" / "compiled_contracts" / ("customer_revenue.yml")
    )
    stale_contract_artifact_dir.mkdir(parents=True)

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert not (tmp_path / "target" / "compiled_sql").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_render_sql_compile_preflights_all_sql_paths_before_first_sql_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_project(tmp_path, profile="local")
    write_profiles(tmp_path)
    tmp_path.joinpath("contracts", "customer_revenue.yml").write_text(
        """
version: 1
name: customer_revenue
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
metrics:
  - name: Total
    type: sum
    column: revenue
  - name: total
    type: sum
    column: revenue
checks:
  use: []
""".lstrip(),
        encoding="utf-8",
    )
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))
    original_write_text = Path.write_text

    def write_text_without_sql_publish(
        path: Path,
        data: str,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        if "compiled_sql" in path.parts:
            raise AssertionError("compiled SQL was written before full-batch preflight finished")
        return original_write_text(path, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_text_without_sql_publish)

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert "case-insensitive collision" in result.diagnostics[0].message
    assert not (tmp_path / "target" / "compiled_sql").exists()
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_render_sql_compile_removes_partial_yaml_when_artifact_write_fails_after_rendering(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path, name="aaa", file_name="aaa.yml")
    write_contract(tmp_path, name="bbb", file_name="bbb.yml")
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))
    blocking_contract_path = tmp_path / "target" / "compiled_contracts" / "bbb.yml"
    blocking_contract_path.mkdir(parents=True)

    result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "aaa.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "aaa.yml").exists()
    assert not (tmp_path / "target" / "compiled_sql").exists()
