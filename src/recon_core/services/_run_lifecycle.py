"""Private run invocation state and finalized outcome; no output serialization."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

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
    run_result: RunResult | None = field(repr=False)


@dataclass(slots=True)
class _RunInvocation:
    run_id: str
    started_at: str
    started_ns: int
    project_name: str | None = None
    stage: _RunStage = _RunStage.PROJECT_CONFIGURATION

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
            run_result=run_result,
        )
