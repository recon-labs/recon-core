"""Check-engine orchestration for loaded compiled checks."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from recon_core.adapters import BaseAdapter, SqlRenderer
from recon_core.artifacts import (
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
)
from recon_core.check_engine.dispatch import CheckDispatcher
from recon_core.check_engine.execution import execute_row_count_check
from recon_core.check_engine.models import (
    CheckReason,
    CheckResult,
    CheckStatus,
    ContractResult,
    RunResult,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

BLOCKED_BY_PREREQUISITE = "RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE"
CHECK_ENGINE_INTERNAL_ERROR = "RC_RUNTIME_CHECK_ENGINE_INTERNAL_ERROR"


class _Dispatcher(Protocol):
    def dispatch(self, check: LoadedCompiledCheck) -> CheckResult: ...


@dataclass(frozen=True, slots=True)
class CheckExecutionContext:
    """Prepared runtime dependencies that allow supported checks to execute."""

    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact]
    adapters_by_connection: Mapping[str, BaseAdapter]
    renderers_by_adapter_type: Mapping[str, SqlRenderer] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _PrerequisiteBlocker:
    check_id: str
    reason: CheckReason
    state: str


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

        blocked_result = self._blocked_result_if_needed(
            check,
            check_results_by_id,
            checks_by_id,
            active_check_ids=active_check_ids | {check.id},
            execution_context=execution_context,
        )
        if blocked_result is not None:
            check_results_by_id[check.id] = blocked_result
            return blocked_result

        try:
            dispatch_result = self._dispatcher.dispatch(check)
            result = (
                _row_count_execution_result_if_available(
                    check,
                    dispatch_result,
                    execution_context,
                )
                or dispatch_result
            )
        except Exception:
            result = _internal_error_result(check)

        check_results_by_id[check.id] = result
        return result

    def _blocked_result_if_needed(
        self,
        check: LoadedCompiledCheck,
        check_results_by_id: dict[str, CheckResult],
        checks_by_id: dict[str, LoadedCompiledCheck],
        *,
        active_check_ids: frozenset[str],
        execution_context: CheckExecutionContext | None,
    ) -> CheckResult | None:
        blockers: list[_PrerequisiteBlocker] = []
        for prerequisite_id in check.prerequisites:
            prerequisite_result = check_results_by_id.get(prerequisite_id)
            if prerequisite_result is None:
                prerequisite_check = checks_by_id.get(prerequisite_id)
                if prerequisite_check is None:
                    blockers.append(
                        _PrerequisiteBlocker(
                            check_id=prerequisite_id,
                            reason=CheckReason.PREREQUISITE_MISSING,
                            state="missing",
                        )
                    )
                    continue
                if prerequisite_id in active_check_ids:
                    return _internal_error_result(check)
                prerequisite_result = self._result_for_check(
                    prerequisite_check,
                    check_results_by_id,
                    checks_by_id,
                    active_check_ids=active_check_ids,
                    execution_context=execution_context,
                )
            if prerequisite_result.status is CheckStatus.FAIL:
                blockers.append(
                    _PrerequisiteBlocker(
                        check_id=prerequisite_id,
                        reason=CheckReason.PREREQUISITE_FAILED,
                        state="failed",
                    )
                )
            if prerequisite_result.status is CheckStatus.ERROR:
                blockers.append(
                    _PrerequisiteBlocker(
                        check_id=prerequisite_id,
                        reason=CheckReason.PREREQUISITE_ERROR,
                        state="errored",
                    )
                )
            if prerequisite_result.status is CheckStatus.BLOCKED:
                blockers.append(
                    _PrerequisiteBlocker(
                        check_id=prerequisite_id,
                        reason=_blocked_prerequisite_reason(prerequisite_result),
                        state="blocked",
                    )
                )
            if prerequisite_result.status is CheckStatus.NOT_EXECUTABLE:
                blockers.append(
                    _PrerequisiteBlocker(
                        check_id=prerequisite_id,
                        reason=CheckReason.PREREQUISITE_NOT_EXECUTABLE,
                        state="was not executable",
                    )
                )
        if blockers:
            return _blocked_result(
                check,
                reason=_dominant_blocker_reason(tuple(blockers)),
                blocked_by=_unique_blocked_by(tuple(blockers)),
                message=_blocked_message(check.name, tuple(blockers)),
            )
        return None


_DISPATCH_HARD_BLOCKING_REASONS = frozenset(
    {
        CheckReason.UNSUPPORTED_CHECK_TYPE,
        CheckReason.UNSUPPORTED_TYPED_OPERATION,
        CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
    }
)


def _row_count_execution_result_if_available(
    check: LoadedCompiledCheck,
    dispatch_result: CheckResult,
    execution_context: CheckExecutionContext | None,
) -> CheckResult | None:
    if execution_context is None:
        return None
    if check.check_type != "row_count_diff":
        return None
    if dispatch_result.status is not CheckStatus.NOT_EXECUTABLE:
        return None
    if dispatch_result.reason_code in _DISPATCH_HARD_BLOCKING_REASONS:
        return None

    contract = execution_context.contracts_by_name.get(check.contract_name)
    if contract is None:
        return None
    adapter = execution_context.adapters_by_connection.get(contract.source.connection)
    if adapter is None:
        return None

    renderer = _renderer_for_adapter(adapter, execution_context)
    return execute_row_count_check(check, contract, adapter, renderer=renderer)


def _renderer_for_adapter(
    adapter: BaseAdapter,
    execution_context: CheckExecutionContext,
) -> SqlRenderer | None:
    adapter_type = _safe_string_attribute(adapter, "adapter_type")
    if adapter_type is None:
        return None
    return execution_context.renderers_by_adapter_type.get(adapter_type)


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


def _blocked_result(
    check: LoadedCompiledCheck,
    *,
    reason: CheckReason,
    blocked_by: tuple[str, ...],
    message: str,
) -> CheckResult:
    diagnostic = Diagnostic(
        code=BLOCKED_BY_PREREQUISITE,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint="Inspect the prerequisite check result before this dependent check.",
    )
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.BLOCKED,
        executed=False,
        reason_code=reason,
        identity=_identity_label(check),
        message=message,
        blocked_by=blocked_by,
        diagnostics=check.diagnostics + (diagnostic,),
    )


def _blocked_prerequisite_reason(result: CheckResult) -> CheckReason:
    if result.reason_code in {
        CheckReason.PREREQUISITE_FAILED,
        CheckReason.PREREQUISITE_ERROR,
        CheckReason.PREREQUISITE_MISSING,
        CheckReason.PREREQUISITE_NOT_EXECUTABLE,
    }:
        return result.reason_code
    return CheckReason.PREREQUISITE_ERROR


def _dominant_blocker_reason(blockers: tuple[_PrerequisiteBlocker, ...]) -> CheckReason:
    for reason in (
        CheckReason.PREREQUISITE_ERROR,
        CheckReason.PREREQUISITE_FAILED,
        CheckReason.PREREQUISITE_NOT_EXECUTABLE,
        CheckReason.PREREQUISITE_MISSING,
    ):
        if any(blocker.reason is reason for blocker in blockers):
            return reason
    return CheckReason.PREREQUISITE_ERROR


def _unique_blocked_by(blockers: tuple[_PrerequisiteBlocker, ...]) -> tuple[str, ...]:
    blocked_by: list[str] = []
    seen: set[str] = set()
    for blocker in blockers:
        if blocker.check_id in seen:
            continue
        seen.add(blocker.check_id)
        blocked_by.append(blocker.check_id)
    return tuple(blocked_by)


def _blocked_message(check_name: str, blockers: tuple[_PrerequisiteBlocker, ...]) -> str:
    unique_blockers = _unique_blocked_by(blockers)
    if len(unique_blockers) == 1:
        blocker = blockers[0]
        return (
            f"Check `{check_name}` did not run because prerequisite "
            f"`{blocker.check_id}` {blocker.state}."
        )

    blocker_states = ", ".join(f"`{blocker.check_id}` {blocker.state}" for blocker in blockers)
    return f"Check `{check_name}` did not run because prerequisites {blocker_states}."


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


def _identity_label(check: LoadedCompiledCheck) -> str | None:
    payload = check.payload
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        return None
    kind = identity.get("kind")
    return kind if isinstance(kind, str) else None


def _safe_string_attribute(instance: object, attribute_name: str) -> str | None:
    try:
        value = getattr(instance, attribute_name)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None
