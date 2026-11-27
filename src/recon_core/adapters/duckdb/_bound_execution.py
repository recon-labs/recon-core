"""Private owned read-only DuckDB transaction for project-run binding."""

from collections.abc import Callable
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from tempfile import gettempdir
from typing import Any

from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters._local_resource_observation import (
    _LocalObservation,
    _observe_local_resources,
)
from recon_core.adapters._project_binding import (
    _BindingLease,
    _BindingScope,
    _BoundSessionError,
    _diagnostic,
    _LocalFileIdentity,
    _proof_error,
)
from recon_core.adapters._resource_scratch import (
    _CheckScratch,
    _create_check_scratch,
    _ScratchError,
)
from recon_core.adapters.duckdb._native_resource_controls import (
    _apply_native_controls,
    _native_startup_config,
    _NativeControlError,
    _NativeControlRequest,
    _read_native_recommendations,
)
from recon_core.adapters.duckdb._resource_targets import (
    _calculate_local_resource_targets,
    _LocalResourceInputs,
    _LocalResourceTargets,
    _UnknownPercentageCapacityError,
)
from recon_core.adapters.duckdb.adapter import _read_aggregate_result
from recon_core.adapters.duckdb.renderer_sql import quote_identifier, sql_string_literal
from recon_core.adapters.duckdb.runtime_scan_guard import (
    _current_file_identity,
    _duckdb_identifier_key,
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
from recon_core.config._local_resource_policy import _LocalResourcePolicy
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

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


def _read_bound_count_result(connection: Any, query: str, *, max_columns: int) -> QueryResult:
    """Read at most two rows of a bounded integer-only native summary.

    Leave exact expected column names and comparison arithmetic to the existing
    Core validators. Invalid shapes contain no native values; the existing
    invalid-result diagnostics remain authoritative.
    """
    cursor = connection.execute(query)
    description = getattr(cursor, "description", None)
    invalid = QueryResult(columns=(), rows=(), row_count=0)
    if not isinstance(description, list | tuple) or not 1 <= len(description) <= max_columns:
        return invalid
    if any(
        not isinstance(column, list | tuple) or not column or not isinstance(column[0], str)
        for column in description
    ):
        return invalid
    columns = tuple(column[0] for column in description)
    rows = cursor.fetchmany(2)
    if not isinstance(rows, list | tuple) or len(rows) != 1:
        return QueryResult(columns=columns, rows=(), row_count=0)
    row = rows[0]
    if (
        not isinstance(row, list | tuple)
        or len(row) != len(columns)
        or any(type(value) is not int for value in row)
    ):
        return QueryResult(columns=columns, rows=(), row_count=0)
    return QueryResult(columns=columns, rows=(tuple(row),), row_count=1)


class _VerifiedReadConnection:
    """Only the execute seam needed by the existing result transport readers."""

    def __init__(self, execute: Callable[[str], Any]) -> None:
        self._execute = execute

    def execute(self, query: str) -> Any:
        return self._execute(query)


def _current_catalog(connection: Any) -> str:
    rows = connection.execute("SELECT current_database()").fetchmany(2)
    if (
        not isinstance(rows, list | tuple)
        or len(rows) != 1
        or not isinstance(rows[0], tuple)
        or len(rows[0]) != 1
        or not isinstance(rows[0][0], str)
        or not rows[0][0]
    ):
        raise _proof_error()
    return rows[0][0]


def _attach_guarded_database(connection: Any, path: Path, catalog: str) -> None:
    """Attach the actual guarded file under its original native catalog."""

    collision = _duckdb_identifier_key(catalog) == "memory"
    if collision:
        connection.execute("ATTACH ':memory:' AS recon_seed")
        connection.execute("USE recon_seed")
        connection.execute("DETACH memory")
    connection.execute(f"ATTACH {sql_string_literal(str(path))} (READ_ONLY)")
    connection.execute(f"USE {quote_identifier(catalog)}")
    if collision:
        connection.execute("DETACH recon_seed")

    if _current_catalog(connection) != catalog or _local_duckdb_catalog_names(
        connection, path
    ) != frozenset({_duckdb_identifier_key(catalog)}):
        raise _proof_error()

    # Native metadata must show the exact read-only attachment, not merely
    # a requested ATTACH option or a catalog inferred from a filename.
    rows = connection.execute(
        "SELECT database_name, path, readonly FROM duckdb_databases() WHERE NOT internal LIMIT 3"
    ).fetchmany(3)
    if not isinstance(rows, list | tuple) or not 1 <= len(rows) <= 2:
        raise _proof_error()
    matches = 0
    for row in rows:
        if (
            not isinstance(row, tuple)
            or len(row) != 3
            or not isinstance(row[0], str)
            or type(row[2]) is not bool
        ):
            raise _proof_error()
        name, native_path, readonly = row
        if name == catalog:
            if not isinstance(native_path, str) or Path(native_path).resolve() != path:
                raise _proof_error()
            if readonly is not True:
                raise _proof_error()
            matches += 1
        elif _duckdb_identifier_key(name) != "memory" or native_path not in (None, "", ":memory:"):
            raise _proof_error()
    if matches != 1:
        raise _proof_error()


def _policy_scratch_base(project_root: Path, policy: _LocalResourcePolicy) -> Path:
    """Resolve only the selected base; never create or switch an authored location."""
    path = (
        Path(gettempdir()) if policy.scratch_directory is None else Path(policy.scratch_directory)
    )
    if not path.is_absolute():
        path = project_root / path
    return path.resolve(strict=True)


def _normalize_resource_policy(
    project_root: Path, policy: _LocalResourcePolicy
) -> _LocalResourcePolicy:
    """Compare authored modes with canonical scratch selection, not host capacity."""
    try:
        return replace(policy, scratch_directory=str(_policy_scratch_base(project_root, policy)))
    except (OSError, RuntimeError, ValueError):
        raise _BoundSessionError(
            "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
            "Private temporary storage could not be established. "
            "Use an existing writable private scratch base.",
        ) from None


def _resource_advisories(
    observed: _LocalObservation,
    inputs: _LocalResourceInputs,
    targets: _LocalResourceTargets,
    policy: _LocalResourcePolicy,
) -> tuple[Diagnostic, ...]:
    advisories: list[Diagnostic] = []

    def warn(message: str, hint: str) -> None:
        advisories.append(
            Diagnostic(
                code="RC_RUNTIME_RESOURCE_ADVISORY",
                severity=DiagnosticSeverity.WARNING,
                message=message,
                resource_type="runtime_policy",
                hint=hint,
            )
        )

    for dimension, available, hint in (
        ("managed-memory", inputs.memory_headroom_bytes, "Use auto or fixed MiB tuning."),
        ("threads", inputs.cpu_capacity, "Use auto or an explicit thread count."),
        ("spill", inputs.scratch_free_bytes, "Use a writable private scratch base or fixed MiB."),
    ):
        if available is None:
            warn(
                f"Available {dimension} capacity is unknown; using available native or "
                "configured settings, not a capacity guarantee.",
                hint,
            )
    if (
        inputs.memory_headroom_bytes is not None
        and inputs.native_memory_bytes is None
        and policy.managed_memory_bytes is None
        and policy.managed_memory_percent is None
    ):
        warn(
            "Native managed-memory recommendation is unavailable; using observed headroom.",
            "Inspect available memory and use fixed MiB tuning if needed.",
        )
    if inputs.cpu_capacity is not None and inputs.native_threads is None and policy.threads is None:
        warn(
            "Native threads recommendation is unavailable; using observed CPU capacity.",
            "Inspect CPU capacity and use an explicit thread count if needed.",
        )
    constraints = observed.linux_constraints
    if observed.platform == "linux" and (
        constraints is None
        or not constraints.full_hierarchy_proven
        or constraints.memory_incomplete
        or constraints.cpu_incomplete
    ):
        warn(
            "Local controller scope is incomplete; resource tuning uses available facts, "
            "not a host or container limit guarantee.",
            "Inspect container resource limits locally and adjust managed settings if needed.",
        )
    if inputs.scratch_memory_backed is True:
        warn(
            "Spill storage is memory-backed; it shares memory headroom with query execution.",
            "Use an existing private disk-backed scratch base for independent spill capacity.",
        )
    for dimension in targets.reduced_authored_targets:
        warn(
            f"Requested {dimension} target was reduced to available observed capacity; "
            "execution may proceed without a capacity guarantee.",
            "Inspect available resources or adjust the selected execution settings.",
        )
    return tuple(advisories)


def _adaptive_native_request(
    connection: Any, scratch: Path, policy: _LocalResourcePolicy
) -> tuple[_NativeControlRequest, tuple[Diagnostic, ...]]:
    observed = _observe_local_resources(scratch)
    native = _read_native_recommendations(connection)
    inputs = _LocalResourceInputs(
        memory_headroom_bytes=observed.memory_headroom_bytes,
        cpu_capacity=observed.cpu_capacity,
        scratch_free_bytes=observed.scratch_free_bytes,
        scratch_memory_backed=observed.scratch_memory_backed,
        native_memory_bytes=native.memory_bytes,
        native_threads=native.threads,
    )
    targets = _calculate_local_resource_targets(policy, inputs)
    if targets.managed_memory_bytes == 0:
        raise _BoundSessionError(
            "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
            "No usable managed-memory capacity for this check. Free memory or adjust tuning.",
        )
    if targets.threads == 0:
        raise _BoundSessionError(
            "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
            "No usable threads capacity for this check. Inspect available CPU resources.",
        )
    # Native zero-spill effect has not yet been independently established.
    if targets.spill_bytes == 0:
        raise _BoundSessionError(
            "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
            "No usable positive spill capacity; verified no-spill execution is unavailable. "
            "Free space or select an existing private disk-backed scratch base.",
        )
    request = _NativeControlRequest(
        targets.managed_memory_bytes, targets.threads, targets.spill_bytes, scratch
    )
    return request, _resource_advisories(observed, inputs, targets, policy)


def _catalog_estimated_rows(connection: Any, relation: Relation) -> int | None:
    """Optional native catalog evidence, never execute a data query to estimate."""
    try:
        rows = connection.execute(
            "SELECT estimated_size FROM duckdb_tables() "
            "WHERE database_name = ? AND schema_name = ? AND table_name = ? LIMIT 2",
            [relation.catalog, relation.schema, relation.identifier],
        ).fetchmany(2)
    except Exception:
        return None
    if not isinstance(rows, list | tuple) or len(rows) != 1:
        return None
    row = rows[0]
    if not isinstance(row, tuple) or len(row) != 1:
        return None
    count = row[0]
    return count if type(count) is int and 0 <= count <= (1 << 63) - 1 else None


def _estimated_input_rows(connection: Any, scope: _BindingScope) -> int | None:
    relations: tuple[Relation, ...]
    if scope.operation in {"null_source_keys", "duplicate_source_keys"}:
        relations = (scope.source,)
    elif scope.operation in {"null_target_keys", "duplicate_target_keys"}:
        relations = (scope.target,)
    else:
        relations = (scope.source, scope.target)
    total = 0
    for relation in relations:
        count = _catalog_estimated_rows(connection, relation)
        if count is None:
            return None
        total += count
    return total if total <= (1 << 63) - 1 else None


class _OwnedDuckDbSession:
    """Single-use session; the caller must close it in a finally block."""

    def __init__(
        self,
        identity: _LocalFileIdentity,
        *,
        native_controls: _NativeControlRequest | None = None,
        scratch_base: Path | None = None,
        project_root: Path | None = None,
        resource_policy: _LocalResourcePolicy | None = None,
    ) -> None:
        self._identity = identity
        if (project_root is None) != (resource_policy is None) or sum(
            mode is not None for mode in (native_controls, scratch_base, resource_policy)
        ) > 1:
            raise ValueError("Specify one native scratch ownership mode.")
        self._project_root = project_root
        self._resource_policy = resource_policy
        self._native_controls = native_controls
        self._scratch_base = scratch_base
        self._scratch: _CheckScratch | None = None
        self._connection: Any = None
        self._guard: Any = None
        self._attempted = False
        self._invalidated = False
        self._binding_attempted = False
        self._lease: _BindingLease | None = None
        self._transaction = False
        self._released = True
        self._cleanup: tuple[Diagnostic, ...] | None = None
        self._advisories: tuple[Diagnostic, ...] = ()

    @property
    def advisories(self) -> tuple[Diagnostic, ...]:
        return self._advisories

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
        if self._scratch_base is not None or self._resource_policy is not None:
            try:
                base = self._scratch_base
                if self._resource_policy is not None:
                    assert self._project_root is not None
                    base = _policy_scratch_base(self._project_root, self._resource_policy)
                assert base is not None
                self._scratch = _create_check_scratch(base)
                self._released = False
                self._native_controls = _NativeControlRequest(None, None, None, self._scratch.path)
            except (OSError, RuntimeError, ValueError):
                self._invalidated = True
                raise _BoundSessionError(
                    "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
                    "Private temporary storage could not be established. "
                    "Use an existing writable private scratch base.",
                ) from None
        catalog = ""
        try:
            duckdb = import_module("duckdb")
            if self._native_controls is None:
                self._connection = duckdb.connect(str(self._identity.path), read_only=True)
                self._released = False
            else:
                self._guard = duckdb.connect(str(self._identity.path), read_only=True)
                self._released = False
                self._verify_file()
                catalog = _current_catalog(self._guard)
                if _local_duckdb_catalog_names(self._guard, self._identity.path) != frozenset(
                    {_duckdb_identifier_key(catalog)}
                ):
                    raise _proof_error()
                self._connection = duckdb.connect(
                    ":memory:", config=_native_startup_config(self._native_controls)
                )
        except _BoundSessionError:
            self._invalidated = True
            raise
        except Exception:
            self._invalidated = True
            raise _BoundSessionError(
                ADAPTER_CONNECTION_FAILED,
                "Read-only execution session could not be opened or initialized. "
                "Close conflicting connections or use a separate invocation.",
            ) from None
        self._verify_file()
        if self._native_controls is not None:
            try:
                if self._resource_policy is not None:
                    assert self._scratch is not None
                    self._native_controls, self._advisories = _adaptive_native_request(
                        self._connection, self._scratch.path, self._resource_policy
                    )
                _apply_native_controls(
                    self._connection,
                    self._native_controls,
                    assign_memory_threads=self._resource_policy is not None,
                )
            except _UnknownPercentageCapacityError as exc:
                self._invalidated = True
                dimension = "managed-memory" if exc.setting == "managed-memory" else "spill"
                raise _BoundSessionError(
                    "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
                    f"Available {dimension} capacity is unknown for the selected percentage; "
                    "use auto or fixed MiB tuning.",
                ) from None
            except _BoundSessionError:
                self._invalidated = True
                raise
            except (_NativeControlError, ValueError):
                self._invalidated = True
                raise _BoundSessionError(
                    "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
                    "Required native resource setting could not be verified. "
                    "Inspect supported native controls and selected tuning.",
                ) from None
            try:
                _attach_guarded_database(self._connection, self._identity.path, catalog)
            except Exception:
                self._invalidated = True
                raise _proof_error() from None
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
        policy = self._resource_policy
        threshold = policy.warn_estimated_input_rows if policy is not None else None
        if threshold is not None:
            estimated = _estimated_input_rows(self._connection, self._lease.scope)
            self.verify_lease(self._lease, self._lease.scope)
            if estimated is None:
                self._advisories += (
                    Diagnostic(
                        code="RC_RUNTIME_ESTIMATED_INPUT_ROWS_UNKNOWN",
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            "Catalog input row estimate is unavailable; the configured advisory "
                            "threshold cannot be evaluated. Execution continues."
                        ),
                        resource_type="runtime_policy",
                        hint="Review workload scope locally; no estimate-based conclusion is made.",
                    ),
                )
            elif estimated > threshold:
                self._advisories += (
                    Diagnostic(
                        code="RC_RUNTIME_ESTIMATED_INPUT_ROWS_ADVISORY",
                        severity=DiagnosticSeverity.WARNING,
                        message=(
                            "Catalog input row estimate exceeds the configured advisory "
                            "threshold; execution continues."
                        ),
                        resource_type="runtime_policy",
                        hint="Review workload scope or adjust warn-estimated-input-rows.",
                    ),
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
            result = _read_bound_count_result(
                reader, query, max_columns=3 if scope.operation == "row_count_diff" else 1
            )
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

    def request_interrupt(self) -> bool:
        """Request native interruption, not confirmed query termination.

        The owner must wait for the executing call and the interrupt caller
        to return before closing the session. No guard or scratch is released
        here, and the interrupted session is not reusable.
        """

        if not self._transaction or self._cleanup is not None or self._connection is None:
            return False
        try:
            self._connection.interrupt()
        except Exception:
            return False
        self._invalidated = True
        return True

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
                    self._connection = None
        # The ordinary reader must outlive the actor. A failed actor close
        # retains both handles and prevents the caller from removing scratch.
        if self._connection is None and self._guard is not None:
            try:
                self._guard.close()
            except Exception:
                diagnostics.append(
                    _diagnostic(ADAPTER_CLOSE_FAILED, "Read-only file guard cleanup failed.")
                )
            else:
                self._guard = None
        if self._connection is None and self._guard is None and self._scratch is not None:
            try:
                self._scratch.cleanup(native_closed=True)
            except _ScratchError:
                diagnostics.append(
                    _diagnostic(ADAPTER_CLOSE_FAILED, "Private temporary storage cleanup failed.")
                )
            else:
                self._scratch = None
        self._released = self._connection is None and self._guard is None and self._scratch is None
        self._cleanup = tuple(diagnostics)
        return self._cleanup
