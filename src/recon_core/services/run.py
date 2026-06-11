"""Run command service."""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from recon_core.artifacts import (
    NO_COMPILED_CHECKS,
    CompiledCheckLoader,
    CompiledCheckLoadResult,
    LoadedCompiledChecksArtifact,
)
from recon_core.check_engine import CheckEngine, ContractResult, RunResult, RunStatus
from recon_core.diagnostics import Diagnostic
from recon_core.project import load_project_context
from recon_core.services.results import ExitCategory, ServiceResult


class _CompiledCheckLoader(Protocol):
    def load(self, target_path: Path) -> CompiledCheckLoadResult: ...


class _CheckEngine(Protocol):
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
    ) -> RunResult: ...


@dataclass(frozen=True, slots=True)
class RunService:
    """Service boundary for recon run."""

    start_path: Path | None = None
    loader: _CompiledCheckLoader | None = None
    engine: _CheckEngine | None = None

    def execute(self) -> ServiceResult:
        context_result = load_project_context(self.start_path)
        if not context_result.succeeded:
            return ServiceResult(
                exit_category=ExitCategory.CONFIGURATION_ERROR,
                message="Project configuration failed.",
                diagnostics=context_result.diagnostics,
            )

        assert context_result.context is not None
        context = context_result.context
        loader = self.loader if self.loader is not None else CompiledCheckLoader()
        load_result = loader.load(context.paths.target_path)
        if not load_result.succeeded:
            return _load_failure_result(load_result)

        started_at = _utc_timestamp()
        run_result = (self.engine if self.engine is not None else CheckEngine()).run(
            load_result.artifacts,
            run_id=f"run-{uuid4().hex}",
            started_at=started_at,
            finished_at=_utc_timestamp(),
            project_name=context.config.name,
        )
        return _run_service_result(run_result)


def _load_failure_result(load_result: CompiledCheckLoadResult) -> ServiceResult:
    message = "Compiled-check artifacts could not be loaded."
    if any(diagnostic.code == NO_COMPILED_CHECKS for diagnostic in load_result.diagnostics):
        message = "No compiled checks are available."
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message=message,
        diagnostics=load_result.diagnostics,
    )


def _run_service_result(run_result: RunResult) -> ServiceResult:
    return ServiceResult(
        exit_category=_exit_category_for_run_status(run_result.status),
        message=_message_for_run_status(run_result.status),
        diagnostics=_collect_run_diagnostics(run_result),
    )


def _exit_category_for_run_status(status: RunStatus) -> ExitCategory:
    if status in {RunStatus.PASS, RunStatus.WARN, RunStatus.SKIPPED}:
        return ExitCategory.SUCCESS
    if status is RunStatus.FAIL:
        return ExitCategory.CHECK_FAILURE
    return ExitCategory.RUNTIME_ERROR


def _message_for_run_status(status: RunStatus) -> str:
    return {
        RunStatus.PASS: "Run completed with passing checks.",
        RunStatus.FAIL: "Run completed with failing checks.",
        RunStatus.WARN: "Run completed with warning checks.",
        RunStatus.ERROR: "Run failed during check-engine evaluation.",
        RunStatus.SKIPPED: "Run completed with skipped checks.",
        RunStatus.BLOCKED: "Run completed with blocked checks.",
        RunStatus.NOT_EXECUTABLE: "Run completed with non-executable checks.",
        RunStatus.NO_CHECKS: "No compiled checks are available.",
    }[status]


def _collect_run_diagnostics(run_result: RunResult) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = list(run_result.diagnostics)
    for contract_result in run_result.contract_results:
        diagnostics.extend(_collect_contract_diagnostics(contract_result))
    return _dedupe_diagnostics(tuple(diagnostics))


def _collect_contract_diagnostics(contract_result: ContractResult) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = list(contract_result.diagnostics)
    for check_result in contract_result.check_results:
        diagnostics.extend(check_result.diagnostics)
    return tuple(diagnostics)


def _dedupe_diagnostics(diagnostics: tuple[Diagnostic, ...]) -> tuple[Diagnostic, ...]:
    unique: list[Diagnostic] = []
    seen: set[tuple[object, ...]] = set()
    for diagnostic in diagnostics:
        key = (
            diagnostic.code,
            diagnostic.severity,
            diagnostic.message,
            diagnostic.resource_type,
            diagnostic.resource_name,
            diagnostic.path,
            diagnostic.line,
            diagnostic.column,
            diagnostic.hint,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(diagnostic)
    return tuple(unique)


def _utc_timestamp() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
