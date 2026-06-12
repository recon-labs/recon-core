"""In-memory result models for the first check-engine boundary."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Self, TypedDict

from recon_core.diagnostics import Diagnostic, DiagnosticDict


class CheckStatus(StrEnum):
    """Per-check reconciliation status values."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    NOT_EXECUTABLE = "not_executable"


class RunStatus(StrEnum):
    """Aggregate run and contract status values."""

    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    ERROR = "error"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    NOT_EXECUTABLE = "not_executable"
    NO_CHECKS = "no_checks"


class CheckReason(StrEnum):
    """Machine-readable reasons for non-executed check results."""

    PREREQUISITE_FAILED = "prerequisite_failed"
    PREREQUISITE_ERROR = "prerequisite_error"
    PREREQUISITE_MISSING = "prerequisite_missing"
    PREREQUISITE_NOT_EXECUTABLE = "prerequisite_not_executable"
    UNSUPPORTED_CHECK_TYPE = "unsupported_check_type"
    UNSUPPORTED_TYPED_OPERATION = "unsupported_typed_operation"
    MISSING_ENGINE_CAPABILITY = "missing_engine_capability"
    UNSUPPORTED_EXECUTION_PLACEMENT = "unsupported_execution_placement"
    UNSUPPORTED_MATERIALIZATION_POLICY = "unsupported_materialization_policy"
    NOT_IMPLEMENTED_IN_CURRENT_PHASE = "not_implemented_in_current_phase"
    SKIPPED_BY_POLICY = "skipped_by_policy"
    SELECTED_OUT = "selected_out"


class CheckResultDict(TypedDict):
    check_id: str
    name: str
    check_type: str
    contract_name: str
    status: str
    severity: str
    executed: bool
    reason_code: str | None
    identity: str | None
    message: str | None
    source_value: object | None
    target_value: object | None
    normalized_source_value: object | None
    normalized_target_value: object | None
    diff_value: object | None
    tolerance: object | None
    nulls: object | None
    normalization: object | None
    failure_count: int | None
    blocked_by: list[str]
    artifact_refs: list[object]
    sink_refs: list[object]
    diagnostics: list[DiagnosticDict]


class ContractResultDict(TypedDict):
    contract_name: str
    status: str
    check_results: list[CheckResultDict]
    diagnostics: list[DiagnosticDict]


class RunResultDict(TypedDict):
    run_id: str
    project_name: str
    started_at: str
    finished_at: str
    status: str
    contract_results: list[ContractResultDict]
    diagnostics: list[DiagnosticDict]
    artifact_refs: list[object]
    sink_refs: list[object]


_REASON_REQUIRED_STATUS: dict[CheckReason, CheckStatus] = {
    CheckReason.PREREQUISITE_FAILED: CheckStatus.BLOCKED,
    CheckReason.PREREQUISITE_ERROR: CheckStatus.BLOCKED,
    CheckReason.PREREQUISITE_MISSING: CheckStatus.BLOCKED,
    CheckReason.PREREQUISITE_NOT_EXECUTABLE: CheckStatus.BLOCKED,
    CheckReason.UNSUPPORTED_CHECK_TYPE: CheckStatus.NOT_EXECUTABLE,
    CheckReason.UNSUPPORTED_TYPED_OPERATION: CheckStatus.NOT_EXECUTABLE,
    CheckReason.MISSING_ENGINE_CAPABILITY: CheckStatus.NOT_EXECUTABLE,
    CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT: CheckStatus.NOT_EXECUTABLE,
    CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY: CheckStatus.NOT_EXECUTABLE,
    CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE: CheckStatus.NOT_EXECUTABLE,
    CheckReason.SKIPPED_BY_POLICY: CheckStatus.SKIPPED,
    CheckReason.SELECTED_OUT: CheckStatus.SKIPPED,
}

_EXECUTED_OUTCOME_STATUSES = {
    CheckStatus.PASS,
    CheckStatus.FAIL,
    CheckStatus.WARN,
}

_NON_EXECUTED_REASON_STATUSES = {
    CheckStatus.SKIPPED,
    CheckStatus.BLOCKED,
    CheckStatus.NOT_EXECUTABLE,
}

_CHECK_TO_RUN_STATUS: dict[CheckStatus, RunStatus] = {
    CheckStatus.PASS: RunStatus.PASS,
    CheckStatus.FAIL: RunStatus.FAIL,
    CheckStatus.WARN: RunStatus.WARN,
    CheckStatus.ERROR: RunStatus.ERROR,
    CheckStatus.SKIPPED: RunStatus.SKIPPED,
    CheckStatus.BLOCKED: RunStatus.BLOCKED,
    CheckStatus.NOT_EXECUTABLE: RunStatus.NOT_EXECUTABLE,
}

_AGGREGATE_PRECEDENCE = (
    RunStatus.ERROR,
    RunStatus.FAIL,
    RunStatus.BLOCKED,
    RunStatus.NOT_EXECUTABLE,
    RunStatus.WARN,
    RunStatus.PASS,
    RunStatus.SKIPPED,
)


@dataclass(frozen=True, slots=True)
class CheckResult:
    """In-memory outcome for one compiled check."""

    check_id: str
    name: str
    check_type: str
    contract_name: str
    status: CheckStatus
    severity: str = "error"
    executed: bool = False
    reason_code: CheckReason | None = None
    identity: str | None = None
    message: str | None = None
    source_value: object | None = None
    target_value: object | None = None
    normalized_source_value: object | None = None
    normalized_target_value: object | None = None
    diff_value: object | None = None
    tolerance: object | None = None
    nulls: object | None = None
    normalization: object | None = None
    failure_count: int | None = None
    blocked_by: tuple[str, ...] = ()
    artifact_refs: tuple[object, ...] = ()
    sink_refs: tuple[object, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        self._validate_status_execution()
        self._validate_reason()
        self._validate_blockers()
        self._validate_non_executed_explanation()
        self._validate_non_executed_payload()

    def to_dict(self) -> CheckResultDict:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "check_type": self.check_type,
            "contract_name": self.contract_name,
            "status": self.status.value,
            "severity": self.severity,
            "executed": self.executed,
            "reason_code": self.reason_code.value if self.reason_code else None,
            "identity": self.identity,
            "message": self.message,
            "source_value": self.source_value,
            "target_value": self.target_value,
            "normalized_source_value": self.normalized_source_value,
            "normalized_target_value": self.normalized_target_value,
            "diff_value": self.diff_value,
            "tolerance": self.tolerance,
            "nulls": self.nulls,
            "normalization": self.normalization,
            "failure_count": self.failure_count,
            "blocked_by": list(self.blocked_by),
            "artifact_refs": list(self.artifact_refs),
            "sink_refs": list(self.sink_refs),
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }

    def _validate_status_execution(self) -> None:
        if self.status in _EXECUTED_OUTCOME_STATUSES and not self.executed:
            raise ValueError(f"{self.status.value} result requires executed=True")
        if self.status in _NON_EXECUTED_REASON_STATUSES and self.executed:
            raise ValueError(f"{self.status.value} result requires executed=False")

    def _validate_reason(self) -> None:
        if self.status in _NON_EXECUTED_REASON_STATUSES and self.reason_code is None:
            raise ValueError(f"{self.status.value} result requires a reason_code")
        if self.reason_code is None:
            return

        expected_status = _REASON_REQUIRED_STATUS[self.reason_code]
        if self.status is not expected_status:
            raise ValueError(f"{self.reason_code.value} requires status {expected_status.value}")

    def _validate_blockers(self) -> None:
        if self.status is CheckStatus.BLOCKED and not self.blocked_by:
            raise ValueError("blocked result requires blocked_by")
        if self.status is not CheckStatus.BLOCKED and self.blocked_by:
            raise ValueError("blocked_by is only valid for blocked results")

    def _validate_non_executed_explanation(self) -> None:
        if self.status not in _NON_EXECUTED_REASON_STATUSES:
            return
        if not self.message:
            raise ValueError(f"{self.status.value} result requires a message")
        if not self.diagnostics:
            raise ValueError(f"{self.status.value} result requires diagnostics")

    def _validate_non_executed_payload(self) -> None:
        if self.executed:
            return
        if any(
            value is not None
            for value in (
                self.source_value,
                self.target_value,
                self.normalized_source_value,
                self.normalized_target_value,
                self.diff_value,
                self.failure_count,
            )
        ):
            raise ValueError("non-executed result cannot include value fields")
        if self.artifact_refs or self.sink_refs:
            raise ValueError("non-executed result cannot include output refs")


@dataclass(frozen=True, slots=True)
class ContractResult:
    """In-memory aggregate result for one contract."""

    contract_name: str
    status: RunStatus
    check_results: tuple[CheckResult, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @classmethod
    def from_check_results(
        cls,
        *,
        contract_name: str,
        check_results: tuple[CheckResult, ...],
        diagnostics: tuple[Diagnostic, ...] = (),
    ) -> Self:
        return cls(
            contract_name=contract_name,
            status=aggregate_check_status(check_results),
            check_results=check_results,
            diagnostics=diagnostics,
        )

    def to_dict(self) -> ContractResultDict:
        return {
            "contract_name": self.contract_name,
            "status": self.status.value,
            "check_results": [result.to_dict() for result in self.check_results],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }


@dataclass(frozen=True, slots=True)
class RunResult:
    """In-memory aggregate result for one run invocation."""

    run_id: str
    project_name: str
    started_at: str
    finished_at: str
    status: RunStatus
    contract_results: tuple[ContractResult, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    artifact_refs: tuple[object, ...] = ()
    sink_refs: tuple[object, ...] = ()

    @classmethod
    def from_contract_results(
        cls,
        *,
        run_id: str,
        project_name: str,
        started_at: str,
        finished_at: str,
        contract_results: tuple[ContractResult, ...],
        diagnostics: tuple[Diagnostic, ...] = (),
    ) -> Self:
        return cls(
            run_id=run_id,
            project_name=project_name,
            started_at=started_at,
            finished_at=finished_at,
            status=aggregate_contract_status(contract_results),
            contract_results=contract_results,
            diagnostics=diagnostics,
        )

    def to_dict(self) -> RunResultDict:
        return {
            "run_id": self.run_id,
            "project_name": self.project_name,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status.value,
            "contract_results": [result.to_dict() for result in self.contract_results],
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
            "artifact_refs": list(self.artifact_refs),
            "sink_refs": list(self.sink_refs),
        }


def aggregate_check_status(results: Iterable[CheckResult]) -> RunStatus:
    """Aggregate check results to a contract/run status without hiding non-pass states."""

    statuses = tuple(_CHECK_TO_RUN_STATUS[result.status] for result in results)
    return _aggregate_statuses(statuses)


def aggregate_contract_status(results: Iterable[ContractResult]) -> RunStatus:
    """Aggregate contract results to a run status."""

    statuses = tuple(result.status for result in results)
    return _aggregate_statuses(statuses)


def _aggregate_statuses(statuses: tuple[RunStatus, ...]) -> RunStatus:
    if not statuses:
        return RunStatus.NO_CHECKS
    if all(status is RunStatus.NO_CHECKS for status in statuses):
        return RunStatus.NO_CHECKS

    non_empty_statuses = tuple(status for status in statuses if status is not RunStatus.NO_CHECKS)
    for status in _AGGREGATE_PRECEDENCE:
        if status in non_empty_statuses:
            return status

    return RunStatus.NO_CHECKS
