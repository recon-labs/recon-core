"""Child-side owned session and scope binding for the private worker.

The transport and admission owner must establish scratch ownership and
policy proof before invoking this collaborator. It is not a public SQL
endpoint or a substitute for parent resource admission.
"""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from recon_core.adapters._aggregate_runtime import (
    _SCALAR_COLUMNS,
    _SUMMARY_COLUMNS,
    _AggregateQueryResult,
)
from recon_core.adapters._project_binding import (
    _BindingLease,
    _BindingScope,
    _LocalFileIdentity,
    _proof_error,
)
from recon_core.adapters.duckdb._bound_execution import (
    _AGGREGATE_BINDING_OPERATIONS,
    _COUNT_BINDING_OPERATIONS,
    _OwnedDuckDbSession,
)
from recon_core.adapters.duckdb._native_resource_controls import _NativeControlRequest
from recon_core.adapters.models import QueryResult
from recon_core.diagnostics import Diagnostic


@dataclass(frozen=True, slots=True)
class _WorkerBindingProof:
    """Wire-compatible identity fields, not the child-local native lease."""

    session_id: UUID
    policy_generation: int
    nonce: UUID
    scope: _BindingScope = field(repr=False)


class _WorkerBoundSession:
    """One native transaction and binding; no fallback or second executor."""

    def __init__(
        self,
        identity: _LocalFileIdentity,
        *,
        controls: _NativeControlRequest,
        session_id: UUID,
        policy_generation: int,
    ) -> None:
        if (
            not isinstance(controls, _NativeControlRequest)
            or not isinstance(session_id, UUID)
            or type(policy_generation) is not int
            or policy_generation <= 0
        ):
            raise _proof_error()
        self._session = _OwnedDuckDbSession(identity, native_controls=controls)
        self._session_id = session_id
        self._generation = policy_generation
        self._lease: _BindingLease | None = None
        self._proof: _WorkerBindingProof | None = None
        self._invalidated = False

    @property
    def released(self) -> bool:
        return self._session.released

    def open(self) -> None:
        if self._invalidated:
            raise _proof_error()
        try:
            self._session.open()
        except Exception:
            self._invalidated = True
            raise

    def bind(
        self, *, check_id: str, operation: str, source: str, target: str
    ) -> _WorkerBindingProof | None:
        if (
            self._invalidated
            or self._proof is not None
            or operation not in (_COUNT_BINDING_OPERATIONS | _AGGREGATE_BINDING_OPERATIONS)
        ):
            self._invalidated = True
            raise _proof_error()
        try:
            lease = self._session.bind(
                check_id=check_id, operation=operation, source=source, target=target
            )
            if lease is None:
                self._invalidated = True
                return None
            self._lease = lease
            self._proof = _WorkerBindingProof(
                self._session_id, self._generation, uuid4(), lease.scope
            )
            return self._proof
        except Exception:
            self._invalidated = True
            raise

    def _verified_lease(
        self, proof: _WorkerBindingProof, operations: frozenset[str]
    ) -> _BindingLease:
        lease = self._lease
        if (
            self._invalidated
            or lease is None
            or not isinstance(proof, _WorkerBindingProof)
            or proof != self._proof
            or lease.scope.operation not in operations
        ):
            self._invalidated = True
            raise _proof_error()
        self._session.verify_lease(lease, lease.scope)
        return lease

    def read_count(self, proof: _WorkerBindingProof, query: str) -> QueryResult:
        try:
            lease = self._verified_lease(proof, _COUNT_BINDING_OPERATIONS)
            return self._session._read_bound_query(lease, lease.scope, query)
        except Exception:
            self._invalidated = True
            raise

    def read_aggregate(
        self, proof: _WorkerBindingProof, query: str, *, expected_columns: tuple[str, ...]
    ) -> _AggregateQueryResult:
        try:
            lease = self._verified_lease(proof, _AGGREGATE_BINDING_OPERATIONS)
            final_columns = (
                _SCALAR_COLUMNS if lease.scope.operation == "sum_diff" else _SUMMARY_COLUMNS
            )
            if expected_columns not in (("type_check",), ("numeric_domain",), final_columns):
                raise _proof_error()
            return self._session._read_bound_aggregate(
                lease, lease.scope, query, expected_columns=expected_columns
            )
        except Exception:
            self._invalidated = True
            raise

    def close(self) -> tuple[Diagnostic, ...]:
        self._invalidated = True
        self._lease = None
        self._proof = None
        return self._session.close()
