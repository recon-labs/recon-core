from typing import Any, cast

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    AdapterRegistry,
    AdapterResolutionResult,
    BaseAdapter,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
    validate_adapter_api_compatibility,
)
from recon_core.diagnostics import Diagnostic


class CompatibleAdapter(BaseAdapter):
    adapter_type = "compatible"
    adapter_version = "0.1.0"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        return QueryResult(columns=(), rows=(), row_count=0)

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({})


class IncompatibleAdapter(CompatibleAdapter):
    supported_adapter_api_version = "0.0"


class EmptyFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult()


class RaisingFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        raise ValueError(f"password={connection.config.get('password')}")


class InvalidResolutionFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return None  # type: ignore[return-value]


class MalformedDiagnosticsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=cast(tuple[Diagnostic, ...], ("not-a-diagnostic",))
        )


class MalformedDiagnosticFieldsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_MALFORMED_DIAGNOSTIC_FIELD",
                    severity=cast(Any, "error"),
                    message="Malformed diagnostic field.",
                ),
            )
        )


class NoneDiagnosticsWithAdapterFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=CompatibleAdapter(connection=connection),
            diagnostics=cast(tuple[Diagnostic, ...], None),
        )


class RaisingApiVersion:
    def __get__(self, instance: object, owner: object | None = None) -> str:
        raise AttributeError("password=super-secret")


class MissingApiVersionAdapter(CompatibleAdapter):
    supported_adapter_api_version = cast(str, RaisingApiVersion())


def test_adapter_api_compatibility_passes_for_current_api_version() -> None:
    adapter = CompatibleAdapter(connection=ConnectionConfig(name="source", type="compatible"))

    assert validate_adapter_api_compatibility(adapter) == ()


def test_adapter_api_compatibility_fails_for_unsupported_api_version() -> None:
    adapter = IncompatibleAdapter(connection=ConnectionConfig(name="source", type="compatible"))

    diagnostics = validate_adapter_api_compatibility(adapter)

    assert [diagnostic.code for diagnostic in diagnostics] == ["RC_ADAPTER_API_VERSION_UNSUPPORTED"]
    assert "0.0" in diagnostics[0].message
    assert ADAPTER_API_VERSION in diagnostics[0].message


def test_adapter_api_compatibility_reports_missing_version_without_raw_error() -> None:
    adapter = MissingApiVersionAdapter(
        connection=ConnectionConfig(
            name="source",
            type="compatible",
            config={"password": "super-secret"},
        )
    )

    diagnostics = validate_adapter_api_compatibility(adapter)
    diagnostic_text = f"{diagnostics[0].message} {diagnostics[0].hint}"

    assert [diagnostic.code for diagnostic in diagnostics] == ["RC_ADAPTER_API_VERSION_UNSUPPORTED"]
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_registry_resolves_registered_adapter() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", CompatibleAdapter)

    result = registry.resolve(ConnectionConfig(name="source", type="compatible"))

    assert result.succeeded
    assert isinstance(result.adapter, CompatibleAdapter)
    assert result.diagnostics == ()


def test_registry_reports_unknown_adapter_type() -> None:
    result = AdapterRegistry().resolve(ConnectionConfig(name="source", type="missing"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_ADAPTER_UNKNOWN_TYPE"]
    assert result.diagnostics[0].resource_name == "missing"


def test_registry_reports_empty_adapter_resolution_result() -> None:
    registry = AdapterRegistry()
    registry.register("empty", EmptyFactory())

    result = registry.resolve(ConnectionConfig(name="source", type="empty"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "empty"


def test_registry_reports_invalid_adapter_resolution_result() -> None:
    registry = AdapterRegistry()
    registry.register("invalid", InvalidResolutionFactory())

    result = registry.resolve(ConnectionConfig(name="source", type="invalid"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "invalid"


def test_registry_reports_malformed_adapter_resolution_diagnostics() -> None:
    registry = AdapterRegistry()
    registry.register("malformed", MalformedDiagnosticsFactory())

    result = registry.resolve(ConnectionConfig(name="source", type="malformed"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "malformed"


def test_registry_reports_malformed_adapter_resolution_diagnostic_fields() -> None:
    registry = AdapterRegistry()
    registry.register("malformed_fields", MalformedDiagnosticFieldsFactory())

    result = registry.resolve(ConnectionConfig(name="source", type="malformed_fields"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "malformed_fields"


def test_registry_reports_none_diagnostics_with_adapter() -> None:
    registry = AdapterRegistry()
    registry.register("none_diagnostics", NoneDiagnosticsWithAdapterFactory())

    result = registry.resolve(ConnectionConfig(name="source", type="none_diagnostics"))

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "none_diagnostics"


def test_registry_sanitizes_adapter_factory_exceptions() -> None:
    registry = AdapterRegistry()
    registry.register("raising", RaisingFactory())

    result = registry.resolve(
        ConnectionConfig(
            name="warehouse",
            type="raising",
            config={"password": "super-secret"},
        )
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_type == "adapter"
    assert result.diagnostics[0].resource_name == "raising"
    assert "ValueError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text
