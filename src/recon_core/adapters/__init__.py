"""Adapter interfaces and registry."""

from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import (
    ADAPTER_CAPABILITY_UNSUPPORTED,
    AdapterCapabilities,
    CapabilitySupport,
    validate_required_capabilities,
)
from recon_core.adapters.diagnostic_redaction import ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED
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
    ADAPTER_METADATA_INVALID,
    ADAPTER_RESOLUTION_FAILED,
    ADAPTER_UNKNOWN_TYPE,
    AdapterFactory,
    AdapterRegistry,
    validate_adapter_api_compatibility,
)
from recon_core.adapters.rendering import (
    ADAPTER_CAPABILITY_DECLARATION_FAILED,
    ADAPTER_INVALID_RELATION,
    ADAPTER_OPERATION_RENDER_FAILED,
    ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
    ADAPTER_RENDERED_SQL_EMPTY,
    ADAPTER_RENDERER_METADATA_INVALID,
    ADAPTER_RENDERER_TYPE_MISMATCH,
    RenderedCheckSql,
    render_check_sql,
)
from recon_core.adapters.runtime_setup import (
    ADAPTER_TYPE_MISMATCH,
    RuntimeAdapterSetupResult,
    prepare_runtime_adapter,
)
from recon_core.profiles import ConnectionConfig


def default_adapter_registry() -> AdapterRegistry:
    """Return the built-in adapter registry without importing concrete adapters eagerly."""
    from recon_core.adapters.default_registry import default_adapter_registry as _default_registry

    return _default_registry()


__all__ = [
    "ADAPTER_API_VERSION",
    "ADAPTER_API_VERSION_UNSUPPORTED",
    "ADAPTER_CAPABILITY_DECLARATION_FAILED",
    "ADAPTER_CAPABILITY_UNSUPPORTED",
    "ADAPTER_DIAGNOSTIC_CODE_SUPPRESSED",
    "ADAPTER_METADATA_INVALID",
    "ADAPTER_RESOLUTION_FAILED",
    "ADAPTER_INVALID_RELATION",
    "ADAPTER_OPERATION_RENDER_FAILED",
    "ADAPTER_QUERY_ENDPOINT_UNSUPPORTED",
    "ADAPTER_RENDERED_SQL_EMPTY",
    "ADAPTER_RENDERER_METADATA_INVALID",
    "ADAPTER_RENDERER_TYPE_MISMATCH",
    "ADAPTER_TYPE_MISMATCH",
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
    "RuntimeAdapterSetupResult",
    "default_adapter_registry",
    "prepare_runtime_adapter",
    "render_check_sql",
    "validate_adapter_api_compatibility",
    "validate_required_capabilities",
]
