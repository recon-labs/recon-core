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


def test_adapter_api_compatibility_passes_for_current_api_version() -> None:
    adapter = CompatibleAdapter(connection=ConnectionConfig(name="source", type="compatible"))

    assert validate_adapter_api_compatibility(adapter) == ()


def test_adapter_api_compatibility_fails_for_unsupported_api_version() -> None:
    adapter = IncompatibleAdapter(connection=ConnectionConfig(name="source", type="compatible"))

    diagnostics = validate_adapter_api_compatibility(adapter)

    assert [diagnostic.code for diagnostic in diagnostics] == ["RC_ADAPTER_API_VERSION_UNSUPPORTED"]
    assert "0.0" in diagnostics[0].message
    assert ADAPTER_API_VERSION in diagnostics[0].message


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
