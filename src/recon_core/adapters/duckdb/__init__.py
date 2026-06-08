"""DuckDB adapter foundation."""

from recon_core.adapters.duckdb.adapter import (
    ADAPTER_DEPENDENCY_MISSING,
    DuckDbAdapter,
    DuckDbAdapterFactory,
    DuckDbSqlRenderer,
)

__all__ = [
    "ADAPTER_DEPENDENCY_MISSING",
    "DuckDbAdapter",
    "DuckDbAdapterFactory",
    "DuckDbSqlRenderer",
]
