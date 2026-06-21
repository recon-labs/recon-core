"""Built-in runtime SQL renderer construction."""

from recon_core.adapters.base import SqlRenderer


def default_runtime_renderers_by_adapter_type() -> dict[str, SqlRenderer]:
    """Return built-in SQL renderers for current runtime execution."""
    from recon_core.adapters.duckdb import DuckDbSqlRenderer

    return {"duckdb": DuckDbSqlRenderer()}
