"""Private aggregate admission and shared numeric policy tests."""

from dataclasses import fields, replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from recon_core._numeric_policy import absolute_tolerance
from recon_core.artifacts import (
    LoadedCheckPlan,
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
    LoadedCompiledEndpoint,
)
from recon_core.artifacts.compiled_contract_loader import _ToleranceReferenceState
from recon_core.check_engine import CheckEngine, CheckExecutionContext, CheckResult, CheckStatus
from recon_core.check_engine.aggregate import aggregate_admission, is_supported_aggregate_plan_shape
from recon_core.check_engine.engine import _AggregateExecutionContext
from recon_core.compiler.policies import validate_tolerance
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, Decimal(0)),
        (-0.0, Decimal(0)),
        (0.1, Decimal("0.1")),
        (2**100 + 1, Decimal(2**100 + 1)),
        (Decimal("123456789.000000000000000001"), Decimal("123456789.000000000000000001")),
        ({"type": "absolute", "value": 0.1}, Decimal("0.1")),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_absolute_tolerance_is_context_independent(value: object, expected: Decimal) -> None:
    with localcontext() as context:
        context.prec = 3
        assert absolute_tolerance(value) == expected
        assert validate_tolerance(value, resource_type="metric", resource_name="m").succeeded


@pytest.mark.parametrize(
    "value",
    [
        None,
        False,
        -1,
        "0.1",
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("-Infinity"),
        {"type": "absolute"},
        {"type": "absolute", "value": {"type": "absolute", "value": 1}},
        {"type": "absolute", "value": True},
        {"type": "absolute", "value": 1, 2: 3},
        {"type": "percentage", "value": 1},
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_invalid_explicit_tolerance_agrees_with_compiler(value: object) -> None:
    assert absolute_tolerance(value) is None
    assert not validate_tolerance(value, resource_type="metric", resource_name="m").succeeded


def _compiled_aggregate(*, grouped: bool = False, tolerance: object = None) -> LoadedCompiledCheck:
    kind = "grouped_aggregate" if grouped else "aggregate"
    check_type = "grouped_aggregate_diff" if grouped else "sum_diff"
    groups = ["customer_id", "month"] if grouped else []
    operations: list[dict[str, object]] = [
        {"type": kind, "side": side, "aggregate": "sum", "column": "revenue"}
        for side in ("source", "target")
    ]
    if grouped:
        for operation in operations:
            operation["group_by"] = groups
    operations.append({"type": "compare_grouped_aggregates" if grouped else "compare_aggregates"})
    return LoadedCompiledCheck(
        id="check.project.contract.revenue",
        name="revenue",
        check_type=check_type,
        contract_name="contract",
        plan=LoadedCheckPlan(
            id="plan.project.contract.revenue",
            operations=tuple(operations),
            required_capabilities=(kind,),
        ),
        payload={
            "identity": {"kind": "none", "keys": []},
            "metric": {"type": "sum", "column": "revenue", "group_by": groups},
            "tolerance": tolerance,
        },
    )


def _contract(tmp_path: Path) -> LoadedCompiledContractArtifact:
    return LoadedCompiledContractArtifact(
        path=tmp_path / "contract.yml",
        project_name="project",
        project_version=None,
        contract_id="contract.project.contract",
        contract_name="contract",
        source_file="contracts/contract.yml",
        source=LoadedCompiledEndpoint(connection="warehouse", relation="qa.source"),
        target=LoadedCompiledEndpoint(connection="warehouse", relation="qa.target"),
    )


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize(
    ("value", "state", "expected"),
    [
        (None, _ToleranceReferenceState.ABSENT, Decimal(0)),
        (0, _ToleranceReferenceState.UNRESOLVED, Decimal(0)),
        (0.1, _ToleranceReferenceState.ABSENT, Decimal("0.1")),
        ({"type": "absolute", "value": 0.1}, _ToleranceReferenceState.UNRESOLVED, Decimal("0.1")),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_aggregate_admission_returns_canonical_threshold(
    tmp_path: Path,
    grouped: bool,
    value: object,
    state: _ToleranceReferenceState,
    expected: Decimal,
) -> None:
    admission = aggregate_admission(
        _compiled_aggregate(grouped=grouped, tolerance=value), _contract(tmp_path), state
    )
    assert admission.blocker is None
    assert admission.tolerance == expected


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.parametrize("index", (0, 1, 2))
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("unexpected", "private-plan-value"),
        ("execution_placement", "side_local"),
        ("comparison_location", "python"),
        ("materialization_policy", "stage"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_injected_aggregate_plan_rejects_unsupported_fields(
    tmp_path: Path, grouped: bool, index: int, field: str, value: object
) -> None:
    check = _compiled_aggregate(grouped=grouped)
    check.plan.operations[index][field] = value
    assert not is_supported_aggregate_plan_shape(check)
    admission = aggregate_admission(check, _contract(tmp_path), _ToleranceReferenceState.ABSENT)
    assert admission.tolerance is None
    assert admission.blocker is not None
    assert not admission.blocker.executed


@pytest.mark.parametrize("grouped", (False, True))
@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_aggregate_shape_accepts_empty_reserved_metadata(grouped: bool) -> None:
    check = _compiled_aggregate(grouped=grouped)
    for operation in check.plan.operations:
        operation.update(
            execution_placement=None, comparison_location="", materialization_policy="none"
        )
    assert is_supported_aggregate_plan_shape(check)


def _run_check(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    context: CheckExecutionContext,
) -> CheckResult:
    artifact = LoadedCompiledChecksArtifact(
        path=contract.path,
        project_name=contract.project_name,
        project_version=contract.project_version,
        contract_id=contract.contract_id,
        contract_name=contract.contract_name,
        source_file=contract.source_file,
        checks=(check,),
    )
    run = CheckEngine().run(
        (artifact,),
        run_id="run-test",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
        execution_context=context,
    )
    return run.contract_results[0].check_results[0]


@pytest.mark.parametrize("value", (None, 0, 0.1))
@pytest.mark.regression_capture("aggregate-admission-tolerance-policy")
def test_aggregate_unknown_private_metadata_blocks_even_with_override(
    tmp_path: Path, value: object
) -> None:
    check = _compiled_aggregate(tolerance=value)
    contract = _contract(tmp_path)
    context = CheckExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.diagnostics[-1].code == "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("execution_placement", "side_local", "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT"),
        ("comparison_location", "python", "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT"),
        ("materialization_policy", "stage", "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY"),
    ],
)
@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_aggregate_reserved_metadata_precedes_rendering_and_policy_blockers(
    tmp_path: Path, field: str, value: str, code: str
) -> None:
    check = _compiled_aggregate(tolerance=-1)
    check.plan.operations[0][field] = value
    check = replace(
        check,
        rendering_status="blocked",
        diagnostics=(
            Diagnostic(
                code="RC_TEST_RENDER_BLOCKED",
                severity=DiagnosticSeverity.ERROR,
                message="Blocked.",
            ),
        ),
    )
    contract = _contract(tmp_path)
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.UNRESOLVED},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert result.diagnostics[-1].code == code
    assert not result.executed


@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
def test_aggregate_prerequisite_precedes_invalid_policy(tmp_path: Path) -> None:
    check = replace(_compiled_aggregate(tolerance=-1), prerequisites=("check.missing",))
    contract = _contract(tmp_path)
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.BLOCKED
    assert result.blocked_by == ("check.missing",)
    assert result.diagnostics[-1].code == "RC_RUNTIME_CHECK_BLOCKED_BY_PREREQUISITE"
    assert not result.executed


def test_public_execution_context_fields_remain_unchanged() -> None:
    assert tuple(field.name for field in fields(CheckExecutionContext)) == (
        "contracts_by_name",
        "adapters_by_connection",
        "connections_by_name",
        "renderers_by_adapter_type",
        "scan_budget_decisions_by_check_id",
    )


@pytest.mark.regression_capture("aggregate-admission-typed-plan-boundary")
@pytest.mark.parametrize("status", ("blocked", "failed"))
def test_valid_aggregate_shape_preserves_rendering_error(tmp_path: Path, status: str) -> None:
    check = replace(
        _compiled_aggregate(tolerance=-1),
        rendering_status=status,
        diagnostics=(
            Diagnostic(
                code="RC_TEST_RENDER_BLOCKED",
                severity=DiagnosticSeverity.ERROR,
                message="Blocked.",
            ),
        ),
    )
    contract = _contract(tmp_path)
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["RC_TEST_RENDER_BLOCKED"]
