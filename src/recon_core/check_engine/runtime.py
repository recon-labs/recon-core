"""Runtime execution routing for supported check-engine execution families."""

from collections.abc import Mapping
from typing import Protocol

from recon_core.adapters import BaseAdapter, ConnectionConfig, SqlRenderer
from recon_core.adapters.rendering import ADAPTER_RENDERER_METADATA_INVALID
from recon_core.artifacts import LoadedCompiledCheck, LoadedCompiledContractArtifact
from recon_core.artifacts.compiled_contract_loader import _ToleranceReferenceState
from recon_core.check_engine.aggregate import (
    _aggregate_connection_blocker,
    _aggregate_runtime_error,
    _aggregate_scan_blocker,
    _execute_aggregate_check,
    aggregate_admission,
    is_aggregate_check_type,
    is_supported_aggregate_plan_shape,
)
from recon_core.check_engine.execution import (
    _execute_row_count_check,
    is_supported_row_count_plan_shape,
    row_count_query_endpoint_not_executable_result,
)
from recon_core.check_engine.execution_support import (
    not_executable_result,
    safe_string_attribute,
    same_connection_context,
)
from recon_core.check_engine.key_safety import (
    _execute_key_safety_check,
    is_key_safety_check_type,
    is_supported_key_safety_plan_shape,
    key_safety_connection_context_not_executable_result,
    key_safety_identity_matches_contract,
    key_safety_identity_mismatch_not_executable_result,
    key_safety_query_endpoint_not_executable_result,
    key_safety_relation_endpoint_error_result_if_needed,
    key_safety_scan_budget_not_executable_result,
    key_safety_unsupported_plan_shape_not_executable_result,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.result_metadata import identity_label
from recon_core.check_engine.scan_budget import (
    BOUNDED_LOCAL_SCAN_REQUIRED,
    ScanBudgetDecision,
    missing_scan_budget_decision,
)
from recon_core.compiler.models import RenderingStatus


class RuntimeExecutionContext(Protocol):
    """Prepared dependencies consumed by runtime check-family routers."""

    contracts_by_name: Mapping[str, LoadedCompiledContractArtifact]
    adapters_by_connection: Mapping[str, BaseAdapter]
    connections_by_name: Mapping[str, ConnectionConfig]
    renderers_by_adapter_type: Mapping[str, SqlRenderer]
    scan_budget_decisions_by_check_id: Mapping[str, ScanBudgetDecision]


_DISPATCH_HARD_BLOCKING_REASONS = frozenset(
    {
        CheckReason.UNSUPPORTED_CHECK_TYPE,
        CheckReason.UNSUPPORTED_TYPED_OPERATION,
        CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
        CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
    }
)

_RUNTIME_BLOCKING_RENDERING_STATUSES = frozenset(
    {
        RenderingStatus.BLOCKED.value,
        RenderingStatus.FAILED.value,
    }
)


def rendering_blocked_result_if_needed(check: LoadedCompiledCheck) -> CheckResult | None:
    """Return an error when compiled rendering status blocks executable shapes."""
    if check.rendering_status not in _RUNTIME_BLOCKING_RENDERING_STATUSES:
        return None
    if (
        check.check_type != "row_count_diff"
        and not is_key_safety_check_type(check.check_type)
        and not is_aggregate_check_type(check.check_type)
    ):
        return None
    if is_aggregate_check_type(check.check_type) and not is_supported_aggregate_plan_shape(check):
        return None
    if check.check_type == "row_count_diff" and not is_supported_row_count_plan_shape(
        check.plan.operations
    ):
        return None
    if is_key_safety_check_type(check.check_type) and not is_supported_key_safety_plan_shape(
        check.check_type,
        check.plan.operations,
    ):
        return None

    message = (
        f"Check `{check.name}` did not run because compiled rendering status is "
        f"`{check.rendering_status}`."
    )
    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=CheckStatus.ERROR,
        executed=False,
        identity=identity_label(check),
        message=message,
        diagnostics=check.diagnostics,
    )


def runtime_execution_result_if_available(
    check: LoadedCompiledCheck,
    dispatch_result: CheckResult,
    execution_context: RuntimeExecutionContext | None,
) -> CheckResult | None:
    """Return a supported runtime execution result for an otherwise non-executable check."""
    if execution_context is None:
        return None
    if is_aggregate_check_type(check.check_type):
        return _aggregate_execution_result(check, dispatch_result, execution_context)
    return _row_count_execution_result_if_available(
        check,
        dispatch_result,
        execution_context,
    ) or _key_safety_execution_result_if_available(
        check,
        dispatch_result,
        execution_context,
    )


def _aggregate_execution_result(
    check: LoadedCompiledCheck,
    dispatch_result: CheckResult,
    execution_context: RuntimeExecutionContext,
) -> CheckResult | None:
    if dispatch_result.status is not CheckStatus.NOT_EXECUTABLE:
        return None
    if dispatch_result.reason_code in _DISPATCH_HARD_BLOCKING_REASONS:
        return None
    contract = execution_context.contracts_by_name.get(check.contract_name)
    if contract is None:
        return None
    states = getattr(execution_context, "tolerance_states_by_contract_id", None)
    state = states.get(contract.contract_id) if isinstance(states, Mapping) else None
    admission = aggregate_admission(
        check, contract, state if isinstance(state, _ToleranceReferenceState) else None
    )
    if admission.blocker is not None:
        return admission.blocker
    if contract.source.connection != contract.target.connection:
        source = execution_context.connections_by_name.get(contract.source.connection)
        target = execution_context.connections_by_name.get(contract.target.connection)
        if source is None or target is None or not same_connection_context(source, target):
            return _aggregate_connection_blocker(check, contract)
    decision = execution_context.scan_budget_decisions_by_check_id.get(
        check.id, missing_scan_budget_decision()
    )
    blocker = _aggregate_scan_blocker(check, contract, decision)
    if blocker is not None:
        return blocker
    blockers = getattr(execution_context, "aggregate_blockers_by_check_id", None)
    if isinstance(blockers, Mapping):
        prepared_blocker = blockers.get(check.id)
        if isinstance(prepared_blocker, CheckResult):
            return prepared_blocker
    adapter = execution_context.adapters_by_connection.get(contract.source.connection)
    if adapter is None:
        return _aggregate_runtime_error(
            check,
            contract,
            ADAPTER_RENDERER_METADATA_INVALID,
            "Aggregate execution requires a prepared private adapter.",
        )
    renderers = getattr(execution_context, "aggregate_renderers_by_adapter_type", None)
    adapter_type = safe_string_attribute(adapter, "adapter_type")
    renderer = renderers.get(adapter_type) if isinstance(renderers, Mapping) else None
    assert admission.tolerance is not None
    return _execute_aggregate_check(
        check,
        contract,
        adapter,
        renderer=renderer,
        tolerance=admission.tolerance,
        decision=decision,
        connections_by_name=execution_context.connections_by_name,
        bound_runner=getattr(execution_context, "_bound_runner", None),
    )


def _row_count_execution_result_if_available(
    check: LoadedCompiledCheck,
    dispatch_result: CheckResult,
    execution_context: RuntimeExecutionContext,
) -> CheckResult | None:
    if check.check_type != "row_count_diff":
        return None
    if dispatch_result.status is not CheckStatus.NOT_EXECUTABLE:
        return None
    if dispatch_result.reason_code in _DISPATCH_HARD_BLOCKING_REASONS:
        return None
    if not is_supported_row_count_plan_shape(check.plan.operations):
        return None

    contract = execution_context.contracts_by_name.get(check.contract_name)
    if contract is None:
        return None
    if _contract_has_query_endpoint(contract):
        return row_count_query_endpoint_not_executable_result(check, contract)
    decision = execution_context.scan_budget_decisions_by_check_id.get(check.id)
    if decision is not None and not decision.allowed:
        return not_executable_result(
            check,
            contract,
            reason=CheckReason.BOUNDED_LOCAL_SCAN_REQUIRED,
            diagnostic_code=BOUNDED_LOCAL_SCAN_REQUIRED,
            message="Check requires a verified local base-table execution scope.",
            hint="Verify the local database and supported base-table relations.",
        )
    adapter = execution_context.adapters_by_connection.get(contract.source.connection)
    if adapter is None:
        return None

    renderer = _renderer_for_adapter(adapter, execution_context)
    return _execute_row_count_check(
        check,
        contract,
        adapter,
        renderer=renderer,
        connections_by_name=execution_context.connections_by_name,
        bound_runner=getattr(execution_context, "_bound_runner", None),
    )


def _key_safety_execution_result_if_available(
    check: LoadedCompiledCheck,
    dispatch_result: CheckResult,
    execution_context: RuntimeExecutionContext,
) -> CheckResult | None:
    if not is_key_safety_check_type(check.check_type):
        return None
    if dispatch_result.status is not CheckStatus.NOT_EXECUTABLE:
        return None
    if dispatch_result.reason_code in _DISPATCH_HARD_BLOCKING_REASONS:
        return None

    contract = execution_context.contracts_by_name.get(check.contract_name)
    if contract is None:
        return None
    if not is_supported_key_safety_plan_shape(check.check_type, check.plan.operations):
        return key_safety_unsupported_plan_shape_not_executable_result(check, contract)
    if not key_safety_identity_matches_contract(check, contract):
        return key_safety_identity_mismatch_not_executable_result(check, contract)
    if _contract_has_query_endpoint(contract):
        return key_safety_query_endpoint_not_executable_result(check, contract)

    relation_error = key_safety_relation_endpoint_error_result_if_needed(check, contract)
    if relation_error is not None:
        return relation_error

    connection_context_blocker = _key_safety_connection_context_blocker_if_needed(
        check,
        contract,
        execution_context,
    )
    if connection_context_blocker is not None:
        return connection_context_blocker
    scan_budget_decision = execution_context.scan_budget_decisions_by_check_id.get(
        check.id,
        missing_scan_budget_decision(),
    )
    if not scan_budget_decision.allowed:
        return key_safety_scan_budget_not_executable_result(
            check,
            contract,
            scan_budget_decision,
        )

    adapter = execution_context.adapters_by_connection.get(contract.source.connection)
    if adapter is None:
        return None

    renderer = _renderer_for_adapter(adapter, execution_context)
    return _execute_key_safety_check(
        check,
        contract,
        adapter,
        scan_budget_decision=scan_budget_decision,
        renderer=renderer,
        connections_by_name=execution_context.connections_by_name,
        bound_runner=getattr(execution_context, "_bound_runner", None),
    )


def _key_safety_connection_context_blocker_if_needed(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    execution_context: RuntimeExecutionContext,
) -> CheckResult | None:
    if contract.source.connection == contract.target.connection:
        return None
    source_connection = execution_context.connections_by_name.get(contract.source.connection)
    target_connection = execution_context.connections_by_name.get(contract.target.connection)
    if source_connection is None or target_connection is None:
        return key_safety_connection_context_not_executable_result(check, contract)
    if not same_connection_context(source_connection, target_connection):
        return key_safety_connection_context_not_executable_result(check, contract)
    return None


def _renderer_for_adapter(
    adapter: BaseAdapter,
    execution_context: RuntimeExecutionContext,
) -> SqlRenderer | None:
    adapter_type = safe_string_attribute(adapter, "adapter_type")
    if adapter_type is None:
        return None
    return execution_context.renderers_by_adapter_type.get(adapter_type)


def _contract_has_query_endpoint(contract: LoadedCompiledContractArtifact) -> bool:
    return contract.source.query is not None or contract.target.query is not None
