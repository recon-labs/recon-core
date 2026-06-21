"""DuckDB adapter foundation."""

from recon_core.adapters.duckdb.adapter import (
    ADAPTER_DEPENDENCY_MISSING,
    AdapterLifecycleError,
    DuckDbAdapter,
    DuckDbAdapterFactory,
)
from recon_core.adapters.duckdb.renderer import DuckDbSqlRenderer
from recon_core.adapters.lifecycle import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
)

__all__ = [
    "ADAPTER_CLOSE_FAILED",
    "ADAPTER_CONNECTION_FAILED",
    "ADAPTER_DEPENDENCY_MISSING",
    "ADAPTER_QUERY_FAILED",
    "AdapterLifecycleError",
    "DuckDbAdapter",
    "DuckDbAdapterFactory",
    "DuckDbSqlRenderer",
]
