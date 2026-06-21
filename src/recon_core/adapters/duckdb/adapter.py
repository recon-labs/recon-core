"""DuckDB local development adapter foundation."""

from collections.abc import Callable
from importlib import import_module
from importlib.util import find_spec
from typing import Any

from recon_core._version import get_version
from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.capabilities import AdapterCapabilities, CapabilitySupport
from recon_core.adapters.duckdb.renderer import DuckDbSqlRenderer as DuckDbSqlRenderer
from recon_core.adapters.lifecycle import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
)
from recon_core.adapters.models import (
    ADAPTER_API_VERSION,
    AdapterResolutionResult,
    QueryResult,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

ADAPTER_DEPENDENCY_MISSING = "RC_ADAPTER_DEPENDENCY_MISSING"


class AdapterLifecycleError(RuntimeError):
    """Raised when adapter lifecycle or query execution fails with a safe diagnostic."""

    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(diagnostic.message)
        self.diagnostic = diagnostic


class DuckDbAdapter(BaseAdapter):
    """DuckDB local development adapter shell."""

    adapter_type = "duckdb"
    adapter_version = get_version()
    supported_adapter_api_version = ADAPTER_API_VERSION

    def __init__(self, *, connection: ConnectionConfig) -> None:
        super().__init__(connection=connection)
        self._connection: Any | None = None

    def connect(self) -> None:
        if self._connection is not None:
            return
        database = self.connection.config.get("database", ":memory:")
        try:
            duckdb = import_module("duckdb")
            self._connection = duckdb.connect(database)
        except Exception as exc:
            raise AdapterLifecycleError(
                _adapter_lifecycle_diagnostic(
                    code=ADAPTER_CONNECTION_FAILED,
                    message="DuckDB adapter connection failed.",
                    exc=exc,
                )
            ) from None

    def close(self) -> None:
        if self._connection is None:
            return
        connection = self._connection
        try:
            connection.close()
        except Exception as exc:
            raise AdapterLifecycleError(
                _adapter_lifecycle_diagnostic(
                    code=ADAPTER_CLOSE_FAILED,
                    message="DuckDB adapter close failed.",
                    exc=exc,
                )
            ) from None
        finally:
            self._connection = None

    def execute(self, query: str) -> QueryResult:
        if self._connection is None:
            raise AdapterLifecycleError(
                Diagnostic(
                    code=ADAPTER_CONNECTION_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="DuckDB adapter is not connected.",
                    resource_type="adapter",
                    resource_name=self.adapter_type,
                    hint="Call adapter.connect() before executing a query.",
                )
            )
        try:
            cursor = self._connection.execute(query)
            description = getattr(cursor, "description", None) or ()
            columns = tuple(str(column[0]) for column in description)
            rows = tuple(tuple(row) for row in cursor.fetchall())
            return QueryResult(columns=columns, rows=rows, row_count=len(rows))
        except AdapterLifecycleError:
            raise
        except Exception as exc:
            raise AdapterLifecycleError(
                _adapter_lifecycle_diagnostic(
                    code=ADAPTER_QUERY_FAILED,
                    message="DuckDB query execution failed.",
                    exc=exc,
                )
            ) from None

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                "relations": CapabilitySupport.FULL,
                "queries": CapabilitySupport.UNSUPPORTED,
                "metadata_columns": CapabilitySupport.NOT_IMPLEMENTED,
                "metadata_precision_scale": CapabilitySupport.NOT_IMPLEMENTED,
                "cte_support": CapabilitySupport.FULL,
                "row_count": CapabilitySupport.FULL,
                "aggregate": CapabilitySupport.FULL,
                "grouped_aggregate": CapabilitySupport.FULL,
                "key_diff": CapabilitySupport.FULL,
                "null_key": CapabilitySupport.FULL,
                "duplicate_key": CapabilitySupport.FULL,
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


def _duckdb_dependency_available() -> bool:
    return find_spec("duckdb") is not None


def _adapter_lifecycle_diagnostic(
    *,
    code: str,
    message: str,
    exc: Exception,
) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="adapter",
        resource_name="duckdb",
        hint=(
            f"DuckDB raised {type(exc).__name__}. Raw adapter, SQL, database error, "
            "and rendered profile text were suppressed."
        ),
    )
