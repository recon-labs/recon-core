"""Built-in runtime SQL renderer construction."""

from recon_core.adapters._aggregate_runtime import _AggregateRuntimeRenderer
from recon_core.adapters.base import SqlRenderer


def default_runtime_renderers_by_adapter_type() -> dict[str, SqlRenderer]:
    """Return built-in SQL renderers for current runtime execution."""
    from recon_core.adapters.duckdb import DuckDbSqlRenderer

    return {"duckdb": DuckDbSqlRenderer()}


def _default_aggregate_runtime_renderers() -> dict[str, _AggregateRuntimeRenderer]:
    """Construct private bounded runtime renderers without changing compile rendering."""
    from recon_core.adapters.duckdb._aggregate_runtime import _DuckDbAggregateRuntimeRenderer

    return {"duckdb": _DuckDbAggregateRuntimeRenderer()}
