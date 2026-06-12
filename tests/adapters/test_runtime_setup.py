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
