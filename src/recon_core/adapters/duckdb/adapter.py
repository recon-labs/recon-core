"""DuckDB local development adapter foundation."""

import re
from collections.abc import Callable
from decimal import Decimal
from importlib import import_module
from importlib.util import find_spec
from typing import Any, TypeVar

from recon_core._version import get_version
from recon_core.adapters._aggregate_runtime import (
    _AggregateQueryResult,
    _NumericDomain,
    _NumericValue,
)
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

_ResultT = TypeVar("_ResultT")
_INTEGER_TYPES = frozenset(
    {
        "TINYINT",
        "SMALLINT",
        "INTEGER",
        "BIGINT",
        "HUGEINT",
        "UTINYINT",
        "USMALLINT",
        "UINTEGER",
        "UBIGINT",
        "UHUGEINT",
        "BIGNUM",
        "VARINT",
    }
)
_ARBITRARY_INTEGER_TYPES = frozenset({"BIGNUM", "VARINT"})
_GENERIC_TYPE_CATEGORIES = frozenset({"NUMBER", "STRING"})


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
        def read(connection: Any) -> QueryResult:
            cursor = connection.execute(query)
            description = getattr(cursor, "description", None) or ()
            columns = tuple(str(column[0]) for column in description)
            rows = tuple(tuple(row) for row in cursor.fetchall())
            return QueryResult(columns=columns, rows=rows, row_count=len(rows))

        return self._read_query(read)

    def _execute_aggregate_query(
        self, query: str, *, expected_columns: tuple[str, ...]
    ) -> _AggregateQueryResult:
        """Read one bounded result from a trusted internal aggregate SELECT."""
        return self._read_query(
            lambda connection: _read_aggregate_result(connection, query, expected_columns)
        )

    def _read_query(self, read: Callable[[Any], _ResultT]) -> _ResultT:
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
            return read(self._connection)
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


class _InvalidAggregateResult(ValueError):
    """Private malformed numeric transport; never include raw query or values."""


def _read_type_description(
    description: object, expected_columns: tuple[str, ...]
) -> tuple[str, ...]:
    if not isinstance(description, (list, tuple)) or len(description) != len(expected_columns):
        raise _InvalidAggregateResult()
    types: list[str] = []
    for column, name in zip(description, expected_columns, strict=True):
        if not isinstance(column, (list, tuple)) or len(column) < 2 or column[0] != name:
            raise _InvalidAggregateResult()
        if not isinstance(column[0], str) or column[1] is None:
            raise _InvalidAggregateResult()
        types.append(str(column[1]).upper())
    return tuple(types)


def _resolve_logical_types(
    connection: Any, query: str, columns: tuple[str, ...], types: tuple[str, ...]
) -> tuple[str, ...]:
    if not any(kind in _GENERIC_TYPE_CATEGORIES for kind in types):
        return types
    # Older drivers expose broad DB-API categories. DESCRIBE binds the same
    # trusted SELECT without reading its data; it is not a comparison fallback.
    metadata = connection.execute(f"DESCRIBE {query}").fetchmany(len(columns) + 1)
    resolved = _read_type_description(metadata, columns)
    for original, logical in zip(types, resolved, strict=True):
        if original == "STRING":
            if logical not in _ARBITRARY_INTEGER_TYPES:
                raise _InvalidAggregateResult()
        elif original == "NUMBER":
            if logical in _ARBITRARY_INTEGER_TYPES:
                # A numeric category may also represent a native exact integer.
                continue
            _numeric_domain(logical)
        elif original != logical:
            raise _InvalidAggregateResult()
    return resolved


def _numeric_domain(logical_type: str) -> _NumericDomain:
    if logical_type in _INTEGER_TYPES:
        return _NumericDomain.EXACT_INTEGER
    if logical_type in {"FLOAT", "DOUBLE"}:
        return _NumericDomain.NATIVE_FLOAT
    decimal = re.fullmatch(r"DECIMAL\(([0-9]{1,2}),\s*([0-9]{1,2})\)", logical_type)
    if decimal is not None:
        width, scale = (int(part) for part in decimal.groups())
        if 1 <= width <= 38 and 0 <= scale <= width:
            return _NumericDomain.EXACT_DECIMAL
    raise _InvalidAggregateResult()


def _normalize_numeric_value(
    value: object, logical_type: str, domain: _NumericDomain
) -> _NumericValue:
    if value is None:
        return None
    if domain is _NumericDomain.EXACT_INTEGER:
        if type(value) is int:
            return value
        if (
            logical_type in _ARBITRARY_INTEGER_TYPES
            and isinstance(value, str)
            and re.fullmatch(r"-?(0|[1-9][0-9]*)", value)
        ):
            # Decimal construction and conversion to int are exact, independent
            # of decimal context and the integer-string conversion digit limit.
            return int(Decimal(value))
    elif domain is _NumericDomain.EXACT_DECIMAL:
        if isinstance(value, Decimal) and value.is_finite():
            return value
    elif domain is _NumericDomain.NATIVE_FLOAT and type(value) is float:
        # Preserve native NaN/Inf as well as signed zero. Core decides whether
        # numeric results are valid for comparison; the adapter owns transport.
        return value
    raise _InvalidAggregateResult()


def _read_aggregate_result(
    connection: Any, query: str, columns: tuple[str, ...]
) -> _AggregateQueryResult:
    if (
        not columns
        or any(not isinstance(name, str) or not name for name in columns)
        or len(set(columns)) != len(columns)
    ):
        raise _InvalidAggregateResult()
    cursor = connection.execute(query)
    types = _read_type_description(cursor.description, columns)
    rows = cursor.fetchmany(2)
    if not isinstance(rows, (list, tuple)) or len(rows) != 1:
        raise _InvalidAggregateResult()
    row = rows[0]
    if not isinstance(row, (list, tuple)) or len(row) != len(columns):
        raise _InvalidAggregateResult()
    types = _resolve_logical_types(connection, query, columns, types)
    domains = tuple(_numeric_domain(kind) for kind in types)
    normalized = tuple(
        _normalize_numeric_value(value, kind, domain)
        for value, kind, domain in zip(row, types, domains, strict=True)
    )
    return _AggregateQueryResult(columns=columns, domains=domains, row=normalized)


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
