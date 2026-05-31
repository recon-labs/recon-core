"""Adapter interfaces and registry."""

from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import (
    ADAPTER_CAPABILITY_UNSUPPORTED,
    AdapterCapabilities,
    CapabilitySupport,
    validate_required_capabilities,
)
from recon_core.adapters.duckdb import DuckDbAdapterFactory
from recon_core.adapters.models import (
    ADAPTER_API_VERSION,
    AdapterResolutionResult,
    ColumnMetadata,
    QueryResult,
    Relation,
    RenderedSql,
)
from recon_core.adapters.registry import (
    ADAPTER_API_VERSION_UNSUPPORTED,
    ADAPTER_UNKNOWN_TYPE,
    AdapterFactory,
    AdapterRegistry,
    validate_adapter_api_compatibility,
)
from recon_core.adapters.rendering import (
    ADAPTER_INVALID_RELATION,
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
    RenderedCheckSql,
    render_check_sql,
)
from recon_core.profiles import ConnectionConfig


def default_adapter_registry() -> AdapterRegistry:
    """Return the built-in adapter registry."""
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory())
    return registry


__all__ = [
    "ADAPTER_API_VERSION",
    "ADAPTER_API_VERSION_UNSUPPORTED",
    "ADAPTER_CAPABILITY_UNSUPPORTED",
    "ADAPTER_INVALID_RELATION",
    "ADAPTER_OPERATION_RENDER_FAILED",
    "ADAPTER_QUERY_ENDPOINT_UNSUPPORTED",
    "ADAPTER_UNKNOWN_TYPE",
    "AdapterCapabilities",
    "AdapterFactory",
    "AdapterRegistry",
    "AdapterResolutionResult",
    "BaseAdapter",
    "CapabilitySupport",
    "ColumnMetadata",
    "ConnectionConfig",
    "QueryResult",
    "Relation",
    "RenderedSql",
    "RenderedCheckSql",
    "SqlRenderer",
    "default_adapter_registry",
    "render_check_sql",
    "validate_adapter_api_compatibility",
    "validate_required_capabilities",
]
