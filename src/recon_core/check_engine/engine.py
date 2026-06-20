"""Check-engine orchestration for loaded compiled checks."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from recon_core.adapters import BaseAdapter, ConnectionConfig, SqlRenderer
from recon_core.artifacts import (
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
)
from recon_core.check_engine import prerequisites as _prerequisites
from recon_core.check_engine.dispatch import CheckDispatcher
from recon_core.check_engine.models import (
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
        finished_at: str,
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
                    active_check_ids=frozenset(),
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
            finished_at=finished_at,
            contract_results=tuple(contract_results),
            diagnostics=tuple(run_diagnostics),
        )

    def _result_for_check(
        self,
        check: LoadedCompiledCheck,
        check_results_by_id: dict[str, CheckResult],
        checks_by_id: dict[str, LoadedCompiledCheck],
        active_check_ids: frozenset[str],
        execution_context: CheckExecutionContext | None,
    ) -> CheckResult:
        existing_result = check_results_by_id.get(check.id)
        if existing_result is not None:
            return existing_result

        def resolve_prerequisite(
            prerequisite_check: LoadedCompiledCheck,
            prerequisite_active_check_ids: frozenset[str],
        ) -> CheckResult:
            return self._result_for_check(
                prerequisite_check,
                check_results_by_id,
                checks_by_id,
                active_check_ids=prerequisite_active_check_ids,
                execution_context=execution_context,
            )

        blocked_result = blocked_result_if_needed(
            check,
            check_results_by_id,
            checks_by_id,
            active_check_ids=active_check_ids | {check.id},
            resolve_prerequisite=resolve_prerequisite,
            cycle_result_factory=_internal_error_result,
        )
        if blocked_result is not None:
            check_results_by_id[check.id] = blocked_result
            return blocked_result

        rendering_blocked_result = rendering_blocked_result_if_needed(check)
        if rendering_blocked_result is not None:
            check_results_by_id[check.id] = rendering_blocked_result
            return rendering_blocked_result

        try:
            dispatch_result = self._dispatcher.dispatch(check)
            result = runtime_execution_result_if_available(
                check,
                dispatch_result,
                execution_context,
            ) or dispatch_result
        except Exception:
            result = _internal_error_result(check)

        check_results_by_id[check.id] = result
        return result


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
