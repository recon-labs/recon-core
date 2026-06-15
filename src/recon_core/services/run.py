"""Run command service."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from recon_core.adapters import (
    AdapterRegistry,
    BaseAdapter,
    ConnectionConfig,
    prepare_runtime_adapter,
)
from recon_core.adapters.diagnostic_redaction import sanitize_profile_backed_adapter_diagnostics
from recon_core.adapters.duckdb import ADAPTER_CLOSE_FAILED, ADAPTER_CONNECTION_FAILED
from recon_core.artifacts import (
    NO_COMPILED_CHECKS,
    CompiledCheckLoader,
    CompiledCheckLoadResult,
    CompiledContractLoader,
    CompiledContractLoadResult,
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
)
from recon_core.check_engine import (
    CHECK_ENGINE_INTERNAL_ERROR,
    CheckEngine,
    CheckExecutionContext,
    ContractResult,
    RunResult,
    RunStatus,
    is_supported_row_count_plan_shape,
)
from recon_core.check_engine.key_safety import (
    is_key_safety_check_type,
    is_supported_key_safety_plan_shape,
)
from recon_core.check_engine.scan_budget import (
    ScanBudgetContext,
    ScanBudgetDecision,
    ScanEstimateState,
    ScanExecutionEnvironment,
    classify_scan_budget,
)
from recon_core.compiler.models import RenderingStatus
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity
from recon_core.profiles import (
    load_selected_profile_for_connection_names,
    referenced_connection_names_from_compiled_contracts,
)
from recon_core.project import ProjectContext, load_project_context
from recon_core.services.results import ExitCategory, ServiceResult


class _CompiledCheckLoader(Protocol):
    def load(self, target_path: Path) -> CompiledCheckLoadResult: ...


class _CompiledContractLoader(Protocol):
    def load_for_compiled_checks(
        self,
        target_path: Path,
        check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
    ) -> CompiledContractLoadResult: ...


class _CheckEngine(Protocol):
    def run(
        self,
        artifacts: tuple[LoadedCompiledChecksArtifact, ...],
        *,
        run_id: str,
        started_at: str,
        finished_at: str,
        project_name: str | None = None,
        execution_context: CheckExecutionContext | None = None,
    ) -> RunResult: ...


@dataclass(frozen=True, slots=True)
class _RuntimeExecutionDependencies:
    execution_context: CheckExecutionContext | None = None
    opened_adapters: tuple["_OpenedAdapter", ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()
    exit_category: ExitCategory = ExitCategory.CONFIGURATION_ERROR
    message: str = ""


@dataclass(frozen=True, slots=True)
class _OpenedAdapter:
    adapter: BaseAdapter
    connection: ConnectionConfig


@dataclass(frozen=True, slots=True)
class RunService:
    """Service boundary for recon run."""

    start_path: Path | None = None
    loader: _CompiledCheckLoader | None = None
    contract_loader: _CompiledContractLoader | None = None
    engine: _CheckEngine | None = None
    adapter_registry: AdapterRegistry | None = None
    environ: Mapping[str, str] | None = None

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

        contract_loader = (
            self.contract_loader if self.contract_loader is not None else CompiledContractLoader()
        )
        contract_load_result = contract_loader.load_for_compiled_checks(
            context.paths.target_path,
            load_result.artifacts,
        )
        if not contract_load_result.succeeded:
            return _compiled_contract_load_failure_result(contract_load_result)

        runtime_dependencies = _prepare_runtime_execution_dependencies(
            context,
            check_artifacts=load_result.artifacts,
            compiled_contracts=contract_load_result.artifacts,
            registry=self.adapter_registry,
            environ=self.environ,
        )
        if runtime_dependencies.diagnostics:
            return ServiceResult(
                exit_category=runtime_dependencies.exit_category,
                message=runtime_dependencies.message,
                diagnostics=runtime_dependencies.diagnostics,
            )

        started_at = _utc_timestamp()
        try:
            run_result = (self.engine if self.engine is not None else CheckEngine()).run(
                load_result.artifacts,
                run_id=f"run-{uuid4().hex}",
                started_at=started_at,
                finished_at=_utc_timestamp(),
                project_name=context.config.name,
                execution_context=runtime_dependencies.execution_context,
            )
        except Exception:
            failure_result = _engine_failure_result()
            close_diagnostics = _close_opened_adapters(runtime_dependencies.opened_adapters)
            if close_diagnostics:
                return ServiceResult(
                    exit_category=failure_result.exit_category,
                    message=failure_result.message,
                    diagnostics=_dedupe_diagnostics(failure_result.diagnostics + close_diagnostics),
                )
            return failure_result

        close_diagnostics = _close_opened_adapters(runtime_dependencies.opened_adapters)
        if close_diagnostics:
            return _run_service_result_with_close_diagnostics(run_result, close_diagnostics)
        return _run_service_result(run_result)


_ROW_COUNT_RUNTIME_REQUIRED_CAPABILITIES = ("row_count", "cte_support")
_KEY_SAFETY_RUNTIME_REQUIRED_CAPABILITIES = {
    "key_diff": ("key_diff", "cte_support"),
    "null_key": ("null_key",),
    "duplicate_key": ("duplicate_key",),
}
_RUNTIME_BLOCKING_RENDERING_STATUSES = frozenset(
    {
        RenderingStatus.BLOCKED.value,
        RenderingStatus.FAILED.value,
    }
)


def _prepare_runtime_execution_dependencies(
    context: ProjectContext,
    *,
    check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
    compiled_contracts: tuple[LoadedCompiledContractArtifact, ...],
    registry: AdapterRegistry | None,
    environ: Mapping[str, str] | None,
) -> _RuntimeExecutionDependencies:
    runtime_candidates = _runtime_execution_candidates(check_artifacts)
    if not runtime_candidates:
        return _RuntimeExecutionDependencies()
    candidate_contracts = _compiled_contracts_for_runtime_candidates(
        runtime_candidates,
        compiled_contracts=compiled_contracts,
    )

    profile_result = load_selected_profile_for_connection_names(
        context,
        referenced_connection_names=referenced_connection_names_from_compiled_contracts(
            candidate_contracts
        ),
        environ=environ,
    )
    if not profile_result.succeeded:
        return _RuntimeExecutionDependencies(
            diagnostics=profile_result.diagnostics,
            exit_category=ExitCategory.CONFIGURATION_ERROR,
            message="Run profile configuration failed.",
        )

    assert profile_result.profile is not None
    contracts_by_name = {contract.contract_name: contract for contract in compiled_contracts}
    required_capabilities_by_connection = _required_capabilities_by_connection(
        runtime_candidates,
        contracts_by_name=contracts_by_name,
    )
    adapters_by_connection: dict[str, BaseAdapter] = {}
    setup_diagnostics: list[Diagnostic] = []
    for connection_name, required_capabilities in sorted(
        required_capabilities_by_connection.items()
    ):
        connection = profile_result.profile.connections[connection_name]
        setup_result = prepare_runtime_adapter(
            connection=connection,
            required_capabilities=required_capabilities,
            registry=registry,
        )
        if not setup_result.succeeded:
            setup_diagnostics.extend(setup_result.diagnostics)
            continue
        assert setup_result.adapter is not None
        adapters_by_connection[connection_name] = setup_result.adapter

    if setup_diagnostics:
        return _RuntimeExecutionDependencies(
            diagnostics=_dedupe_diagnostics(tuple(setup_diagnostics)),
            exit_category=ExitCategory.CONFIGURATION_ERROR,
            message="Run adapter configuration failed.",
        )

    open_result = _open_runtime_adapters(
        runtime_candidates,
        contracts_by_name=contracts_by_name,
        adapters_by_connection=adapters_by_connection,
        connections_by_name=profile_result.profile.connections,
    )
    if open_result.diagnostics:
        return _RuntimeExecutionDependencies(
            diagnostics=open_result.diagnostics,
            exit_category=ExitCategory.RUNTIME_ERROR,
            message="Run adapter connection failed.",
        )

    return _RuntimeExecutionDependencies(
        execution_context=CheckExecutionContext(
            contracts_by_name=contracts_by_name,
            adapters_by_connection=adapters_by_connection,
            connections_by_name=profile_result.profile.connections,
            scan_budget_decisions_by_check_id=_scan_budget_decisions_by_check_id(
                runtime_candidates,
                contracts_by_name=contracts_by_name,
                connections_by_name=profile_result.profile.connections,
            ),
        ),
        opened_adapters=open_result.opened_adapters,
    )


@dataclass(frozen=True, slots=True)
class _AdapterOpenResult:
    opened_adapters: tuple[_OpenedAdapter, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()


def _open_runtime_adapters(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    adapters_by_connection: Mapping[str, BaseAdapter],
    connections_by_name: Mapping[str, ConnectionConfig],
) -> _AdapterOpenResult:
    connection_names = _connection_names_to_open(
        runtime_candidates,
        contracts_by_name,
        connections_by_name,
    )
    opened_adapters: list[_OpenedAdapter] = []
    diagnostics: list[Diagnostic] = []

    for connection_name in connection_names:
        adapter = adapters_by_connection.get(connection_name)
        connection = connections_by_name.get(connection_name)
        if adapter is None or connection is None:
            continue
        if connection.type != "duckdb":
            continue
        try:
            adapter.connect()
        except Exception as exc:
            diagnostics.append(
                _adapter_lifecycle_diagnostic(
                    exc,
                    connection=connection,
                    fallback_code=ADAPTER_CONNECTION_FAILED,
                    fallback_message="Adapter connection failed.",
                )
            )
            diagnostics.extend(_close_opened_adapters(tuple(opened_adapters)))
            return _AdapterOpenResult(diagnostics=_dedupe_diagnostics(tuple(diagnostics)))
        opened_adapters.append(_OpenedAdapter(adapter=adapter, connection=connection))

    return _AdapterOpenResult(opened_adapters=tuple(opened_adapters))


def _runtime_execution_candidates(
    check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
) -> tuple[LoadedCompiledChecksArtifact, ...]:
    candidates: list[LoadedCompiledChecksArtifact] = []
    for artifact in check_artifacts:
        candidate_checks = tuple(
            check
            for check in artifact.checks
            if _is_runtime_execution_candidate(check)
        )
        if not candidate_checks:
            continue
        candidates.append(
            LoadedCompiledChecksArtifact(
                path=artifact.path,
                project_name=artifact.project_name,
                project_version=artifact.project_version,
                contract_id=artifact.contract_id,
                contract_name=artifact.contract_name,
                source_file=artifact.source_file,
                checks=candidate_checks,
                diagnostics=artifact.diagnostics,
                payload=artifact.payload,
            )
        )
    return tuple(candidates)


def _is_runtime_execution_candidate(check: LoadedCompiledCheck) -> bool:
    if check.rendering_status in _RUNTIME_BLOCKING_RENDERING_STATUSES:
        return False
    if check.check_type == "row_count_diff":
        return is_supported_row_count_plan_shape(check.plan.operations)
    if is_key_safety_check_type(check.check_type):
        return is_supported_key_safety_plan_shape(check.check_type, check.plan.operations)
    return False


def _compiled_contracts_for_runtime_candidates(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    compiled_contracts: tuple[LoadedCompiledContractArtifact, ...],
) -> tuple[LoadedCompiledContractArtifact, ...]:
    candidate_contract_names = frozenset(
        artifact.contract_name for artifact in runtime_candidates
    )
    return tuple(
        contract
        for contract in compiled_contracts
        if contract.contract_name in candidate_contract_names
    )


def _required_capabilities_by_connection(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
) -> dict[str, tuple[str, ...]]:
    capabilities_by_connection: dict[str, list[str]] = {}
    for artifact in runtime_candidates:
        contract = contracts_by_name.get(artifact.contract_name)
        if contract is None:
            continue
        for check in artifact.checks:
            required_capabilities = _runtime_required_capabilities(check)
            for connection_name in (contract.source.connection, contract.target.connection):
                capabilities = capabilities_by_connection.setdefault(connection_name, [])
                for capability in required_capabilities:
                    if capability not in capabilities:
                        capabilities.append(capability)
    return {
        connection_name: tuple(capabilities)
        for connection_name, capabilities in capabilities_by_connection.items()
    }


def _runtime_required_capabilities(check: LoadedCompiledCheck) -> tuple[str, ...]:
    required_capabilities = list(check.plan.required_capabilities)
    if check.check_type == "row_count_diff":
        required_capabilities.extend(_ROW_COUNT_RUNTIME_REQUIRED_CAPABILITIES)
    elif is_key_safety_check_type(check.check_type) and check.plan.operations:
        operation_type = check.plan.operations[0].get("type")
        if isinstance(operation_type, str):
            required_capabilities.extend(
                _KEY_SAFETY_RUNTIME_REQUIRED_CAPABILITIES.get(operation_type, ())
            )

    deduped: list[str] = []
    for capability in required_capabilities:
        if capability and capability not in deduped:
            deduped.append(capability)
    return tuple(deduped)


def _scan_budget_decisions_by_check_id(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    connections_by_name: Mapping[str, ConnectionConfig],
) -> dict[str, ScanBudgetDecision]:
    decisions: dict[str, ScanBudgetDecision] = {}
    for artifact in runtime_candidates:
        contract = contracts_by_name.get(artifact.contract_name)
        if contract is None:
            continue
        for check in artifact.checks:
            if not is_key_safety_check_type(check.check_type):
                continue
            decisions[check.id] = _scan_budget_decision_for_key_safety(
                contract,
                connections_by_name=connections_by_name,
            )
    return decisions


def _scan_budget_decision_for_key_safety(
    contract: LoadedCompiledContractArtifact,
    *,
    connections_by_name: Mapping[str, ConnectionConfig],
) -> ScanBudgetDecision:
    relation_backed = contract.source.relation is not None and contract.target.relation is not None
    source_connection = connections_by_name.get(contract.source.connection)
    target_connection = connections_by_name.get(contract.target.connection)
    bounded_local = (
        relation_backed
        and source_connection is not None
        and target_connection is not None
        and source_connection.type == "duckdb"
        and _same_connection_context(source_connection, target_connection)
    )
    return classify_scan_budget(
        ScanBudgetContext(
            environment=(
                ScanExecutionEnvironment.LOCAL_DEV
                if bounded_local
                else ScanExecutionEnvironment.PRODUCTION
            ),
            relation_backed=relation_backed,
            bounded=bounded_local,
            estimate_state=ScanEstimateState.UNKNOWN,
        )
    )


def _connection_names_to_open(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    connections_by_name: Mapping[str, ConnectionConfig],
) -> tuple[str, ...]:
    connection_names: set[str] = set()
    for artifact in runtime_candidates:
        contract = contracts_by_name.get(artifact.contract_name)
        if contract is None:
            continue
        if contract.source.relation is None or contract.target.relation is None:
            continue
        if contract.source.query is not None or contract.target.query is not None:
            continue
        source_connection = connections_by_name.get(contract.source.connection)
        target_connection = connections_by_name.get(contract.target.connection)
        if source_connection is None or target_connection is None:
            continue
        if not _same_connection_context(source_connection, target_connection):
            continue
        connection_names.add(contract.source.connection)
    return tuple(sorted(connection_names))


def _same_connection_context(left: ConnectionConfig, right: ConnectionConfig) -> bool:
    return left.type == right.type and left.config == right.config


def _load_failure_result(load_result: CompiledCheckLoadResult) -> ServiceResult:
    message = "Compiled-check artifacts could not be loaded."
    if any(diagnostic.code == NO_COMPILED_CHECKS for diagnostic in load_result.diagnostics):
        message = "No compiled checks are available."
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message=message,
        diagnostics=load_result.diagnostics,
    )


def _compiled_contract_load_failure_result(
    load_result: CompiledContractLoadResult,
) -> ServiceResult:
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message="Compiled-contract artifacts could not be loaded.",
        diagnostics=load_result.diagnostics,
    )


def _engine_failure_result() -> ServiceResult:
    message = "Check engine internal error occurred before a trustworthy result was produced."
    diagnostic = Diagnostic(
        code=CHECK_ENGINE_INTERNAL_ERROR,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="check_engine",
        hint="Retry the command or inspect Recon Core logs if available.",
    )
    return ServiceResult(
        exit_category=ExitCategory.RUNTIME_ERROR,
        message="Run failed during check-engine evaluation.",
        diagnostics=(diagnostic,),
    )


def _close_opened_adapters(opened_adapters: tuple[_OpenedAdapter, ...]) -> tuple[Diagnostic, ...]:
    diagnostics: list[Diagnostic] = []
    for opened_adapter in reversed(opened_adapters):
        try:
            opened_adapter.adapter.close()
        except Exception as exc:
            diagnostics.append(
                _adapter_lifecycle_diagnostic(
                    exc,
                    connection=opened_adapter.connection,
                    fallback_code=ADAPTER_CLOSE_FAILED,
                    fallback_message="Adapter close failed.",
                )
            )
    return _dedupe_diagnostics(tuple(diagnostics))


def _adapter_lifecycle_diagnostic(
    exc: Exception,
    *,
    connection: ConnectionConfig,
    fallback_code: str,
    fallback_message: str,
) -> Diagnostic:
    diagnostic = getattr(exc, "diagnostic", None)
    if not isinstance(diagnostic, Diagnostic):
        diagnostic = Diagnostic(
            code=fallback_code,
            severity=DiagnosticSeverity.ERROR,
            message=fallback_message,
            resource_type="adapter",
            resource_name=connection.type,
            hint=(
                f"Adapter lifecycle raised {type(exc).__name__}. Raw adapter error text "
                "was suppressed because runtime adapter diagnostics must not expose "
                "rendered connection config."
            ),
        )
    return sanitize_profile_backed_adapter_diagnostics(
        (diagnostic,),
        connection=connection,
    )[0]


def _run_service_result(run_result: RunResult) -> ServiceResult:
    return ServiceResult(
        exit_category=_exit_category_for_run_status(run_result.status),
        message=_message_for_run_status(run_result.status),
        diagnostics=_collect_run_diagnostics(run_result),
    )


def _run_service_result_with_close_diagnostics(
    run_result: RunResult,
    close_diagnostics: tuple[Diagnostic, ...],
) -> ServiceResult:
    base_result = _run_service_result(run_result)
    diagnostics = _dedupe_diagnostics(base_result.diagnostics + close_diagnostics)
    if base_result.exit_category in {ExitCategory.SUCCESS, ExitCategory.CHECK_FAILURE}:
        return ServiceResult(
            exit_category=ExitCategory.RUNTIME_ERROR,
            message="Run failed during adapter lifecycle cleanup.",
            diagnostics=diagnostics,
        )
    return ServiceResult(
        exit_category=base_result.exit_category,
        message=base_result.message,
        diagnostics=diagnostics,
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
