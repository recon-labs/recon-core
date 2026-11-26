"""Private owned read-only DuckDB transaction for project-run binding."""

from collections.abc import Callable
from importlib import import_module
from typing import Any

from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters._project_binding import (
    _BindingLease,
    _BindingScope,
    _BoundSessionError,
    _diagnostic,
    _LocalFileIdentity,
    _proof_error,
)
from recon_core.adapters.duckdb.adapter import _read_aggregate_result, _read_query_result
from recon_core.adapters.duckdb.runtime_scan_guard import (
    _current_file_identity,
    _duckdb_relation_name,
    _local_duckdb_catalog_names,
    _resolve_local_base_table,
)
from recon_core.adapters.lifecycle import (
    ADAPTER_CLOSE_FAILED,
    ADAPTER_CONNECTION_FAILED,
    ADAPTER_QUERY_FAILED,
)
from recon_core.adapters.models import QueryResult, Relation
from recon_core.diagnostics import Diagnostic

# The lease binds the typed check family as well as the exact relations.
_AGGREGATE_BINDING_OPERATIONS = frozenset({"sum_diff", "grouped_aggregate_diff"})
_COUNT_BINDING_OPERATIONS = frozenset(
    {
        "row_count_diff",
        "null_source_keys",
        "null_target_keys",
        "duplicate_source_keys",
        "duplicate_target_keys",
        "missing_keys",
        "extra_keys",
    }
)


class _VerifiedReadConnection:
    """Only the execute seam needed by the existing result transport readers."""

    def __init__(self, execute: Callable[[str], Any]) -> None:
        self._execute = execute

    def execute(self, query: str) -> Any:
        return self._execute(query)


class _OwnedDuckDbSession:
    """Single-use session; the caller must close it in a finally block."""

    def __init__(self, identity: _LocalFileIdentity) -> None:
        self._identity = identity
        self._connection: Any = None
        self._attempted = False
        self._invalidated = False
        self._binding_attempted = False
        self._lease: _BindingLease | None = None
        self._transaction = False
        self._released = True
        self._cleanup: tuple[Diagnostic, ...] | None = None

    @property
    def released(self) -> bool:
        return self._released

    def _verify_file(self) -> None:
        if self._invalidated or _current_file_identity(self._identity.path) != self._identity:
            self._invalidated = True
            raise _proof_error()

    def open(self) -> None:
        if self._attempted or self._cleanup is not None:
            raise _proof_error()
        self._attempted = True
        self._verify_file()
        try:
            duckdb = import_module("duckdb")
            self._connection = duckdb.connect(str(self._identity.path), read_only=True)
            self._released = False
        except Exception:
            raise _BoundSessionError(
                ADAPTER_CONNECTION_FAILED,
                "Read-only execution session could not be opened or initialized.",
            ) from None
        self._verify_file()
        try:
            self._connection.execute("BEGIN TRANSACTION")
            self._transaction = True
        except Exception:
            raise _BoundSessionError(
                ADAPTER_CONNECTION_FAILED,
                "Read-only execution session could not be opened or initialized.",
            ) from None

    def resolve_relation(self, name: str) -> Relation | None:
        if not self._transaction or self._cleanup is not None:
            raise _proof_error()
        self._verify_file()
        relation = _duckdb_relation_name(name)
        if relation is None:
            return None
        try:
            catalogs = _local_duckdb_catalog_names(self._connection, self._identity.path)
            self._verify_file()
            if not catalogs:
                return None
            resolved = _resolve_local_base_table(
                self._connection, relation, local_catalog_names=catalogs
            )
            self._verify_file()
            return resolved
        except Exception:
            self._invalidated = True
            raise _proof_error() from None

    def bind(
        self, *, check_id: str, operation: str, source: str, target: str
    ) -> _BindingLease | None:
        if self._binding_attempted or not self._transaction or self._cleanup is not None:
            self._invalidated = True
            raise _proof_error()
        self._binding_attempted = True
        self._verify_file()
        source_relation = self.resolve_relation(source)
        target_relation = self.resolve_relation(target)
        if source_relation is None or target_relation is None:
            self._invalidated = True
            return None
        self._verify_file()
        self._lease = _BindingLease(
            _BindingScope(check_id, operation, source_relation, target_relation)
        )
        return self._lease

    def verify_lease(self, lease: _BindingLease, scope: _BindingScope) -> None:
        if (
            not self._transaction
            or self._cleanup is not None
            or self._lease is not lease
            or lease.scope != scope
        ):
            self._invalidated = True
            raise _proof_error()
        self._verify_file()

    def _verified_reader(
        self, lease: _BindingLease, scope: _BindingScope, query: str, *, describe: bool = False
    ) -> _VerifiedReadConnection:
        # Only trusted internal rendered statements reach this private seam.
        # The only transport-generated follow-up is DESCRIBE of the same statement.
        self.verify_lease(lease, scope)
        operations = _AGGREGATE_BINDING_OPERATIONS if describe else _COUNT_BINDING_OPERATIONS
        if scope.operation not in operations:
            self._invalidated = True
            raise _proof_error()

        def execute(statement: str) -> Any:
            self.verify_lease(lease, scope)
            if statement != query and not (describe and statement == f"DESCRIBE {query}"):
                self._invalidated = True
                raise _proof_error()
            try:
                return self._connection.execute(statement)
            except Exception:
                self._invalidated = True
                raise _BoundSessionError(
                    ADAPTER_QUERY_FAILED, "DuckDB query execution failed."
                ) from None

        return _VerifiedReadConnection(execute)

    def _read_bound_query(
        self, lease: _BindingLease, scope: _BindingScope, query: str
    ) -> QueryResult:
        try:
            reader = self._verified_reader(lease, scope, query)
            result = _read_query_result(reader, query)
            self.verify_lease(lease, scope)
            return result
        except Exception:
            self._invalidated = True
            raise

    def _read_bound_aggregate(
        self,
        lease: _BindingLease,
        scope: _BindingScope,
        query: str,
        *,
        expected_columns: tuple[str, ...],
    ) -> _AggregateQueryResult:
        try:
            reader = self._verified_reader(lease, scope, query, describe=True)
            result = _read_aggregate_result(reader, query, expected_columns)
            self.verify_lease(lease, scope)
            return result
        except Exception:
            self._invalidated = True
            raise

    def close(self) -> tuple[Diagnostic, ...]:
        if self._cleanup is not None:
            return self._cleanup
        self._lease = None
        self._invalidated = True
        diagnostics: list[Diagnostic] = []
        if self._connection is not None:
            try:
                if self._transaction:
                    try:
                        self._connection.execute("ROLLBACK")
                    except Exception:
                        diagnostics.append(
                            _diagnostic(
                                ADAPTER_CLOSE_FAILED, "Read-only transaction cleanup failed."
                            )
                        )
            finally:
                self._transaction = False
                try:
                    self._connection.close()
                except Exception:
                    diagnostics.append(
                        _diagnostic(
                            ADAPTER_CLOSE_FAILED, "Read-only execution session cleanup failed."
                        )
                    )
                else:
                    self._released = True
                    self._connection = None
                finally:
                    self._cleanup = tuple(diagnostics)
        else:
            self._cleanup = ()
        return self._cleanup
