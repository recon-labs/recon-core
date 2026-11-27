"""Private project-run orchestration of one owned native session per check."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters._project_binding import (
    _MAX_BOUNDED_LOCAL_DUCKDB_BYTES,
    _BindingLease,
    _BoundSessionError,
    _InvalidAggregateResultError,
    _local_file_identity,
    _LocalFileIdentity,
    _new_owned_session,
    _OwnedSession,
)
from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.lifecycle import ADAPTER_QUERY_FAILED
from recon_core.adapters.models import QueryResult
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.check_engine._bound_protocol import _BoundEvaluation
from recon_core.check_engine.execution_support import (
    adapter_matches_connection,
    error_result,
    not_executable_result,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.scan_budget import BOUNDED_LOCAL_SCAN_REQUIRED, SCAN_BUDGET_EXCEEDED
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig


class _SessionReader:
    def __init__(self, session: _OwnedSession, lease: _BindingLease) -> None:
        self._session = session
        self._lease = lease

    def execute(self, query: str) -> QueryResult:
        return self._session._read_bound_query(self._lease, self._lease.scope, query)

    def _execute_aggregate_query(
        self, query: str, *, expected_columns: tuple[str, ...]
    ) -> _AggregateQueryResult:
        return self._session._read_bound_aggregate(
            self._lease, self._lease.scope, query, expected_columns=expected_columns
        )


def _scope_refusal(
    check: LoadedCompiledCheck, contract: LoadedCompiledContractArtifact, *, over_cap: bool = False
) -> CheckResult:
    return not_executable_result(
        check,
        contract,
        reason=(
            CheckReason.SCAN_BUDGET_EXCEEDED
            if over_cap
            else CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED
        ),
        diagnostic_code=SCAN_BUDGET_EXCEEDED if over_cap else BOUNDED_LOCAL_SCAN_REQUIRED,
        message=(
            "Check exceeds the temporary local file limit."
            if over_cap
            else "Check requires a verified local base-table execution scope."
        ),
        hint="Verify the local database and supported base-table relations.",
    )


def _safe_error(
    check: LoadedCompiledCheck, contract: LoadedCompiledContractArtifact, code: str, message: str
) -> CheckResult:
    return error_result(
        check,
        contract,
        message=message,
        diagnostics=(Diagnostic(code=code, severity=DiagnosticSeverity.ERROR, message=message),),
    )


class _ProjectBoundRunner:
    """Run-local cleanup latch; no adapter connection is borrowed or reused."""

    def __init__(
        self,
        project_root: Path,
        connections: Mapping[str, ConnectionConfig],
        identities: Mapping[str, _LocalFileIdentity],
    ) -> None:
        self._root = project_root
        self._connections = deepcopy(dict(connections))
        self._identities = dict(identities)
        self._unreleased: list[tuple[_LocalFileIdentity, _OwnedSession]] = []
        self._session_count = 0

    def run(
        self,
        check: LoadedCompiledCheck,
        contract: LoadedCompiledContractArtifact,
        adapter: BaseAdapter,
        evaluate: _BoundEvaluation,
    ) -> CheckResult:
        source = self._connections.get(contract.source.connection)
        target = self._connections.get(contract.target.connection)
        if (
            source is None
            or target is None
            or source.type != "duckdb"
            or source.type != target.type
            or source.config != target.config
            or not adapter_matches_connection(adapter, source)
        ):
            return not_executable_result(
                check,
                contract,
                reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
                diagnostic_code="RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED",
                message="Check requires one verified adapter connection context.",
                hint="Use matching supported connection configurations.",
            )
        identity = self._identities.get(check.id)
        if identity is None:
            return _scope_refusal(check, contract)
        if check.check_type != "row_count_diff" and identity.size > _MAX_BOUNDED_LOCAL_DUCKDB_BYTES:
            return _scope_refusal(check, contract, over_cap=True)
        if any(
            failed.path == identity.path
            or (failed.device, failed.inode) == (identity.device, identity.inode)
            for failed, _ in self._unreleased
        ):
            return _safe_error(
                check,
                contract,
                "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE",
                "Execution context unavailable because prior session cleanup could not be confirmed.",
            )
        if _local_file_identity(source, self._root) != identity:
            return _safe_error(
                check,
                contract,
                "RC_RUNTIME_BINDING_PROOF_FAILED",
                "Execution binding could not be verified.",
            )
        if contract.source.relation is None or contract.target.relation is None:
            return _scope_refusal(check, contract)
        self._session_count += 1
        session_number = self._session_count
        session = _new_owned_session(source.type, identity)
        try:
            session.open()
            lease = session.bind(
                check_id=check.id,
                operation=check.check_type,
                source=contract.source.relation,
                target=contract.target.relation,
            )
            if lease is None:
                result = _scope_refusal(check, contract)
            else:
                result = evaluate(
                    lease.scope.source, lease.scope.target, _SessionReader(session, lease)
                )
        except _BoundSessionError as exc:
            result = error_result(
                check, contract, message=exc.diagnostic.message, diagnostics=(exc.diagnostic,)
            )
        except _InvalidAggregateResultError:
            result = _safe_error(
                check,
                contract,
                "RC_RUNTIME_AGGREGATE_RESULT_INVALID",
                "Aggregate runtime returned invalid numeric evidence.",
            )
        except Exception:
            result = _safe_error(
                check,
                contract,
                ADAPTER_QUERY_FAILED,
                "Native execution failed before a trustworthy result was produced.",
            )
        finally:
            cleanup = session.close()
            if not session.released:
                self._unreleased.append((identity, session))

        # Preserve distinct fixed, non-identifying per-session diagnostics across
        # the service's diagnostic deduplication boundary.
        def attribute(diagnostic: Diagnostic) -> Diagnostic:
            return replace(diagnostic, hint=f"Native session #{session_number}: inspect locally.")

        if result.status is CheckStatus.ERROR:
            result = replace(
                result,
                diagnostics=tuple(
                    attribute(diagnostic)
                    if diagnostic.code
                    in {
                        ADAPTER_QUERY_FAILED,
                        "RC_ADAPTER_CONNECTION_FAILED",
                        "RC_RUNTIME_BINDING_PROOF_FAILED",
                    }
                    else diagnostic
                    for diagnostic in result.diagnostics
                ),
            )
        if not cleanup:
            return result
        cleanup = tuple(attribute(diagnostic) for diagnostic in cleanup)
        primary = result.diagnostics
        if result.status is CheckStatus.FAIL:
            primary += (
                Diagnostic(
                    code=ADAPTER_QUERY_FAILED,
                    severity=DiagnosticSeverity.ERROR,
                    message="Check evaluated to a failing outcome before cleanup failed.",
                ),
            )
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=CheckStatus.ERROR,
            identity=result.identity,
            message="Check failed during read-only execution cleanup.",
            diagnostics=primary + cleanup,
        )
