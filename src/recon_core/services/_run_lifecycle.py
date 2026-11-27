"""Private run invocation state and finalized outcome; no output serialization."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from recon_core._run_control import _RunControl, _StopCause
from recon_core.adapters._project_binding import _NativeResourceFacts
from recon_core.artifacts import LoadedCompiledChecksArtifact
from recon_core.check_engine.models import CheckReason, RunResult
from recon_core.config._local_resource_policy import _ResourceSettingFact
from recon_core.services.results import ExitCategory, ServiceResult


class _RunStage(StrEnum):
    PROJECT_CONFIGURATION = "project_configuration"
    COMPILED_CHECKS = "compiled_checks"
    COMPILED_CONTRACTS = "compiled_contracts"
    RUNTIME_SETUP = "runtime_setup"
    CHECK_EXECUTION = "check_execution"
    RESULT_PROJECTION = "result_projection"


class _InvocationStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"


class _PlanScope(StrEnum):
    WHOLE_COMPILED = "whole_compiled"


@dataclass(frozen=True, slots=True)
class _PlannedCheck:
    check_id: str
    plan_id: str
    check_type: str
    prerequisites: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PlannedContract:
    contract_id: str
    contract_name: str
    project_version: str | None
    checks: tuple[_PlannedCheck, ...]


@dataclass(frozen=True, slots=True)
class _CompiledRunPlan:
    """Identity and order of validated loaded artifacts, not another execution graph."""

    project_name: str
    contracts: tuple[_PlannedContract, ...]
    scope: _PlanScope = _PlanScope.WHOLE_COMPILED

    @classmethod
    def from_artifacts(
        cls, project_name: str, artifacts: tuple[LoadedCompiledChecksArtifact, ...]
    ) -> "_CompiledRunPlan":
        return cls(
            project_name=project_name,
            contracts=tuple(
                _PlannedContract(
                    contract_id=artifact.contract_id,
                    contract_name=artifact.contract_name,
                    project_version=artifact.project_version,
                    checks=tuple(
                        _PlannedCheck(
                            check_id=check.id,
                            plan_id=check.plan.id,
                            check_type=check.check_type,
                            prerequisites=check.prerequisites,
                        )
                        for check in artifact.checks
                    ),
                )
                for artifact in artifacts
            ),
        )


@dataclass(frozen=True, slots=True)
class _RunScopeFacts:
    """Counts of retained result records, not proof of native execution attempts."""

    planned_contract_count: int | None
    planned_check_count: int | None
    finalized_check_count: int
    executed_check_count: int
    complete: bool | None

    @classmethod
    def from_result(
        cls,
        plan: _CompiledRunPlan | None,
        *,
        known_empty: bool,
        run_id: str,
        result: RunResult | None,
    ) -> "_RunScopeFacts":
        contracts = result.contract_results if result is not None else ()
        finalized = sum(len(contract.check_results) for contract in contracts)
        executed = sum(check.executed for contract in contracts for check in contract.check_results)
        if plan is None:
            return cls(None, 0 if known_empty else None, finalized, executed, None)

        complete = (
            result is not None
            and result.run_id == run_id
            and result.project_name == plan.project_name
            and _matches_plan(plan, result)
        )
        return cls(
            len(plan.contracts),
            sum(len(contract.checks) for contract in plan.contracts),
            finalized,
            executed,
            complete,
        )


def _matches_plan(plan: _CompiledRunPlan, result: RunResult) -> bool:
    if len(plan.contracts) != len(result.contract_results):
        return False
    for planned, actual in zip(plan.contracts, result.contract_results, strict=True):
        if planned.contract_name != actual.contract_name:
            return False
        if len(planned.checks) != len(actual.check_results):
            return False
        for expected, check in zip(planned.checks, actual.check_results, strict=True):
            if (
                expected.check_id != check.check_id
                or expected.check_type != check.check_type
                or planned.contract_name != check.contract_name
            ):
                return False
    return True


class _NativeAdmission(StrEnum):
    NOT_REACHED = "not_reached"
    REFUSED = "refused"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class _CheckResourceFacts:
    check_id: str
    preliminary_allowed: bool | None
    preliminary_reason: CheckReason | None
    source_policy: tuple[_ResourceSettingFact, ...] | None
    target_policy: tuple[_ResourceSettingFact, ...] | None
    admission: _NativeAdmission = _NativeAdmission.NOT_REACHED
    capability_admitted: bool | None = None
    native: _NativeResourceFacts | None = None


@dataclass(frozen=True, slots=True)
class _InvocationOutcome:
    run_id: str
    project_name: str | None
    started_at: str
    finished_at: str
    elapsed_ns: int
    stage: _RunStage
    status: _InvocationStatus
    service_result: ServiceResult
    plan: _CompiledRunPlan | None = field(repr=False)
    run_result: RunResult | None = field(repr=False)
    resource_facts: tuple[_CheckResourceFacts, ...] = field(repr=False)
    scope_facts: _RunScopeFacts
    stop_cause: _StopCause | None = None


@dataclass(slots=True)
class _RunInvocation:
    run_id: str
    started_at: str
    started_ns: int
    project_name: str | None = None
    stage: _RunStage = _RunStage.PROJECT_CONFIGURATION
    plan: _CompiledRunPlan | None = field(default=None, repr=False)
    resource_facts: dict[str, _CheckResourceFacts] = field(default_factory=dict, repr=False)
    known_empty_scope: bool = False
    scope_facts: _RunScopeFacts | None = None
    control: _RunControl | None = field(default=None, repr=False)

    def observe_stop(self) -> _StopCause | None:
        return self.control.observe() if self.control is not None else None

    def inspect_scope(self, result: RunResult | None) -> _RunScopeFacts:
        self.scope_facts = _RunScopeFacts.from_result(
            self.plan, known_empty=self.known_empty_scope, run_id=self.run_id, result=result
        )
        return self.scope_facts

    def finish(
        self,
        *,
        finished_at: str,
        finished_ns: int,
        service_result: ServiceResult,
        run_result: RunResult | None,
        stop_cause: _StopCause | None = None,
    ) -> _InvocationOutcome:
        if run_result is not None:
            assert self.project_name is not None
            run_result = replace(
                run_result,
                started_at=self.started_at,
                finished_at=finished_at,
            )
        # A trustworthy reconciliation mismatch is a completed invocation,
        # not an invocation failure. Command mapping remains with RunService.
        status = (
            _InvocationStatus.COMPLETED
            if run_result is not None
            and service_result.exit_category in {ExitCategory.SUCCESS, ExitCategory.CHECK_FAILURE}
            else _InvocationStatus.FAILED
        )
        return _InvocationOutcome(
            run_id=self.run_id,
            project_name=self.project_name,
            started_at=self.started_at,
            finished_at=finished_at,
            elapsed_ns=finished_ns - self.started_ns,
            stage=self.stage,
            status=status,
            service_result=service_result,
            plan=self.plan,
            run_result=run_result,
            resource_facts=tuple(self.resource_facts.values()),
            scope_facts=self.scope_facts or self.inspect_scope(run_result),
            stop_cause=stop_cause,
        )
