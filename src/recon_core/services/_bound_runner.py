"""Private project-run orchestration of one owned native session per check."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from recon_core._run_control import _RunControl, _RunStoppedError
from recon_core.adapters._aggregate_runtime import _AggregateQueryResult
from recon_core.adapters._project_binding import (
    _BindingLease,
    _BoundSessionError,
    _exceeds_authored_footprint,
    _InvalidAggregateResultError,
    _local_file_identity,
    _LocalFileIdentity,
    _new_owned_session,
    _normalize_owned_resource_policy,
    _OwnedSession,
)
from recon_core.adapters.base import BaseAdapter
from recon_core.adapters.lifecycle import ADAPTER_CLOSE_FAILED, ADAPTER_QUERY_FAILED
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
from recon_core.config._local_resource_policy import _LocalResourcePolicy
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import ConnectionConfig
from recon_core.services._run_lifecycle import (
    _CheckResourceFacts,
    _ExecutionLedger,
    _NativeAdmission,
)


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
            "Check exceeds the configured database footprint limit."
            if over_cap
            else "Check requires a verified local base-table execution scope."
        ),
        hint=(
            "Reduce the database footprint or adjust max-database-mib."
            if over_cap
            else "Verify the local database and supported base-table relations."
        ),
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
        resource_policies: Mapping[str, _LocalResourcePolicy],
        resource_facts: dict[str, _CheckResourceFacts],
        *,
        control: _RunControl | None = None,
        execution_ledger: _ExecutionLedger | None = None,
    ) -> None:
        self._root = project_root
        self._connections = deepcopy(dict(connections))
        self._identities = dict(identities)
        self._resource_policies = dict(resource_policies)
        self._resource_facts = resource_facts
        self._control = control
        self._execution_ledger = (
            execution_ledger if execution_ledger is not None else _ExecutionLedger()
        )
        self._unreleased: list[tuple[_LocalFileIdentity, _OwnedSession]] = []
        self._session_count = 0

    def run(
        self,
        check: LoadedCompiledCheck,
        contract: LoadedCompiledContractArtifact,
        adapter: BaseAdapter,
        evaluate: _BoundEvaluation,
    ) -> CheckResult:
        facts = self._resource_facts.get(check.id)
        if facts is None:
            facts = _CheckResourceFacts(check.id, None, None, None, None)
        self._resource_facts[check.id] = replace(
            facts, admission=_NativeAdmission.UNVERIFIED, capability_admitted=True
        )
        result = self._run_bound_check(check, contract, adapter, evaluate)
        facts = self._resource_facts[check.id]
        if (
            result.status is CheckStatus.NOT_EXECUTABLE
            and facts.admission is not _NativeAdmission.VERIFIED
        ):
            self._resource_facts[check.id] = replace(facts, admission=_NativeAdmission.REFUSED)
        return result

    def _run_bound_check(
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
        if any(
            failed.path == identity.path
            or (failed.device, failed.inode) == (identity.device, identity.inode)
            for failed, _ in self._unreleased
        ):
            return _safe_error(
                check,
                contract,
                "RC_RUNTIME_EXECUTION_CONTEXT_UNAVAILABLE",
                "Execution context unavailable because prior cleanup could not be confirmed.",
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
        source_policy = self._resource_policies.get(
            contract.source.connection, _LocalResourcePolicy()
        )
        target_policy = self._resource_policies.get(
            contract.target.connection, _LocalResourcePolicy()
        )
        if source_policy != target_policy:
            try:
                source_policy = _normalize_owned_resource_policy(
                    source.type, self._root, source_policy
                )
                target_policy = _normalize_owned_resource_policy(
                    target.type, self._root, target_policy
                )
            except _BoundSessionError as exc:
                return not_executable_result(
                    check,
                    contract,
                    reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
                    diagnostic_code=exc.diagnostic.code,
                    message=exc.diagnostic.message,
                    hint="Inspect the selected resource settings locally.",
                )
        if source_policy != target_policy:
            return not_executable_result(
                check,
                contract,
                reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
                diagnostic_code="RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE",
                message="Connection aliases require matching execution policies.",
                hint="Align the selected connection execution settings.",
            )
        if _exceeds_authored_footprint(identity, source_policy):
            return _scope_refusal(check, contract, over_cap=True)
        if self._control is not None and (cause := self._control.observe()) is not None:
            diagnostic = cause.diagnostic()
            return not_executable_result(
                check,
                contract,
                reason=CheckReason(cause.value),
                diagnostic_code=diagnostic.code,
                message=diagnostic.message,
                hint=diagnostic.hint or "Start a new invocation when ready.",
            )
        self._session_count += 1
        session_number = self._session_count
        session = _new_owned_session(
            source.type, identity, project_root=self._root, resource_policy=source_policy
        )
        binding_verified = False
        attempted = False
        try:
            if self._control is not None:
                session._set_run_control(self._control)
                self._control.checkpoint()
            self._execution_ledger.begin()
            attempted = True
            session.open()
            if self._control is not None:
                self._control.checkpoint()
            lease = session.bind(
                check_id=check.id,
                operation=check.check_type,
                source=contract.source.relation,
                target=contract.target.relation,
            )
            if self._control is not None:
                self._control.checkpoint()
            if lease is None:
                result = _scope_refusal(check, contract)
            else:
                binding_verified = True
                result = evaluate(
                    lease.scope.source, lease.scope.target, _SessionReader(session, lease)
                )
        except _RunStoppedError as exc:
            diagnostic = exc.cause.diagnostic()
            result = error_result(
                check, contract, message=diagnostic.message, diagnostics=(diagnostic,)
            )
        except _BoundSessionError as exc:
            if exc.diagnostic.code == "RC_RUNTIME_RESOURCE_CONTROL_UNAVAILABLE":
                result = not_executable_result(
                    check,
                    contract,
                    reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
                    diagnostic_code=exc.diagnostic.code,
                    message=exc.diagnostic.message,
                    hint="Inspect the selected resource settings locally.",
                )
            else:
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
            try:
                cleanup = self._close_owned_session(session, identity)
                self._resource_facts[check.id] = replace(
                    self._resource_facts[check.id],
                    admission=(
                        _NativeAdmission.VERIFIED
                        if binding_verified
                        else _NativeAdmission.UNVERIFIED
                    ),
                    native=session.resource_facts,
                )
            finally:
                if attempted:
                    self._execution_ledger.end()

        if self._control is not None and not result.executed:
            cause = self._control.observe()
            if cause is not None:
                diagnostic = cause.diagnostic()
                if diagnostic not in result.diagnostics:
                    result = replace(result, diagnostics=result.diagnostics + (diagnostic,))

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
        if session.advisories:
            result = replace(result, diagnostics=result.diagnostics + session.advisories)
        if not cleanup:
            return result
        cleanup = tuple(attribute(diagnostic) for diagnostic in cleanup)
        primary = result.diagnostics
        if result.status is CheckStatus.FAIL:
            primary += (
                attribute(
                    Diagnostic(
                        code="RC_RUNTIME_CHECK_FAILURE_BEFORE_CLEANUP",
                        severity=DiagnosticSeverity.ERROR,
                        message="Check evaluated to a failing outcome before cleanup failed.",
                    )
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

    def _close_owned_session(
        self, session: _OwnedSession, identity: _LocalFileIdentity
    ) -> tuple[Diagnostic, ...]:
        cleanup: tuple[Diagnostic, ...] = ()
        cleanup_raised = False
        try:
            cleanup = session.close()
            released = session.released
        except Exception:
            # A close/release exception is not proof that native resources were released.
            released = False
            cleanup_raised = True
        if not released:
            self._unreleased.append((identity, session))
            if cleanup_raised or not cleanup:
                cleanup += (
                    Diagnostic(
                        code=ADAPTER_CLOSE_FAILED,
                        severity=DiagnosticSeverity.ERROR,
                        message="Native execution cleanup could not be confirmed.",
                    ),
                )
        return cleanup
