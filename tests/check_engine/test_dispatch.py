from recon_core.artifacts import LoadedCheckPlan, LoadedCompiledCheck
from recon_core.check_engine import (
    CheckDispatcher,
    CheckReason,
    CheckStatus,
)


def test_known_current_check_type_is_not_executable_in_current_phase() -> None:
    result = CheckDispatcher().dispatch(_loaded_check())

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.reason_code is CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE
    assert result.source_value is None
    assert result.target_value is None
    assert result.artifact_refs == ()
    assert result.sink_refs == ()
    assert result.diagnostics[0].code == "RC_RUNTIME_CHECK_NOT_EXECUTABLE"
    assert result.diagnostics[0].resource_type == "compiled_check"
    assert result.diagnostics[0].resource_name == "customer_revenue.row_count_diff"


def test_unknown_check_type_is_not_executable_with_unsupported_reason() -> None:
    result = CheckDispatcher().dispatch(
        _loaded_check(check_type="future_value_match", operation_type="row_count")
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_CHECK_TYPE
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_CHECK_TYPE"
    assert "future_value_match" in result.message


def test_unknown_typed_operation_is_not_executable_with_unsupported_reason() -> None:
    result = CheckDispatcher().dispatch(_loaded_check(operation_type="future_operation"))

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_TYPED_OPERATION
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
    assert "future_operation" in result.message


def test_unsupported_execution_placement_is_explicit_non_execution() -> None:
    result = CheckDispatcher().dispatch(
        _loaded_check(
            operation={
                "type": "row_count",
                "side": "source",
                "execution_placement": "external_comparison_engine",
            }
        )
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT"


def test_unsupported_materialization_policy_is_explicit_non_execution() -> None:
    result = CheckDispatcher().dispatch(
        _loaded_check(
            operation={
                "type": "row_count",
                "side": "source",
                "materialization_policy": "temporary_table",
            }
        )
    )

    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.reason_code is CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY
    assert result.diagnostics[0].code == "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY"


def test_dispatch_boundary_is_internal_not_public_registry() -> None:
    dispatcher = CheckDispatcher()

    assert not hasattr(dispatcher, "register")


def _loaded_check(
    *,
    check_type: str = "row_count_diff",
    operation_type: str = "row_count",
    operation: dict[str, object] | None = None,
) -> LoadedCompiledCheck:
    return LoadedCompiledCheck(
        id="check.ecommerce_recon.customer_revenue.row_count_diff",
        name="row_count_diff",
        check_type=check_type,
        contract_name="customer_revenue",
        plan=LoadedCheckPlan(
            id="plan.ecommerce_recon.customer_revenue.row_count_diff",
            operations=(operation if operation is not None else {"type": operation_type},),
            required_capabilities=(),
        ),
        payload={
            "identity": {
                "kind": "none",
                "keys": [],
            }
        },
    )
