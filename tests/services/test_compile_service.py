from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from recon_core.adapters import (
    AdapterCapabilities,
    AdapterRegistry,
    AdapterResolutionResult,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    QueryResult,
    Relation,
    RenderedSql,
)
from recon_core.adapters.duckdb import DuckDbAdapterFactory, DuckDbSqlRenderer
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig
from recon_core.services import CompileService
from recon_core.services.results import ExitCategory


def test_compile_service_writes_compiled_artifacts_for_valid_project(tmp_path: Path) -> None:
    write_project(tmp_path)
    nulls: dict[str, object] = {
        "treat_as_null": {
            "values": ["", "NULL"],
            "regex": ["^\\s*$"],
        }
    }
    write_contract(tmp_path, tolerance_policy="finance", nulls=nulls)

    result = CompileService(start_path=tmp_path).execute()

    contract_path = tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml"
    checks_path = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.message == (
        f"Compiled 1 contract. Wrote artifacts to {contract_path.parent} and {checks_path.parent}."
    )
    assert result.diagnostics == ()

    contract_artifact = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    checks_artifact = yaml.safe_load(checks_path.read_text(encoding="utf-8"))

    assert contract_artifact["artifact_type"] == "compiled_contract"
    assert contract_artifact["contract"]["id"] == "contract.ecommerce_recon.customer_revenue"
    assert contract_artifact["artifact_version"] == 1
    assert contract_artifact["policies"]["tolerance_policy"] == "finance"
    assert contract_artifact["policies"]["nulls"] == nulls
    assert "normalization" not in contract_artifact["policies"]
    assert checks_artifact["artifact_type"] == "compiled_checks"
    assert [check["name"] for check in checks_artifact["checks"]] == [
        "row_count_diff",
        "missing_keys",
        "extra_keys",
        "null_source_keys",
        "null_target_keys",
        "duplicate_source_keys",
        "duplicate_target_keys",
        "total_revenue",
    ]
    assert checks_artifact["checks"][-1]["plan"]["operations"][-1] == {"type": "compare_aggregates"}


def test_plain_compile_does_not_require_profiles_when_project_selects_profile(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.diagnostics == ()
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_sql").exists()


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


def test_render_sql_compile_preserves_factory_diagnostics_when_adapter_is_returned(
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
        "RC_TEST_ADAPTER_WITH_DIAGNOSTIC",
        "RC_TEST_ADAPTER_WITH_DIAGNOSTIC",
    ]
    _assert_distinct_connection_diagnostic_messages(
        result.diagnostics,
        unscoped_message="Adapter factory returned an adapter with a setup diagnostic.",
    )
    _assert_render_sql_blocked_artifact(tmp_path, "RC_TEST_ADAPTER_WITH_DIAGNOSTIC")
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
            "Adapter `fake` does not declare a valid supported "
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
    public_output = yaml.safe_dump(
        {
            "service": [diagnostic.to_dict() for diagnostic in result.diagnostics],
            "artifact": checks_artifact,
        },
        sort_keys=False,
    )

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


def test_render_sql_compile_sanitizes_short_numeric_rendering_adapter_type(
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
    public_output = yaml.safe_dump(
        {
            "service": [diagnostic.to_dict() for diagnostic in result.diagnostics],
            "artifact": checks_artifact,
        },
        sort_keys=False,
    )

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert result.message == "SQL rendering failed."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "adapter diagnostic text was suppressed" in public_output
    assert "12" not in public_output
    assert {check["rendering"].get("adapter_type") for check in checks_artifact["checks"]} == {
        "short_numeric_adapter_type"
    }
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


def test_plain_compile_removes_stale_compiled_sql_artifacts(tmp_path: Path) -> None:
    write_project(tmp_path, profile="local")
    write_contract(tmp_path)
    write_profiles(tmp_path)
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory(dependency_available=lambda: True))

    render_result = CompileService(
        start_path=tmp_path,
        render_sql=True,
        adapter_registry=registry,
    ).execute()
    plain_result = CompileService(start_path=tmp_path).execute()

    checks_artifact = yaml.safe_load(
        (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert render_result.exit_category is ExitCategory.SUCCESS
    assert plain_result.exit_category is ExitCategory.SUCCESS
    assert not (tmp_path / "target" / "compiled_sql").exists()
    assert all(
        check["rendering"] == {"status": "not_rendered", "sql_paths": []}
        for check in checks_artifact["checks"]
    )


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
        "recon_core.services.compile.DuckDbSqlRenderer",
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
        "recon_core.services.compile.DuckDbSqlRenderer",
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
        "recon_core.services.compile.DuckDbSqlRenderer",
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
        "recon_core.services.compile.DuckDbSqlRenderer",
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


def test_render_sql_compile_sanitizes_render_phase_adapter_metadata(
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
    assert result.message == "SQL rendering failed."
    assert {diagnostic.code for diagnostic in result.diagnostics} == {
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    }
    assert "adapter diagnostic text was suppressed" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "super-secret" not in checks_artifact_text
    assert "password" not in diagnostic_text
    assert "password" not in checks_artifact_text
    assert all(
        check["rendering"]["adapter_type"] == "duckdb" for check in checks_artifact["checks"]
    )
    assert not (tmp_path / "target" / "compiled_sql").exists()


class FakeAdapter(BaseAdapter):
    adapter_type = "fake"
    adapter_version = "0.0.test"
    supported_adapter_api_version = "1"

    def connect(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError

    def execute(self, query: str) -> QueryResult:
        raise NotImplementedError

    def relation_exists(self, relation: Relation) -> bool:
        raise NotImplementedError

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        raise NotImplementedError

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({})


class FakeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=FakeAdapter(connection=connection))


class DiagnosticAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=FakeAdapter(connection=connection),
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_WITH_DIAGNOSTIC",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter factory returned an adapter with a setup diagnostic.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Fix the adapter factory setup diagnostic.",
                ),
            ),
        )


class ConnectionDiagnosticAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_CONNECTION_SETUP_FAILED",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Connection `{connection.name}` setup failed.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Fix the adapter setup failure.",
                ),
            )
        )


class LeakyApiAdapter(FakeAdapter):
    adapter_type = "password=super-secret"
    supported_adapter_api_version = "0"


class LeakyApiAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=LeakyApiAdapter(connection=connection))


class RaisingApiVersion:
    def __get__(self, instance: object, owner: object | None = None) -> str:
        raise AttributeError("password=super-secret")


class MissingApiVersionAdapter(FakeAdapter):
    supported_adapter_api_version = cast(str, RaisingApiVersion())


class MissingApiVersionAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=MissingApiVersionAdapter(connection=connection))


class NonStringAdapterTypeAdapter(FakeAdapter):
    adapter_type = cast(Any, 123)


class NonStringAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=NonStringAdapterTypeAdapter(connection=connection))


class RaisingAdapterType:
    def __get__(self, instance: object, owner: object | None = None) -> str:
        raise RuntimeError("password=super-secret")


class RaisingAdapterTypeAdapter(FakeAdapter):
    adapter_type = cast(str, RaisingAdapterType())


class RaisingAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=RaisingAdapterTypeAdapter(connection=connection))


class CapabilityRaisingDuckDbAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        raise ValueError(f"password={self.connection.config.get('password')}")


class CapabilityRaisingDuckDbAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=CapabilityRaisingDuckDbAdapter(connection=connection)
        )


class InvalidCapabilityDuckDbAdapter(FakeAdapter):
    adapter_type = "duckdb"

    def capabilities(self) -> AdapterCapabilities:
        invalid_support: dict[str, Any] = {
            "relations": CapabilitySupport.FULL,
            "row_count": "wat",
        }
        return AdapterCapabilities(invalid_support)


class InvalidCapabilityDuckDbAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=InvalidCapabilityDuckDbAdapter(connection=connection)
        )


class EmptyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult()


class InvalidResolutionAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return None  # type: ignore[return-value]


class MalformedDiagnosticsAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=cast(tuple[Diagnostic, ...], ("not-a-diagnostic",))
        )


class RaisingAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        raise ValueError(f"password={connection.config.get('password')}")


class LeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Connection database={connection.config.get('database')} "
                        f"password={connection.config.get('password')}"
                    ),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint=f"Do not leak database {connection.config.get('database')}.",
                ),
            )
        )


class NumericValueLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_NUMERIC_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=str(connection.config.get("password")),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class NumericFieldLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_NUMERIC_FIELD_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    line=int(str(connection.config.get("password"))),
                    column=int(str(connection.config.get("password"))),
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class ShortNumericFieldLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_SHORT_NUMERIC_FIELD_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter setup failed safely.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    line=int(str(connection.config.get("port"))),
                    column=int(str(connection.config.get("port"))),
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class ShortNumericTextLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        port = str(connection.config.get("port"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_SHORT_NUMERIC_TEXT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup failed at endpoint {port}.",
                    resource_type="adapter",
                    resource_name=port,
                    hint=f"Inspect endpoint {port}.",
                ),
            )
        )


class ShortNumericAdapterTypeAdapter(FakeAdapter):
    adapter_type = "12"


class ShortNumericAdapterTypeAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=ShortNumericAdapterTypeAdapter(connection=connection)
        )


class CaseVariantLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        database = str(connection.config.get("database"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_CASE_VARIANT_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=(f"PASSWORD={password.casefold()} DATABASE={database.upper()}"),
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint=f"Check DATABASE {database.upper()}.",
                ),
            )
        )


class ResourceTypeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_RESOURCE_TYPE_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter failed while resolving the selected connection.",
                    resource_type=f"PASSWORD={password.casefold()}",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class MessageAndResourceTypeLeakyAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_MESSAGE_AND_RESOURCE_TYPE_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter failed with password={password.casefold()}.",
                    resource_type=f"PASSWORD={password.casefold()}",
                    resource_name=connection.type,
                    hint="Inspect the adapter configuration.",
                ),
            )
        )


class LeakyRenderPhaseAdapter(FakeAdapter):
    adapter_type = "password=super-secret"


class LeakyRenderPhaseAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(adapter=LeakyRenderPhaseAdapter(connection=connection))


def test_compile_service_ignores_indexed_non_contract_files_for_compiled_output(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    (tmp_path / "check_packs").mkdir()
    (tmp_path / "sample_policies").mkdir()
    (tmp_path / "tolerances").mkdir()
    (tmp_path / "schema_policies").mkdir()
    (tmp_path / "macros").mkdir()
    (tmp_path / "check_packs" / "company.yml").write_text(
        "this is not valid: [\n",
        encoding="utf-8",
    )
    (tmp_path / "sample_policies" / "stable.yml").write_text(
        "name: stable\n",
        encoding="utf-8",
    )
    (tmp_path / "tolerances" / "default.yml").write_text(
        "name: default\n",
        encoding="utf-8",
    )
    (tmp_path / "schema_policies" / "cdc.yml").write_text(
        "name: cdc\n",
        encoding="utf-8",
    )
    (tmp_path / "macros" / "normalize.sql").write_text(
        "lower(trim({{ column }}))\n",
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.SUCCESS
    assert result.diagnostics == ()
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_contracts" / "company.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "company.yml").exists()
    assert not (tmp_path / "target" / "compiled_sql").exists()


def test_compile_service_removes_stale_artifacts_for_explicit_missing_resource_path(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

    write_project(tmp_path, check_pack_paths=("custom_packs",))

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_PARSE_RESOURCE_PATH_NOT_FOUND"
    ]
    assert second_result.diagnostics[0].resource_type == "check_pack_path"
    assert second_result.diagnostics[0].path == str(tmp_path / "custom_packs")
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_overwrites_previous_compiled_artifacts(tmp_path: Path) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()
    second_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert second_result.exit_category is ExitCategory.SUCCESS


def test_compile_service_removes_stale_compiled_artifacts_for_removed_contract(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, name="customer_revenue", file_name="customer_revenue.yml")
    write_contract(tmp_path, name="orders_revenue", file_name="orders_revenue.yml")

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_contracts" / "orders_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "orders_revenue.yml").is_file()

    (tmp_path / "contracts" / "orders_revenue.yml").unlink()

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_contracts" / "orders_revenue.yml").exists()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()
    assert not (tmp_path / "target" / "compiled_checks" / "orders_revenue.yml").exists()


def test_compile_service_returns_validation_error_for_invalid_contract(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, include_grain=False)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == (
        "Compile completed with 1 diagnostic. Wrote compiled artifacts for 1 contract."
    )
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    ]

    checks_path = tmp_path / "target" / "compiled_checks" / "customer_revenue.yml"
    checks_artifact = yaml.safe_load(checks_path.read_text(encoding="utf-8"))
    assert checks_artifact["checks"] == []
    assert checks_artifact["diagnostics"][0]["code"] == (
        "RC_VALIDATE_CHECK_PACK_REQUIRES_GRAIN_KEYS"
    )


def test_compile_service_writes_no_artifacts_when_parse_fails(tmp_path: Path) -> None:
    write_project(tmp_path)
    contract_path = tmp_path / "contracts" / "customer_revenue.yml"
    contract_path.write_text(
        """
version: 1
name: customer_revenue
source:
  connection: legacy
  relation: qa.customer_source
target:
  connection: warehouse
  relation: qa.customer_target
""".lstrip(),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_writes_no_artifacts_when_no_contracts_are_found(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_NO_CONTRACTS_FOUND"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_removes_stale_compiled_artifacts_when_parse_fails(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

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
""".lstrip(),
        encoding="utf-8",
    )

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed during project parsing."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_PARSE_MISSING_REQUIRED_FIELD"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_rejects_symlinked_compiled_artifact_directories(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external"
    external_path.mkdir()
    external_artifact = external_path / "stale.yml"
    external_artifact.write_text("stale\n", encoding="utf-8")
    target_path.mkdir()
    try:
        (target_path / "compiled_contracts").symlink_to(
            external_path,
            target_is_directory=True,
        )
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert external_artifact.read_text(encoding="utf-8") == "stale\n"


def test_compile_service_rejects_symlinked_target_directory_before_cleanup(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    target_path = tmp_path / "target"
    external_path = tmp_path / "external_target"
    external_contracts = external_path / "compiled_contracts"
    external_checks = external_path / "compiled_checks"
    external_contracts.mkdir(parents=True)
    external_checks.mkdir(parents=True)
    external_contract_artifact = external_contracts / "customer_revenue.yml"
    external_check_artifact = external_checks / "customer_revenue.yml"
    external_contract_artifact.write_text("stale contract\n", encoding="utf-8")
    external_check_artifact.write_text("stale checks\n", encoding="utf-8")
    try:
        target_path.symlink_to(external_path, target_is_directory=True)
    except OSError:
        pytest.skip("Filesystem does not support directory symlinks.")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert "symlink" in result.diagnostics[0].message
    assert external_contract_artifact.read_text(encoding="utf-8") == "stale contract\n"
    assert external_check_artifact.read_text(encoding="utf-8") == "stale checks\n"


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


def test_compile_service_writes_no_artifacts_for_invalid_stable_id_parts(
    tmp_path: Path,
) -> None:
    write_project(tmp_path, project_name="ecommerce-recon")
    write_contract(tmp_path)

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_INVALID_STABLE_ID_PART"
    ]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_removes_stale_compiled_artifacts_for_fatal_compile_validation(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)

    first_result = CompileService(start_path=tmp_path).execute()

    assert first_result.exit_category is ExitCategory.SUCCESS
    assert (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").is_file()
    assert (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").is_file()

    tmp_path.joinpath("recon_project.yml").write_text(
        """
name: ecommerce-recon
version: 0.1.0
config-version: 1
contract-paths:
  - contracts
target-path: target
""".lstrip(),
        encoding="utf-8",
    )

    second_result = CompileService(start_path=tmp_path).execute()

    assert second_result.exit_category is ExitCategory.VALIDATION_ERROR
    assert second_result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in second_result.diagnostics] == [
        "RC_VALIDATE_INVALID_STABLE_ID_PART"
    ]
    assert not (tmp_path / "target" / "compiled_contracts" / "customer_revenue.yml").exists()
    assert not (tmp_path / "target" / "compiled_checks" / "customer_revenue.yml").exists()


def test_compile_service_writes_no_artifacts_for_duplicate_contract_names(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    tmp_path.joinpath("contracts", "duplicate.yml").write_text(
        tmp_path.joinpath("contracts", "customer_revenue.yml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_DUPLICATE_CONTRACT"]
    assert result.diagnostics[0].path == "contracts/duplicate.yml"
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_writes_no_artifacts_for_case_colliding_artifact_names(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path, name="Sales", file_name="sales_upper.yml")
    write_contract(tmp_path, name="sales", file_name="sales_lower.yml")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert result.message == "Compile failed with 1 diagnostic. Wrote no compiled artifacts."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_VALIDATE_COMPILED_ARTIFACT_FILENAME_COLLISION"
    ]
    assert result.diagnostics[0].path in {
        "contracts/sales_lower.yml",
        "contracts/sales_upper.yml",
    }
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_returns_validation_error_for_non_string_check_mapping_key(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
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
grain:
  keys:
    - customer_id
checks:
  use:
    - recon_core.basic_equivalence
  1: true
""".lstrip(),
        encoding="utf-8",
    )

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.VALIDATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_PARSE_INVALID_CONTRACT"]
    assert "string keys" in result.diagnostics[0].message
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def test_compile_service_returns_runtime_error_when_artifacts_cannot_be_written(
    tmp_path: Path,
) -> None:
    write_project(tmp_path)
    write_contract(tmp_path)
    tmp_path.joinpath("target").write_text("not a directory\n", encoding="utf-8")

    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.RUNTIME_ERROR
    assert result.message == "Compile completed but artifacts could not be written."
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_RUNTIME_COMPILED_ARTIFACT_WRITE_FAILED"
    ]
    assert result.diagnostics[0].path == "target"


def test_compile_service_writes_no_artifacts_when_project_root_is_missing(
    tmp_path: Path,
) -> None:
    result = CompileService(start_path=tmp_path).execute()

    assert result.exit_category is ExitCategory.CONFIGURATION_ERROR
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_CONFIG_PROJECT_NOT_FOUND"]
    assert not (tmp_path / "target" / "compiled_contracts").exists()
    assert not (tmp_path / "target" / "compiled_checks").exists()


def write_project(
    project_root: Path,
    *,
    project_name: str = "ecommerce_recon",
    check_pack_paths: tuple[str, ...] | None = None,
    profile: str | None = None,
) -> None:
    check_pack_paths_yaml = _path_list_yaml("check-pack-paths", check_pack_paths)
    profile_yaml = f"profile: {profile}\n" if profile is not None else ""
    project_root.joinpath("contracts").mkdir(exist_ok=True)
    project_root.joinpath("recon_project.yml").write_text(
        f"""
name: {project_name}
version: 0.1.0
config-version: 1
{profile_yaml}
contract-paths:
  - contracts
{check_pack_paths_yaml}
target-path: target
""".lstrip(),
        encoding="utf-8",
    )


def write_profiles(
    project_root: Path,
    *,
    connection_type: str = "duckdb",
    use_distinct_databases: bool = False,
    include_password: bool = False,
    password: str = "super-secret",
    port: int | None = None,
) -> None:
    legacy_database = "legacy.duckdb" if use_distinct_databases else "local.duckdb"
    warehouse_database = "warehouse.duckdb" if use_distinct_databases else "local.duckdb"
    password_yaml = f"            password: {password}\n" if include_password else ""
    port_yaml = f"            port: {port}\n" if port is not None else ""
    profiles_path = project_root / "connections" / "profiles.yml"
    profiles_path.parent.mkdir()
    profiles_path.write_text(
        f"""
profiles:
  local:
    target: dev
    outputs:
      dev:
        connections:
          legacy:
            type: {connection_type}
            database: {legacy_database}
{password_yaml.rstrip()}
{port_yaml.rstrip()}
          warehouse:
            type: {connection_type}
            database: {warehouse_database}
{password_yaml.rstrip()}
{port_yaml.rstrip()}
""".lstrip(),
        encoding="utf-8",
    )


def _assert_render_sql_blocked_artifact(project_root: Path, diagnostic_code: str) -> None:
    checks_artifact = yaml.safe_load(
        (project_root / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )

    assert all(check["rendering"]["status"] == "blocked" for check in checks_artifact["checks"])
    assert all(check["rendering"]["sql_paths"] == [] for check in checks_artifact["checks"])
    assert {
        diagnostic["code"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    } == {diagnostic_code}


def _assert_distinct_connection_diagnostic_messages(
    diagnostics: tuple[Diagnostic, ...],
    *,
    unscoped_message: str,
) -> None:
    assert {diagnostic.message for diagnostic in diagnostics} == {
        f"Connection `legacy`: {unscoped_message}",
        f"Connection `warehouse`: {unscoped_message}",
    }


def _assert_blocked_artifact_includes_messages(
    project_root: Path,
    expected_messages: set[str],
) -> None:
    checks_artifact = yaml.safe_load(
        (project_root / "target" / "compiled_checks" / "customer_revenue.yml").read_text(
            encoding="utf-8"
        )
    )
    artifact_messages = {
        diagnostic["message"]
        for check in checks_artifact["checks"]
        for diagnostic in check["diagnostics"]
    }

    assert expected_messages <= artifact_messages


def _path_list_yaml(field_name: str, paths: tuple[str, ...] | None) -> str:
    if paths is None:
        return ""
    path_items = "\n".join(f"  - {path}" for path in paths)
    return f"{field_name}:\n{path_items}"


def write_contract(
    project_root: Path,
    *,
    name: str = "customer_revenue",
    file_name: str = "customer_revenue.yml",
    include_grain: bool = True,
    tolerance_policy: str | None = None,
    nulls: dict[str, object] | None = None,
    source_query: str | None = None,
) -> None:
    grain_yaml = (
        """
grain:
  keys:
    - customer_id
    - month
"""
        if include_grain
        else ""
    )
    tolerance_policy_yaml = (
        yaml.safe_dump({"tolerance_policy": tolerance_policy}, sort_keys=False)
        if tolerance_policy is not None
        else ""
    )
    nulls_yaml = yaml.safe_dump({"nulls": nulls}, sort_keys=False) if nulls is not None else ""
    source_endpoint_yaml = (
        f"  query: {source_query}\n"
        if source_query is not None
        else "  relation: qa.customer_source\n"
    )
    project_root.joinpath("contracts", file_name).write_text(
        f"""
version: 1
name: {name}
source:
  connection: legacy
{source_endpoint_yaml}target:
  connection: warehouse
  relation: qa.customer_target
{grain_yaml}metrics:
  - name: total_revenue
    type: sum
    column: revenue
checks:
  use:
    - recon_core.basic_equivalence
sampling:
  default_policy: full
{tolerance_policy_yaml}{nulls_yaml}
""".lstrip(),
        encoding="utf-8",
    )
