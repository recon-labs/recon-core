"""Check-engine orchestration for loaded compiled checks."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from recon_core._run_control import _RunControl, _StopCause
from recon_core.adapters import BaseAdapter, ConnectionConfig, SqlRenderer
from recon_core.adapters._aggregate_runtime import _AggregateRuntimeRenderer
from recon_core.artifacts import (
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
)
from recon_core.artifacts.compiled_contract_loader import _ToleranceReferenceState
from recon_core.check_engine import prerequisites as _prerequisites
from recon_core.check_engine._bound_protocol import _BoundRunner
from recon_core.check_engine.dispatch import CheckDispatcher
from recon_core.check_engine.models import (
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)
from recon_core.check_engine.prerequisites import (
    blocked_result_if_needed,
)
from recon_core.check_engine.runtime import (
    RuntimeExecutionContext,
    rendering_blocked_result_if_needed,
    runtime_execution_result_if_available,
)
from recon_core.check_engine.scan_budget import ScanBudgetDecision
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

BLOCKED_BY_PREREQUISITE = _prerequisites.BLOCKED_BY_PREREQUISITE
CHECK_ENGINE_INTERNAL_ERROR = "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"


class _Dispatcher(Protocol):
    def dispatch(self, check: LoadedCompiledCheck) -> CheckResult: ...


@dataclass(frozen=True, slots=True)
class CheckExecutionContext(RuntimeExecutionContext):
    """Prepared runtime dependencies that allow supported checks to execute."""

    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact]
    adapters_by_connection: Mapping[str, BaseAdapter]
    connections_by_name: Mapping[str, ConnectionConfig] = field(default_factory=dict)
    renderers_by_adapter_type: Mapping[str, SqlRenderer] = field(default_factory=dict)
    scan_budget_decisions_by_check_id: Mapping[str, ScanBudgetDecision] = field(
        default_factory=dict
    )
    _run_control: _RunControl | None = field(default=None, repr=False, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class _AggregateExecutionContext(CheckExecutionContext):
    tolerance_states_by_contract_id: Mapping[str, _ToleranceReferenceState] = field(
        default_factory=dict
    )
    aggregate_blockers_by_check_id: Mapping[str, CheckResult] = field(default_factory=dict)
    aggregate_renderers_by_adapter_type: Mapping[str, _AggregateRuntimeRenderer] = field(
        default_factory=dict
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class _ProjectExecutionContext(_AggregateExecutionContext):
    _bound_runner: _BoundRunner


class CheckEngine:
    """Build in-memory run results from loaded compiled checks."""

    def __init__(self, dispatcher: _Dispatcher | None = None) -> None:
        self._dispatcher = dispatcher if dispatcher is not None else CheckDispatcher()

    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str | None,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult:
        resolved_project_name = _project_name(artifacts, project_name)
        checks_by_id = _index_checks(artifacts)
        check_results_by_id: dict[str, CheckResult] = {}
        contract_results: list[ContractResult] = []
        run_diagnostics: list[Diagnostic] = []

        for artifact in artifacts:
            run_diagnostics.extend(artifact.diagnostics)
            contract_check_results = tuple(
                self._result_for_check(
                    check,
                    check_results_by_id,
                    checks_by_id,
                    execution_context=execution_context,
                )
                for check in artifact.checks
            )
            contract_results.append(
                ContractResult.from_check_results(
                    contract_name=artifact.contract_name,
                    check_results=contract_check_results,
                    diagnostics=artifact.diagnostics,
                )
            )

        return RunResult.from_contract_results(
            run_id=run_id,
            project_name=resolved_project_name,
            started_at=started_at,
            finished_at=(
                finished_at
                if finished_at is not None
                else datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
            ),
            contract_results=tuple(contract_results),
            diagnostics=tuple(run_diagnostics),
        )

    def _result_for_check(
        self,
        check: LoadedCompiledCheck,
        check_results_by_id: dict[str, CheckResult],
        checks_by_id: dict[str, LoadedCompiledCheck],
        execution_context: CheckExecutionContext | None,
    ) -> CheckResult:
        if check.id in check_results_by_id:
            return check_results_by_id[check.id]

        # Depth-first evaluation uses the existing index and result cache.
        # An explicit stack avoids an interpreter-dependent depth limit.
        pending: list[tuple[LoadedCompiledCheck, Iterator[str]]] = [
            (check, iter(check.prerequisites))
        ]
        active_check_ids = {check.id}
        while pending:
            current, prerequisites = pending[-1]
            cause = _observe_stop(execution_context)
            prerequisite_id = next(prerequisites, None) if cause is None else None
            if cause is not None:
                result = _stopped_check_result(current, cause)
            elif prerequisite_id is None:
                result = self._evaluate_ready_check(current, check_results_by_id, execution_context)
            elif prerequisite_id in check_results_by_id:
                continue
            elif prerequisite_id in active_check_ids:
                result = _internal_error_result(current)
            else:
                prerequisite = checks_by_id.get(prerequisite_id)
                if prerequisite is None:
                    # The existing blocker policy reports missing prerequisites.
                    continue
                active_check_ids.add(prerequisite_id)
                pending.append((prerequisite, iter(prerequisite.prerequisites)))
                continue

            check_results_by_id[current.id] = result
            active_check_ids.remove(current.id)
            pending.pop()

        return check_results_by_id[check.id]

    def _evaluate_ready_check(
        self,
        check: LoadedCompiledCheck,
        check_results_by_id: Mapping[str, CheckResult],
        execution_context: CheckExecutionContext | None,
    ) -> CheckResult:
        if (cause := _observe_stop(execution_context)) is not None:
            return _stopped_check_result(check, cause)
        blocked_result = blocked_result_if_needed(check, check_results_by_id)
        if blocked_result is not None:
            return blocked_result

        rendering_blocked_result = rendering_blocked_result_if_needed(check)
        if rendering_blocked_result is not None:
            return rendering_blocked_result

        try:
            dispatch_result = self._dispatcher.dispatch(check)
            if (cause := _observe_stop(execution_context)) is not None:
                if dispatch_result.executed:
                    return dispatch_result
                return _stopped_check_result(check, cause)
            return (
                runtime_execution_result_if_available(
                    check,
                    dispatch_result,
                    execution_context,
                )
                or dispatch_result
            )
        except Exception:
            return _internal_error_result(check)


def _observe_stop(context: CheckExecutionContext | None) -> _StopCause | None:
    if context is None or context._run_control is None:
        return None
    return context._run_control.observe()


def _stopped_check_result(check: LoadedCompiledCheck, cause: _StopCause) -> CheckResult:
    diagnostic = cause.diagnostic()
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.NOT_EXECUTABLE,
        reason_code=CheckReason(cause.value),
        message=diagnostic.message,
        diagnostics=check.diagnostics + (diagnostic,),
    )


def _index_checks(
    artifacts: tuple[LoadedCompiledChecksArtifact, ...],
) -> dict[str, LoadedCompiledCheck]:
    return {check.id: check for artifact in artifacts for check in artifact.checks}


def _project_name(
    artifacts: tuple[LoadedCompiledChecksArtifact, ...],
    explicit_project_name: str | None,
) -> str:
    if explicit_project_name is not None:
        return explicit_project_name
    if artifacts:
        return artifacts[0].project_name
    return "unknown"


def _internal_error_result(check: LoadedCompiledCheck) -> CheckResult:
    message = "Check engine internal error occurred before a trustworthy result was produced."
    diagnostic = Diagnostic(
        code=CHECK_ENGINE_INTERNAL_ERROR,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint="Retry the command or inspect Recon Core logs if available.",
    )
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.ERROR,
        executed=False,
        message=message,
        diagnostics=check.diagnostics + (diagnostic,),
    )
