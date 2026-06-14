"""DuckDB adapter foundation."""

from recon_core.adapters.duckdb.adapter import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_DEPENDENCY_MISSING,
    ADAPTER_QUERY_FAILED,
    AdapterLifecycleError,
    DuckDbAdapter,
    DuckDbAdapterFactory,
    DuckDbSqlRenderer,
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
