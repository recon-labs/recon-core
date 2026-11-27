"""Private adapter-neutral project binding contract and built-in dispatch."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters.models import QueryResult, Relation
from recon_core.config._local_resource_policy import _LocalResourcePolicy
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig

# Temporary compatibility limit, not a calibrated resource ceiling.
_MAX_BOUNDED_LOCAL_DUCKDB_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class _LocalFileIdentity:
    path: Path
    device: int
    inode: int
    size: int
    modified_ns: int


class _BoundSessionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.diagnostic = _diagnostic(code, message)


def _diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="adapter",
    )


def _proof_error() -> _BoundSessionError:
    return _BoundSessionError(
        "RC_RUNTIME_BINDING_PROOF_FAILED", "Execution binding could not be verified."
    )


@dataclass(frozen=True, slots=True)
class _BindingScope:
    check_id: str = field(repr=False)
    operation: str
    source: Relation = field(repr=False)
    target: Relation = field(repr=False)


@dataclass(frozen=True, slots=True, eq=False)
class _BindingLease:
    """Identity-only proof owned by one single-use transaction."""

    scope: _BindingScope = field(repr=False)


class _InvalidAggregateResultError(ValueError):
    """Private malformed numeric transport; never include raw query or values."""


class _OwnedSession(Protocol):
    @property
    def advisories(self) -> tuple[Diagnostic, ...]: ...

    @property
    def released(self) -> bool: ...

    def open(self) -> None: ...

    def bind(
        self, *, check_id: str, operation: str, source: str, target: str
    ) -> _BindingLease | None: ...

    def _read_bound_query(
        self, lease: _BindingLease, scope: _BindingScope, query: str
    ) -> QueryResult: ...

    def _read_bound_aggregate(
        self,
        lease: _BindingLease,
        scope: _BindingScope,
        query: str,
        *,
        expected_columns: tuple[str, ...],
    ) -> _AggregateQueryResult: ...

    def close(self) -> tuple[Diagnostic, ...]: ...


def _local_file_identity(
    connection: ConnectionConfig, project_root: Path
) -> _LocalFileIdentity | None:
    if connection.type != "duckdb":
        return None
    from recon_core.adapters.duckdb.runtime_scan_guard import _local_file_identity as inspect

    return inspect(connection, project_root)


def _normalize_owned_resource_policy(
    adapter_type: str, project_root: Path, policy: _LocalResourcePolicy
) -> _LocalResourcePolicy:
    if adapter_type != "duckdb":
        raise _proof_error()
    from recon_core.adapters.duckdb._bound_execution import _normalize_resource_policy

    return _normalize_resource_policy(project_root, policy)


def _new_owned_session(
    adapter_type: str,
    identity: _LocalFileIdentity,
    *,
    project_root: Path,
    resource_policy: _LocalResourcePolicy,
) -> _OwnedSession:
    if adapter_type != "duckdb":
        raise _proof_error()
    from recon_core.adapters.duckdb._bound_execution import _OwnedDuckDbSession

    return _OwnedDuckDbSession(identity, project_root=project_root, resource_policy=resource_policy)
