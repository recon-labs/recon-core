"""Private run invocation state and finalized outcome; no output serialization."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from recon_core.artifacts import LoadedCompiledChecksArtifact
from recon_core.check_engine.models import RunResult
from recon_core.services.results import ExitCategory, ServiceResult


class _RunStage(StrEnum):
    PROJECT_CONFIGURATION = "project_configuration"
    COMPILED_CHECKS = "compiled_checks"
    COMPILED_CONTRACTS = "compiled_contracts"
    RUNTIME_SETUP = "runtime_setup"
    CHECK_EXECUTION = "check_execution"


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


@dataclass(slots=True)
class _RunInvocation:
    run_id: str
    started_at: str
    started_ns: int
    project_name: str | None = None
    stage: _RunStage = _RunStage.PROJECT_CONFIGURATION
    plan: _CompiledRunPlan | None = field(default=None, repr=False)

    def finish(
        self,
        *,
        finished_at: str,
        finished_ns: int,
        service_result: ServiceResult,
        run_result: RunResult | None,
    ) -> _InvocationOutcome:
        if run_result is not None:
            assert self.project_name is not None
            run_result = replace(
                run_result,
                run_id=self.run_id,
                project_name=self.project_name,
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
        )
