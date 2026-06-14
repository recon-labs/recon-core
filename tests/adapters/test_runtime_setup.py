from typing import cast

from recon_core.adapters import (
    ADAPTER_API_VERSION,
    AdapterCapabilities,
    AdapterRegistry,
    AdapterResolutionResult,
    BaseAdapter,
    CapabilitySupport,
    ColumnMetadata,
    ConnectionConfig,
    QueryResult,
    Relation,
)
from recon_core.adapters.runtime_setup import prepare_runtime_adapter
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


class CompatibleAdapter(BaseAdapter):
    adapter_type = "compatible"
    adapter_version = "0.1.0"
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(self, *, connection: ConnectionConfig) -> None:
        super().__init__(connection=connection)
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        pass

    def execute(self, query: str) -> QueryResult:
        return QueryResult(columns=(), rows=(), row_count=0)

    def relation_exists(self, relation: Relation) -> bool:
        return False

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        return ()

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "row_count": CapabilitySupport.FULL,
                "cte_support": CapabilitySupport.FULL,
            }
        )


class IncompatibleApiAdapter(CompatibleAdapter):
    supported_adapter_api_version = "0.0"


class MismatchedAdapterTypeAdapter(CompatibleAdapter):
    adapter_type = "actual"


class MetadataRaisingAdapter(CompatibleAdapter):
    @property  # type: ignore[override]
    def adapter_type(self) -> str:
        raise RuntimeError(f"password={self.connection.config.get('password')}")


class MissingCapabilityAdapter(CompatibleAdapter):
    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities({"row_count": CapabilitySupport.FULL})


class CapabilityRaisingAdapter(CompatibleAdapter):
    def capabilities(self) -> AdapterCapabilities:
        raise RuntimeError(f"password={self.connection.config.get('password')}")


class EmptyFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult()


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


class LeakyDiagnosticsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        database = str(connection.config.get("database"))
        password = str(connection.config.get("password"))
        port = int(str(connection.config.get("port")))
        token = str(connection.config.get("token"))
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code=f"RC{password}LEAK",
                    severity=DiagnosticSeverity.ERROR,
                    message=(
                        f"Adapter failed with PASSWORD={password.casefold()} "
                        f"database={database.upper()} token={token}."
                    ),
                    resource_type=f"PASSWORD={password.casefold()}",
                    resource_name=f"endpoint-{port}",
                    path=f"adapter://endpoint/{port}/{token}",
                    line=port,
                    column=port,
                    hint=f"Inspect DSN {database}.",
                ),
            )
        )


class SafeDiagnosticsFactory:
    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        return AdapterResolutionResult(
            diagnostics=(
                Diagnostic(
                    code="RC_ADAPTER_CAPABILITY_UNSUPPORTED",
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter does not support the required capability.",
                    resource_type="adapter",
                    resource_name=connection.type,
                    hint="Use an adapter that supports this capability.",
                ),
            )
        )


def test_prepare_runtime_adapter_validates_without_connecting() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", CompatibleAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="compatible"),
        required_capabilities=("row_count", "cte_support"),
        registry=registry,
    )

    assert result.succeeded
    assert isinstance(result.adapter, CompatibleAdapter)
    assert result.adapter_type == "compatible"
    assert result.capabilities is not None
    assert result.capabilities.support_for("row_count") is CapabilitySupport.FULL
    assert not result.adapter.connected
    assert result.diagnostics == ()


def test_prepare_runtime_adapter_reports_unknown_adapter_type() -> None:
    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="missing"),
        required_capabilities=("row_count",),
        registry=AdapterRegistry(),
    )

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_ADAPTER_UNKNOWN_TYPE"]


def test_prepare_runtime_adapter_reports_invalid_factory_result() -> None:
    registry = AdapterRegistry()
    registry.register("empty", EmptyFactory())

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="empty"),
        required_capabilities=("row_count",),
        registry=registry,
    )

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]


def test_prepare_runtime_adapter_rejects_adapter_plus_diagnostics_result() -> None:
    registry = AdapterRegistry()
    registry.register("leaky", AdapterWithDiagnosticsFactory())

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="leaky",
            config={"password": "super-secret"},
        ),
        required_capabilities=("row_count",),
        registry=registry,
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_RESOLUTION_FAILED"
    ]
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_prepare_runtime_adapter_sanitizes_factory_diagnostics() -> None:
    registry = AdapterRegistry()
    registry.register("leaky", LeakyDiagnosticsFactory())

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="leaky",
            config={
                "database": "duckdb://admin:super-secret@warehouse.local:12/app?token=abc123",
                "password": "super-secret",
                "port": 12,
                "token": "abc123",
            },
        ),
        required_capabilities=("row_count",),
        registry=registry,
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
    assert "adapter diagnostic text was suppressed" in diagnostic.message
    assert "super-secret" not in public_text
    assert "password" not in public_text.casefold()
    assert "warehouse.local" not in public_text
    assert "abc123" not in public_text
    assert "duckdb://" not in public_text
    assert "\n12\n" not in f"\n{public_text}\n"


def test_prepare_runtime_adapter_preserves_safe_factory_diagnostic_code() -> None:
    registry = AdapterRegistry()
    registry.register("safe", SafeDiagnosticsFactory())

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="safe",
            config={"password": "super-secret"},
        ),
        required_capabilities=("row_count",),
        registry=registry,
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_prepare_runtime_adapter_reports_adapter_type_mismatch() -> None:
    registry = AdapterRegistry()
    registry.register("profile_type", MismatchedAdapterTypeAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="profile_type"),
        required_capabilities=("row_count",),
        registry=registry,
    )

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_ADAPTER_TYPE_MISMATCH"]


def test_prepare_runtime_adapter_reports_metadata_failure_without_raw_error() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", MetadataRaisingAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="compatible",
            config={"password": "super-secret"},
        ),
        required_capabilities=("row_count",),
        registry=registry,
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_ADAPTER_METADATA_INVALID"]
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_prepare_runtime_adapter_reports_api_version_mismatch() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", IncompatibleApiAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="compatible"),
        required_capabilities=("row_count",),
        registry=registry,
    )

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_API_VERSION_UNSUPPORTED"
    ]


def test_prepare_runtime_adapter_reports_missing_required_capability() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", MissingCapabilityAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="compatible"),
        required_capabilities=("row_count", "cte_support"),
        registry=registry,
    )

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "cte_support" in result.diagnostics[0].message


def test_prepare_runtime_adapter_sanitizes_capability_declaration_exception() -> None:
    registry = AdapterRegistry()
    registry.register("compatible", CapabilityRaisingAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(
            name="warehouse",
            type="compatible",
            config={"password": "super-secret"},
        ),
        required_capabilities=("row_count",),
        registry=registry,
    )

    diagnostic_text = f"{result.diagnostics[0].message} {result.diagnostics[0].hint}"

    assert not result.succeeded
    assert result.adapter is None
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_DECLARATION_FAILED"
    ]
    assert "RuntimeError" in diagnostic_text
    assert "super-secret" not in diagnostic_text
    assert "password" not in diagnostic_text


def test_prepare_runtime_adapter_treats_malformed_capability_state_as_unsupported() -> None:
    class MalformedCapabilityAdapter(CompatibleAdapter):
        def capabilities(self) -> AdapterCapabilities:
            return AdapterCapabilities({"row_count": cast(CapabilitySupport, "wat")})

    registry = AdapterRegistry()
    registry.register("compatible", MalformedCapabilityAdapter)

    result = prepare_runtime_adapter(
        connection=ConnectionConfig(name="warehouse", type="compatible"),
        required_capabilities=("row_count",),
        registry=registry,
    )

    assert not result.succeeded
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        "RC_ADAPTER_CAPABILITY_UNSUPPORTED"
    ]
    assert "invalid support state" in result.diagnostics[0].message
