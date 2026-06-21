"""Prerequisite blocker support for check-engine orchestration."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from recon_core.artifacts import LoadedCompiledCheck
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.result_metadata import identity_label
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

BLOCKED_BY_PREREQUISITE = "RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE"

_ResolvePrerequisite = Callable[[LoadedCompiledCheck, frozenset[str]], CheckResult]
_CycleResultFactory = Callable[[LoadedCompiledCheck], CheckResult]


@dataclass(frozen=True, slots=True)
class _PrerequisiteBlocker:
    check_id: str
    reason: CheckReason
    state: str


def blocked_result_if_needed(
    check: LoadedCompiledCheck,
    check_results_by_id: Mapping[str, CheckResult],
    checks_by_id: Mapping[str, LoadedCompiledCheck],
    *,
    active_check_ids: frozenset[str],
    resolve_prerequisite: _ResolvePrerequisite,
    cycle_result_factory: _CycleResultFactory,
) -> CheckResult | None:
    """Return a dependent-check blocker when prerequisites are unsafe."""
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
                return cycle_result_factory(check)
            prerequisite_result = resolve_prerequisite(prerequisite_check, active_check_ids)

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
        identity=identity_label(check),
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
