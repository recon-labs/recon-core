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
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


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


class AdapterWithDiagnosticsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            adapter=CompatibleAdapter(connection=connection),
            diagnostics=(
                Diagnostic(
                    code="RC_TEST_ADAPTER_LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"password={connection.config.get('password')}",
                    resource_type="adapter",
                    resource_name=connection.type,
                ),
            ),
        )


class LeakyResolutionDiagnosticsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        password = str(connection.config.get("password"))
        port = int(str(connection.config.get("port")))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=f"RC{password}LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=f"Adapter setup leaked password={password} on port {port}.",
                    resource_type=f"password={password}",
                    resource_name=str(port),
                    path=f"adapter://{port}/{password}",
                    line=port,
                    column=port,
                    hint=f"Inspect password={password}.",
                ),
            ),
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


def test_registry_reports_adapter_with_diagnostics_result_as_invalid() -> None:
    registry = AdapterRegistry()
    registry.register("adapter_and_diagnostics", AdapterWithDiagnosticsFactory())

    result = registry.resolve(
        ConnectionConfig(
            name="source",
            type="adapter_and_diagnostics",
            config={"password": "super-secret"},
        )
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert result.diagnostics[0].resource_name == "adapter_and_diagnostics"
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_registry_sanitizes_adapter_resolution_diagnostics() -> None:
    registry = AdapterRegistry()
    registry.register("leaky", LeakyResolutionDiagnosticsFactory())

    result = registry.resolve(
        ConnectionConfig(
            name="source",
            type="leaky",
            config={"password": "super-secret", "port": 12},
        )
    )

    diagnostic = result.diagnostics[0]
    public_text = "\n".join(
        str(value)
        for value in (
            diagnostic.code,
            diagnostic.message,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.hint,
        )
        if value is not None
    )

    assert not result.succeeded
    assert result.adapter is None
    assert diagnostic.code == "RC_ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED"
    assert diagnostic.resource_type == "adapter"
    assert diagnostic.resource_name == "leaky"
    assert diagnostic.path is None
    assert diagnostic.line is None
    assert diagnostic.column is None
    assert "super-secret" not in public_text
    assert "password" not in public_text.casefold()
    assert "\n12\n" not in f"\n{public_text}\n"


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
