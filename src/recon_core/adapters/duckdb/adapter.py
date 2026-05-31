"""DuckDB local development adapter foundation."""

from collections.abc import Callable, Mapping
from importlib.util import find_spec
from typing import Any

from recon_core._version import get_version
from recon_core.adapters.base import BaseAdapter, SqlRenderer
from recon_core.adapters.capabilities import AdapterCapabilities, CapabilitySupport
from recon_core.adapters.models import (
    ADAPTER_API_VERSION,
    AdapterResolutionResult,
    ColumnMetadata,
    QueryResult,
    Relation,
    RenderedSql,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

ADAPTER_DEPENDENCY_MISSING = "RC_ADAPTER_DEPENDENCY_MISSING"


class DuckDbAdapter(BaseAdapter):
    """DuckDB local development adapter shell."""

    adapter_type = "duckdb"
    adapter_version = get_version()
    supported_adapter_api_version = ADAPTER_API_VERSION

    def connect(self) -> None:
        raise NotImplementedError("DuckDB connection lifecycle is implemented in a later phase.")

    def close(self) -> None:
        raise NotImplementedError("DuckDB connection lifecycle is implemented in a later phase.")

    def execute(self, query: str) -> QueryResult:
        raise NotImplementedError("DuckDB query execution is implemented in a later phase.")

    def relation_exists(self, relation: Relation) -> bool:
        raise NotImplementedError("DuckDB metadata access is implemented in a later phase.")

    def get_columns(self, relation: Relation) -> tuple[ColumnMetadata, ...]:
        raise NotImplementedError("DuckDB metadata access is implemented in a later phase.")

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "queries": CapabilitySupport.UNSUPPORTED,
                "metadata_columns": CapabilitySupport.NOT_IMPLEMENTED,
                "metadata_precision_scale": CapabilitySupport.NOT_IMPLEMENTED,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.NOT_IMPLEMENTED,
                "aggregate": CapabilitySupport.NOT_IMPLEMENTED,
                "grouped_aggregate": CapabilitySupport.NOT_IMPLEMENTED,
                "key_diff": CapabilitySupport.NOT_IMPLEMENTED,
                "null_key": CapabilitySupport.NOT_IMPLEMENTED,
                "duplicate_key": CapabilitySupport.NOT_IMPLEMENTED,
            }
        )


class DuckDbAdapterFactory:
    """Factory that checks whether the optional DuckDB dependency is installed."""

    def __init__(self, *, dependency_available: Callable[[], bool] | None = None) -> None:
        self._dependency_available = dependency_available or _duckdb_dependency_available

    def create(self, connection: ConnectionConfig) -> AdapterResolutionResult:
        if not self._dependency_available():
            return AdapterResolutionResult(
                diagnostics=(
                    Diagnostic(
                        code=ADAPTER_DEPENDENCY_MISSING,
                        severity=DiagnosticSeverity.ERROR,
                        message="DuckDB adapter dependency is not installed.",
                        resource_type="adapter",
                        resource_name="duckdb",
                        hint="Install Recon Core with `recon-core[duckdb]`.",
                    ),
                )
            )

        return AdapterResolutionResult(adapter=DuckDbAdapter(connection=connection))


class DuckDbSqlRenderer(SqlRenderer):
    """DuckDB SQL renderer shell."""

    adapter_type = "duckdb"

    def render_operation(self, operation: Mapping[str, Any]) -> RenderedSql:
        raise NotImplementedError("DuckDB operation SQL rendering is implemented in Phase 3.")

    def quote_identifier(self, identifier: str) -> str:
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    def render_relation(self, relation: Relation) -> str:
        return ".".join(
            self.quote_identifier(part)
            for part in (relation.catalog, relation.schema, relation.identifier)
            if part is not None
        )


def _duckdb_dependency_available() -> bool:
    return find_spec("duckdb") is not None
