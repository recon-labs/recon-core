"""Built-in adapter registry construction."""

from recon_core.adapters.duckdb import DuckDbAdapterFactory
from recon_core.adapters.registry import AdapterRegistry


def default_adapter_registry() -> AdapterRegistry:
    """Return the built-in adapter registry."""
    registry = AdapterRegistry()
    registry.register("duckdb", DuckDbAdapterFactory())
    return registry
