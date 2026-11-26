"""Run command service."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from recon_core.adapters import (
    AdapterRegistry,
    BaseAdapter,
    ConnectionConfig,
    SqlRenderer,
    prepare_runtime_adapter,
)
from recon_core.adapters._aggregate_runtime import _AggregateRuntimeRenderer
from recon_core.adapters._project_binding import (
    _MAX_BOUNDED_LOCAL_DUCKDB_BYTES,
    _local_file_identity,
    _LocalFileIdentity,
)
from recon_core.adapters.capabilities import ADAPTER_CAPABILITY_UNSUPPORTED, AdapterCapabilities
from recon_core.adapters.default_renderers import (
    _default_aggregate_runtime_renderers,
    default_runtime_renderers_by_adapter_type,
)
from recon_core.adapters.registry import (
    ADAPTER_API_VERSION_UNSUPPORTED,
    ADAPTER_METADATA_INVALID,
    ADAPTER_RESOLUTION_FAILED,
    ADAPTER_UNKNOWN_TYPE,
)
from recon_core.adapters.runtime_safety import (
    RuntimeSafetyCheckRegistry,
    RuntimeSafetyCheckRequest,
    default_runtime_safety_check_registry,
)
from recon_core.adapters.runtime_setup import (
    ADAPTER_CAPABILITY_DECLARATION_FAILED,
    ADAPTER_TYPE_MISMATCH,
)
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
from recon_core.artifacts.compiled_contract_loader import _ToleranceReferenceState
from recon_core.check_engine import (
    CHECK_ENGINE_INTERNAL_ERROR,
    CheckEngine,
    CheckExecutionContext,
    CheckResult,
    ContractResult,
    RunResult,
    RunStatus,
    is_supported_row_count_plan_shape,
)
from recon_core.check_engine._bound_protocol import _BoundRunner
from recon_core.check_engine.aggregate import (
    _aggregate_capability_blocker,
    _aggregate_capability_diagnostics,
    _aggregate_collaborator_blocker,
    aggregate_admission,
    is_aggregate_check_type,
    is_supported_aggregate_plan_shape,
)
from recon_core.check_engine.engine import _AggregateExecutionContext, _ProjectExecutionContext
from recon_core.check_engine.execution_support import adapter_matches_connection
from recon_core.check_engine.key_safety import (
    is_key_safety_check_type,
    is_supported_key_safety_plan_shape,
    key_safety_identity_matches_contract,
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
from recon_core.profiles import load_selected_profile_for_connection_names
from recon_core.profiles.connection_references import (
    referenced_connection_names_from_compiled_contracts,
)
from recon_core.project import ProjectContext, load_project_context
from recon_core.services._bound_runner import _ProjectBoundRunner
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
    diagnostics: tuple[Diagnostic, ...] = ()
    exit_category: ExitCategory = ExitCategory.CONFIGURATION_ERROR
    message: str = ""


@dataclass(frozen=True, slots=True)
class _RuntimeScanBudgetDecisions:
    decisions_by_check_id: Mapping[str, ScanBudgetDecision]
    identities_by_check_id: Mapping[str, _LocalFileIdentity]
    adapter_setup_required_check_ids: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class _RuntimeScanBudgetDecision:
    decision: ScanBudgetDecision
    requires_adapter_setup: bool = False


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

        tolerance_states: dict[str, _ToleranceReferenceState] = {}
        if self.contract_loader is None:
            contract_load_result, tolerance_states = CompiledContractLoader()._load_for_runtime(
                context.paths.target_path, load_result.artifacts
            )
        else:
            contract_load_result = self.contract_loader.load_for_compiled_checks(
                context.paths.target_path, load_result.artifacts
            )
        if not contract_load_result.succeeded:
            return _compiled_contract_load_failure_result(contract_load_result)

        runtime_dependencies = _prepare_runtime_execution_dependencies(
            context,
            check_artifacts=load_result.artifacts,
            compiled_contracts=contract_load_result.artifacts,
            tolerance_states=tolerance_states,
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
            return _engine_failure_result()
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
    tolerance_states: Mapping[str, _ToleranceReferenceState],
    registry: AdapterRegistry | None,
    environ: Mapping[str, str] | None,
) -> _RuntimeExecutionDependencies:
    contracts_by_name = {contract.contract_name: contract for contract in compiled_contracts}
    has_aggregate_checks = any(
        is_aggregate_check_type(check.check_type)
        for artifact in check_artifacts
        for check in artifact.checks
    )
    known_check_ids = {check.id for artifact in check_artifacts for check in artifact.checks}
    missing_prerequisite_ids = frozenset(
        check.id
        for artifact in check_artifacts
        for check in artifact.checks
        if is_aggregate_check_type(check.check_type)
        and any(prerequisite not in known_check_ids for prerequisite in check.prerequisites)
    )
    runtime_candidates = _runtime_execution_candidates(
        check_artifacts, excluded_check_ids=missing_prerequisite_ids
    )
    if not runtime_candidates:
        if has_aggregate_checks or _has_key_safety_checks(check_artifacts):
            return _RuntimeExecutionDependencies(
                execution_context=_runtime_context(
                    contracts_by_name=contracts_by_name,
                    adapters_by_connection={},
                    tolerance_states=tolerance_states if has_aggregate_checks else None,
                ),
            )
        return _RuntimeExecutionDependencies()
    profile_candidates = _relation_backed_runtime_candidates(
        runtime_candidates,
        contracts_by_name=contracts_by_name,
        tolerance_states=tolerance_states,
    )
    if not profile_candidates:
        return _RuntimeExecutionDependencies(
            execution_context=_runtime_context(
                contracts_by_name=contracts_by_name,
                adapters_by_connection={},
                tolerance_states=tolerance_states if has_aggregate_checks else None,
            ),
        )
    candidate_contracts = _compiled_contracts_for_runtime_candidates(
        profile_candidates,
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
    connections_by_name = _runtime_connections_for_project(
        profile_result.profile.connections,
        project_root=context.project_root,
    )
    runtime_safety_checks = default_runtime_safety_check_registry()
    scan_budget_decisions = _scan_budget_decisions_by_check_id(
        profile_candidates,
        contracts_by_name=contracts_by_name,
        connections_by_name=connections_by_name,
        project_root=context.project_root,
        runtime_safety_checks=runtime_safety_checks,
    )
    adapter_candidates = _adapter_required_runtime_candidates(
        profile_candidates,
        scan_budget_decisions_by_check_id=scan_budget_decisions.decisions_by_check_id,
        adapter_setup_required_check_ids=scan_budget_decisions.adapter_setup_required_check_ids,
    )
    required_capabilities_by_connection = _required_capabilities_by_connection(
        adapter_candidates,
        contracts_by_name=contracts_by_name,
    )
    adapters_by_connection: dict[str, BaseAdapter] = {}
    capabilities_by_connection: dict[str, AdapterCapabilities] = {}
    setup_diagnostics: list[Diagnostic] = []
    aggregate_connections = {
        name
        for artifact in adapter_candidates
        if any(is_aggregate_check_type(check.check_type) for check in artifact.checks)
        for name in (
            contracts_by_name[artifact.contract_name].source.connection,
            contracts_by_name[artifact.contract_name].target.connection,
        )
    }
    aggregate_connection_indices = {
        name: index
        for index, name in enumerate(sorted(required_capabilities_by_connection), start=1)
        if name in aggregate_connections
    }
    for connection_name, required_capabilities in sorted(
        required_capabilities_by_connection.items()
    ):
        connection_index = aggregate_connection_indices.get(connection_name)
        connection = connections_by_name[connection_name]
        # Keep the scan-approved config independent of mutable factory input.
        verify_binding = connection_index is not None or connection.type == "duckdb"
        setup_connection = deepcopy(connection) if verify_binding else connection
        setup_result = prepare_runtime_adapter(
            connection=setup_connection,
            required_capabilities=required_capabilities,
            registry=registry,
        )
        if not setup_result.succeeded:
            # Aggregate-only capability declarations are check-level blockers.
            # Retain the existing service-level setup boundary for legacy checks
            # and for all other resolution or adapter API failures.
            if (
                not required_capabilities
                and setup_result.diagnostics
                and all(
                    diagnostic.code == ADAPTER_CAPABILITY_DECLARATION_FAILED
                    for diagnostic in setup_result.diagnostics
                )
            ):
                continue
            setup_diagnostics.extend(
                _safe_aggregate_setup_diagnostic(diagnostic, connection_index=connection_index)
                if connection_index is not None
                else diagnostic
                for diagnostic in setup_result.diagnostics
            )
            continue
        assert setup_result.adapter is not None
        if verify_binding and not adapter_matches_connection(
            setup_result.adapter, connection
        ):
            setup_diagnostics.append(
                Diagnostic(
                    code=ADAPTER_METADATA_INVALID,
                    severity=DiagnosticSeverity.ERROR,
                    message="Adapter binding does not match the approved connection.",
                    resource_type="adapter",
                    hint=(
                        _aggregate_setup_hint(connection_index)
                        if connection_index is not None
                        else "Inspect the approved connection configuration locally."
                    ),
                )
            )
            continue
        adapters_by_connection[connection_name] = setup_result.adapter
        assert setup_result.capabilities is not None
        capabilities_by_connection[connection_name] = setup_result.capabilities

    if setup_diagnostics:
        return _RuntimeExecutionDependencies(
            diagnostics=_dedupe_diagnostics(tuple(setup_diagnostics)),
            exit_category=ExitCategory.CONFIGURATION_ERROR,
            message="Run adapter configuration failed.",
        )

    aggregate_blockers = _aggregate_capability_blockers(
        adapter_candidates,
        contracts_by_name=contracts_by_name,
        connections_by_name=connections_by_name,
        capabilities_by_connection=capabilities_by_connection,
    )
    aggregate_renderers = _default_aggregate_runtime_renderers() if has_aggregate_checks else {}
    for artifact in adapter_candidates:
        contract = contracts_by_name[artifact.contract_name]
        for check in artifact.checks:
            if not is_aggregate_check_type(check.check_type) or check.id in aggregate_blockers:
                continue
            adapter = adapters_by_connection[contract.source.connection]
            renderer = aggregate_renderers.get(connections_by_name[contract.source.connection].type)
            blocker = _aggregate_collaborator_blocker(check, contract, adapter, renderer)
            if blocker is not None:
                aggregate_blockers[check.id] = blocker
    return _RuntimeExecutionDependencies(
        execution_context=_runtime_context(
            contracts_by_name=contracts_by_name,
            adapters_by_connection=adapters_by_connection,
            connections_by_name=connections_by_name,
            renderers_by_adapter_type=default_runtime_renderers_by_adapter_type(),
            scan_budget_decisions_by_check_id=scan_budget_decisions.decisions_by_check_id,
            tolerance_states=tolerance_states if has_aggregate_checks else None,
            aggregate_blockers_by_check_id=aggregate_blockers,
            aggregate_renderers_by_adapter_type=aggregate_renderers,
            bound_runner=_ProjectBoundRunner(
                context.project_root,
                connections_by_name,
                scan_budget_decisions.identities_by_check_id,
            ),
        ),
    )


def _runtime_context(
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    adapters_by_connection: Mapping[str, BaseAdapter],
    tolerance_states: Mapping[str, _ToleranceReferenceState] | None,
    connections_by_name: Mapping[str, ConnectionConfig] | None = None,
    renderers_by_adapter_type: Mapping[str, SqlRenderer] | None = None,
    scan_budget_decisions_by_check_id: Mapping[str, ScanBudgetDecision] | None = None,
    aggregate_blockers_by_check_id: Mapping[str, CheckResult] | None = None,
    aggregate_renderers_by_adapter_type: Mapping[str, _AggregateRuntimeRenderer] | None = None,
    bound_runner: _BoundRunner | None = None,
) -> CheckExecutionContext:
    if bound_runner is not None:
        return _ProjectExecutionContext(
            contracts_by_name=contracts_by_name,
            adapters_by_connection=adapters_by_connection,
            connections_by_name=connections_by_name or {},
            renderers_by_adapter_type=renderers_by_adapter_type or {},
            scan_budget_decisions_by_check_id=scan_budget_decisions_by_check_id or {},
            tolerance_states_by_contract_id=tolerance_states or {},
            aggregate_blockers_by_check_id=aggregate_blockers_by_check_id or {},
            aggregate_renderers_by_adapter_type=aggregate_renderers_by_adapter_type or {},
            _bound_runner=bound_runner,
        )
    if tolerance_states is not None:
        return _AggregateExecutionContext(
            contracts_by_name=contracts_by_name,
            adapters_by_connection=adapters_by_connection,
            connections_by_name=connections_by_name or {},
            renderers_by_adapter_type=renderers_by_adapter_type or {},
            scan_budget_decisions_by_check_id=scan_budget_decisions_by_check_id or {},
            tolerance_states_by_contract_id=tolerance_states,
            aggregate_blockers_by_check_id=aggregate_blockers_by_check_id or {},
            aggregate_renderers_by_adapter_type=aggregate_renderers_by_adapter_type or {},
        )
    return CheckExecutionContext(
        contracts_by_name=contracts_by_name,
        adapters_by_connection=adapters_by_connection,
        connections_by_name=connections_by_name or {},
        renderers_by_adapter_type=renderers_by_adapter_type or {},
        scan_budget_decisions_by_check_id=scan_budget_decisions_by_check_id or {},
    )


def _runtime_connections_for_project(
    connections_by_name: Mapping[str, ConnectionConfig],
    *,
    project_root: Path,
) -> dict[str, ConnectionConfig]:
    return {
        name: _runtime_connection_for_project(connection, project_root=project_root)
        for name, connection in connections_by_name.items()
    }


def _runtime_connection_for_project(
    connection: ConnectionConfig,
    *,
    project_root: Path,
) -> ConnectionConfig:
    if connection.type != "duckdb":
        return connection
    database = connection.config.get("database")
    if not isinstance(database, str) or not database or database == ":memory:":
        return connection
    database_path = Path(database)
    if database_path.is_absolute():
        return connection
    try:
        resolved_database = (project_root / database_path).resolve()
    except (OSError, RuntimeError, ValueError):
        return connection
    return ConnectionConfig(
        name=connection.name,
        type=connection.type,
        config={**connection.config, "database": str(resolved_database)},
    )


def _runtime_execution_candidates(
    check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    excluded_check_ids: frozenset[str] = frozenset(),
) -> tuple[LoadedCompiledChecksArtifact, ...]:
    candidates: list[LoadedCompiledChecksArtifact] = []
    for artifact in check_artifacts:
        candidate_checks = tuple(
            check
            for check in artifact.checks
            if _is_runtime_execution_candidate(check) and check.id not in excluded_check_ids
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


def _has_key_safety_checks(
    check_artifacts: tuple[LoadedCompiledChecksArtifact, ...],
) -> bool:
    return any(
        is_key_safety_check_type(check.check_type)
        for artifact in check_artifacts
        for check in artifact.checks
    )


def _relation_backed_runtime_candidates(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    tolerance_states: Mapping[str, _ToleranceReferenceState],
) -> tuple[LoadedCompiledChecksArtifact, ...]:
    candidates: list[LoadedCompiledChecksArtifact] = []
    for artifact in runtime_candidates:
        contract = contracts_by_name.get(artifact.contract_name)
        if contract is None or not _is_relation_backed_contract(contract):
            continue
        candidate_checks = tuple(
            check
            for check in artifact.checks
            if _requires_runtime_profile_for_contract(
                check, contract, tolerance_states.get(contract.contract_id)
            )
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


def _requires_runtime_profile_for_contract(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    tolerance_state: _ToleranceReferenceState | None,
) -> bool:
    if check.check_type == "row_count_diff":
        return True
    if is_key_safety_check_type(check.check_type):
        return key_safety_identity_matches_contract(
            check,
            contract,
        ) and _contract_has_valid_relation_endpoint_shape(contract)
    if is_aggregate_check_type(check.check_type):
        return aggregate_admission(check, contract, tolerance_state).blocker is None
    return False


def _contract_has_valid_relation_endpoint_shape(
    contract: LoadedCompiledContractArtifact,
) -> bool:
    return (
        _relation_name_parts(contract.source.relation) is not None
        and _relation_name_parts(contract.target.relation) is not None
    )


def _adapter_required_runtime_candidates(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    scan_budget_decisions_by_check_id: Mapping[str, ScanBudgetDecision],
    adapter_setup_required_check_ids: frozenset[str],
) -> tuple[LoadedCompiledChecksArtifact, ...]:
    candidates: list[LoadedCompiledChecksArtifact] = []
    for artifact in runtime_candidates:
        candidate_checks = tuple(
            check
            for check in artifact.checks
            if _check_requires_adapter_setup(
                check,
                scan_budget_decisions_by_check_id=scan_budget_decisions_by_check_id,
                adapter_setup_required_check_ids=adapter_setup_required_check_ids,
            )
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


def _check_requires_adapter_setup(
    check: LoadedCompiledCheck,
    *,
    scan_budget_decisions_by_check_id: Mapping[str, ScanBudgetDecision],
    adapter_setup_required_check_ids: frozenset[str],
) -> bool:
    if is_aggregate_check_type(check.check_type):
        decision = scan_budget_decisions_by_check_id.get(check.id)
        return decision is not None and decision.allowed
    if not is_key_safety_check_type(check.check_type):
        decision = scan_budget_decisions_by_check_id.get(check.id)
        return decision is None or decision.allowed
    if check.id in adapter_setup_required_check_ids:
        return True
    decision = scan_budget_decisions_by_check_id.get(check.id)
    return decision is not None and decision.allowed


def _is_relation_backed_contract(contract: LoadedCompiledContractArtifact) -> bool:
    return (
        contract.source.relation is not None
        and contract.target.relation is not None
        and contract.source.query is None
        and contract.target.query is None
    )


def _is_runtime_execution_candidate(check: LoadedCompiledCheck) -> bool:
    if check.rendering_status in _RUNTIME_BLOCKING_RENDERING_STATUSES:
        return False
    if check.check_type == "row_count_diff":
        return is_supported_row_count_plan_shape(check.plan.operations)
    if is_key_safety_check_type(check.check_type):
        return is_supported_key_safety_plan_shape(check.check_type, check.plan.operations)
    if is_aggregate_check_type(check.check_type):
        return is_supported_aggregate_plan_shape(check)
    return False


def _compiled_contracts_for_runtime_candidates(
    runtime_candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    compiled_contracts: tuple[LoadedCompiledContractArtifact, ...],
) -> tuple[LoadedCompiledContractArtifact, ...]:
    candidate_contract_names = frozenset(artifact.contract_name for artifact in runtime_candidates)
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
            required_capabilities = (
                ()
                if is_aggregate_check_type(check.check_type)
                else _runtime_required_capabilities(check)
            )
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
    project_root: Path,
    runtime_safety_checks: RuntimeSafetyCheckRegistry,
) -> _RuntimeScanBudgetDecisions:
    decisions: dict[str, ScanBudgetDecision] = {}
    identities: dict[str, _LocalFileIdentity] = {}
    adapter_setup_required_check_ids: set[str] = set()
    for artifact in runtime_candidates:
        contract = contracts_by_name.get(artifact.contract_name)
        if contract is None:
            continue
        for check in artifact.checks:
            aggregate = is_aggregate_check_type(check.check_type)
            source = connections_by_name.get(contract.source.connection)
            target = connections_by_name.get(contract.target.connection)
            same_context = (
                source is not None
                and target is not None
                and _same_connection_context(source, target)
            )
            if same_context and source is not None and source.type == "duckdb":
                if not _contract_has_valid_relation_endpoint_shape(contract):
                    continue
                identity = _local_file_identity(source, project_root)
                over_cap = (
                    identity is not None
                    and check.check_type != "row_count_diff"
                    and identity.size > _MAX_BOUNDED_LOCAL_DUCKDB_BYTES
                )
                if identity is not None:
                    identities[check.id] = identity
                # This decision only selects eligible setup candidates. It is
                # not final admission: the owned session must bind both relations
                # before any comparison code may consume an allowed decision.
                decisions[check.id] = classify_scan_budget(
                    ScanBudgetContext(
                        environment=ScanExecutionEnvironment.LOCAL_DEV,
                        relation_backed=True,
                        bounded=identity is not None and not over_cap,
                        estimate_state=(
                            ScanEstimateState.OVER_BUDGET if over_cap else ScanEstimateState.UNKNOWN
                        ),
                    )
                )
                continue
            if not aggregate and not is_key_safety_check_type(check.check_type):
                continue
            if aggregate and not same_context:
                continue
            prepared_decision = _scan_budget_decision_for_relation(
                contract,
                connections_by_name=connections_by_name,
                project_root=project_root,
                runtime_safety_checks=runtime_safety_checks,
            )
            decisions[check.id] = prepared_decision.decision
            if not aggregate and prepared_decision.requires_adapter_setup:
                adapter_setup_required_check_ids.add(check.id)
    return _RuntimeScanBudgetDecisions(
        decisions_by_check_id=decisions,
        identities_by_check_id=identities,
        adapter_setup_required_check_ids=frozenset(adapter_setup_required_check_ids),
    )


def _scan_budget_decision_for_relation(
    contract: LoadedCompiledContractArtifact,
    *,
    connections_by_name: Mapping[str, ConnectionConfig],
    project_root: Path,
    runtime_safety_checks: RuntimeSafetyCheckRegistry,
) -> _RuntimeScanBudgetDecision:
    relation_backed = contract.source.relation is not None and contract.target.relation is not None
    source_connection = connections_by_name.get(contract.source.connection)
    target_connection = connections_by_name.get(contract.target.connection)
    scan_safety_status = runtime_safety_checks.scan_safety_status(
        RuntimeSafetyCheckRequest(
            source_connection=source_connection,
            target_connection=target_connection,
            source_relation=contract.source.relation,
            target_relation=contract.target.relation,
            project_root=project_root,
        )
    )
    local_dev = relation_backed and scan_safety_status.local_dev
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=(
                ScanExecutionEnvironment.LOCAL_DEV
                if local_dev
                else ScanExecutionEnvironment.PRODUCTION
            ),
            relation_backed=relation_backed,
            bounded=scan_safety_status.bounded,
            estimate_state=ScanEstimateState.UNKNOWN,
        )
    )
    return _RuntimeScanBudgetDecision(
        decision=decision,
        requires_adapter_setup=(
            local_dev and scan_safety_status.metadata_open_failed and not decision.allowed
        ),
    )


def _aggregate_setup_hint(connection_index: int) -> str:
    # A run-local ordinal preserves distinct setup failures without naming connections.
    return f"Connection setup #{connection_index}: inspect configuration locally."


def _safe_aggregate_setup_diagnostic(
    diagnostic: Diagnostic, *, connection_index: int
) -> Diagnostic:
    """Preserve recognized setup categories, never arbitrary adapter fields."""
    messages = {
        ADAPTER_RESOLUTION_FAILED: "Aggregate adapter resolution failed.",
        ADAPTER_UNKNOWN_TYPE: "Aggregate adapter type is not registered.",
        ADAPTER_API_VERSION_UNSUPPORTED: "Aggregate adapter API version is unsupported.",
        ADAPTER_METADATA_INVALID: "Aggregate adapter metadata is invalid.",
        ADAPTER_TYPE_MISMATCH: "Aggregate adapter type does not match the connection.",
        ADAPTER_CAPABILITY_DECLARATION_FAILED: "Aggregate adapter capability declaration failed.",
        ADAPTER_CAPABILITY_UNSUPPORTED: "Aggregate adapter required capability is unsupported.",
        "RC_ADAPTER_DEPENDENCY_MISSING": "Aggregate adapter dependency is missing.",
    }
    code = diagnostic.code if diagnostic.code in messages else ADAPTER_RESOLUTION_FAILED
    return Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=messages[code],
        resource_type="adapter",
        hint=_aggregate_setup_hint(connection_index),
    )


def _aggregate_capability_blockers(
    candidates: tuple[LoadedCompiledChecksArtifact, ...],
    *,
    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact],
    connections_by_name: Mapping[str, ConnectionConfig],
    capabilities_by_connection: Mapping[str, AdapterCapabilities],
) -> dict[str, CheckResult]:
    blockers: dict[str, CheckResult] = {}
    for artifact in candidates:
        contract = contracts_by_name[artifact.contract_name]
        for check in artifact.checks:
            if not is_aggregate_check_type(check.check_type):
                continue
            diagnostics: list[Diagnostic] = []
            for name in dict.fromkeys((contract.source.connection, contract.target.connection)):
                connection = connections_by_name[name]
                diagnostics.extend(
                    _aggregate_capability_diagnostics(
                        check, capabilities_by_connection.get(name), adapter_type=connection.type
                    )
                )
            if diagnostics:
                blockers[check.id] = _aggregate_capability_blocker(
                    check, contract, _dedupe_diagnostics(tuple(diagnostics))
                )
    return blockers


def _relation_name_parts(relation_name: str | None) -> tuple[str, ...] | None:
    if relation_name is None:
        return None
    raw_parts = relation_name.split(".")
    parts = tuple(part for part in raw_parts if part)
    if len(parts) not in {1, 2, 3} or len(parts) != len(raw_parts):
        return None
    return parts


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
