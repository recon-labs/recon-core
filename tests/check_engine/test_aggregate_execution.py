"""Private aggregate admission and shared numeric policy tests."""

from dataclasses import fields, replace
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from recon_core._numeric_policy import absolute_tolerance
from recon_core.adapters import (
    AdapterCapabilities,
    CapabilitySupport,
    ConnectionConfig,
    RenderedSql,
)
from recon_core.adapters._aggregate_runtime import (
    _SCALAR_COLUMNS,
    _SUMMARY_COLUMNS,
    _AggregateQueryResult,
    _AggregateRuntimePlan,
    _NumericDomain,
)
from recon_core.artifacts import (
    LoadedCheckPlan,
    LoadedCompiledCheck,
    LoadedCompiledChecksArtifact,
    LoadedCompiledContractArtifact,
    LoadedCompiledEndpoint,
)
from recon_core.artifacts.compiled_contract_loader import _ToleranceReferenceState
from recon_core.check_engine import CheckEngine, CheckExecutionContext, CheckResult, CheckStatus
from recon_core.check_engine.aggregate import (
    _compare_aggregate_result,
    aggregate_admission,
    is_supported_aggregate_plan_shape,
)
from recon_core.check_engine.engine import _AggregateExecutionContext
from recon_core.check_engine.scan_budget import (
    ScanBudgetContext,
    ScanBudgetDecision,
    ScanEstimateState,
    ScanExecutionEnvironment,
    classify_scan_budget,
)
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


_I = _NumericDomain.EXACT_INTEGER
_D = _NumericDomain.EXACT_DECIMAL
_F = _NumericDomain.NATIVE_FLOAT


def _compare(
    tmp_path: Path,
    row: tuple[object, ...],
    domain: _NumericDomain,
    tolerance: Decimal = Decimal(0),
    *,
    grouped: bool = False,
    columns: tuple[str, ...] | None = None,
    domains: tuple[_NumericDomain, ...] | None = None,
) -> CheckResult:
    if columns is None:
        columns = _SUMMARY_COLUMNS if grouped else _SCALAR_COLUMNS
    if domains is None:
        domains = (_I,) * 7 + (domain,) * 2 if grouped else (domain,) * 3
    result = _compare_aggregate_result(
        _compiled_aggregate(grouped=grouped),
        _contract(tmp_path),
        _AggregateQueryResult(columns=columns, domains=domains, row=row),
        domain=domain,
        tolerance=tolerance,
    )
    assert isinstance(result, CheckResult)
    assert result.executed == (result.status in (CheckStatus.PASS, CheckStatus.FAIL))
    assert result.reason_code is None
    for key in (
        "source_value",
        "target_value",
        "normalized_source_value",
        "normalized_target_value",
        "diff_value",
        "failure_count",
        "tolerance",
    ):
        assert result.to_dict()[key] is None
    assert result.artifact_refs == result.sink_refs == ()
    if result.status is CheckStatus.ERROR:
        assert result.diagnostics[-1].code == "RC_RUNTIME_AGGREGATE_RESULT_INVALID"
    return result


@pytest.mark.parametrize(
    ("domain", "row", "threshold", "status"),
    [
        (_I, (2**100 + 1, 2**100, 1), "0", CheckStatus.FAIL),
        (_I, (2**100 + 1, 2**100, 1), "1", CheckStatus.PASS),
        (_I, (-(2**127), 0, -(2**127)), str(2**127), CheckStatus.PASS),
        (_I, (10**5000 + 1, 10**5000, 1), "0", CheckStatus.FAIL),
        (_I, (10**5000 + 1, 10**5000, 1), "1", CheckStatus.PASS),
        (
            _D,
            (Decimal("123456789.000000000001"), Decimal("123456789"), Decimal("1E-12")),
            "0.000000000001",
            CheckStatus.PASS,
        ),
        (
            _D,
            (Decimal("123456789.000000000001"), Decimal("123456789"), Decimal("1E-12")),
            "0.000000000000999999",
            CheckStatus.FAIL,
        ),
        (_F, (0.30000000000000004, 0.2, 0.10000000000000003), "0.1", CheckStatus.FAIL),
        (
            _F,
            (0.30000000000000004, 0.2, 0.10000000000000003),
            "0.10000000000000003",
            CheckStatus.PASS,
        ),
        (_F, (0.2, 0.30000000000000004, -0.10000000000000003), "0.1", CheckStatus.FAIL),
        (_F, (-0.0, 0.0, -0.0), "0", CheckStatus.PASS),
        (_F, (5e-324, 0.0, 5e-324), "4e-324", CheckStatus.FAIL),
        (_F, (5e-324, 0.0, 5e-324), "5e-324", CheckStatus.PASS),
        (_F, (1e308, 0.0, 1e308), "1e308", CheckStatus.PASS),
    ],
)
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_scalar_numeric_comparison(
    tmp_path: Path,
    domain: _NumericDomain,
    row: tuple[object, ...],
    threshold: str,
    status: CheckStatus,
) -> None:
    with localcontext() as context:
        context.prec = 3
        assert _compare(tmp_path, row, domain, Decimal(threshold)).status is status


@pytest.mark.parametrize(
    ("row", "status"),
    [
        ((None, None, None), CheckStatus.PASS),
        ((None, 0, None), CheckStatus.FAIL),
        ((0, None, None), CheckStatus.FAIL),
        ((None, None, 0), CheckStatus.ERROR),
        ((None, 0, 0), CheckStatus.ERROR),
        ((1, 1, None), CheckStatus.ERROR),
        ((1, 1, 1), CheckStatus.ERROR),
        ((True, 1, 0), CheckStatus.ERROR),
        (("1", 1, 0), CheckStatus.ERROR),
        ((1.0, 1, 0), CheckStatus.ERROR),
        ((1, 1), CheckStatus.ERROR),
        ((1, 1, 0, 0), CheckStatus.ERROR),
    ],
)
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_scalar_nulls_and_malformed_results(
    tmp_path: Path, row: tuple[object, ...], status: CheckStatus
) -> None:
    assert _compare(tmp_path, row, _I).status is status


@pytest.mark.parametrize(
    ("domain", "row"),
    [
        (_F, (float("nan"), None, None)),
        (_F, (None, float("inf"), None)),
        (_F, (float("-inf"), float("-inf"), float("nan"))),
        (_F, (1e308, -1e308, float("inf"))),
        (_F, (0.3, 0.2, 0.1)),
        (_D, (Decimal("sNaN"), None, None)),
        (_D, (Decimal("Infinity"), Decimal(0), Decimal("Infinity"))),
        (_D, (Decimal("1.01"), Decimal("1"), Decimal("0.02"))),
        (_D, (Decimal(1), 1, Decimal(0))),
    ],
)
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_scalar_invalid_arithmetic(
    tmp_path: Path, domain: _NumericDomain, row: tuple[object, ...]
) -> None:
    assert _compare(tmp_path, row, domain).status is CheckStatus.ERROR


@pytest.mark.parametrize(
    ("columns", "domains"),
    [
        (("a", "b", "c"), (_I,) * 3),
        ((_SCALAR_COLUMNS[0],) * 3, (_I,) * 3),
        (_SCALAR_COLUMNS, (_I,) * 2),
        (_SCALAR_COLUMNS, (_I, _I, _D)),
        (_SCALAR_COLUMNS, ("exact_integer",) * 3),
    ],
)
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_scalar_invalid_metadata(
    tmp_path: Path, columns: tuple[str, ...], domains: tuple[_NumericDomain, ...]
) -> None:
    assert (
        _compare(tmp_path, (1, 1, 0), _I, columns=columns, domains=domains).status
        is CheckStatus.ERROR
    )


@pytest.mark.parametrize(
    ("domain", "row", "threshold", "status"),
    [
        (_I, (0, 0, 0, 0, 0, 0, 0, None, None), "0", CheckStatus.PASS),
        (_I, (3, 0, 0, 3, 0, 0, 0, None, None), "0", CheckStatus.PASS),
        (_I, (1, 1, 0, 0, 0, 0, 0, None, None), "100", CheckStatus.FAIL),
        (_I, (1, 0, 1, 0, 0, 0, 0, None, None), "100", CheckStatus.FAIL),
        (_I, (1, 0, 0, 0, 1, 0, 0, None, None), "100", CheckStatus.FAIL),
        (_I, (2, 0, 0, 0, 0, 2, 0, -5, 4), "5", CheckStatus.PASS),
        (_I, (2, 0, 0, 0, 0, 2, 0, -5, 4), "4", CheckStatus.FAIL),
        (_I, (2, 0, 0, 0, 0, 2, 0, -4, 5), "4", CheckStatus.FAIL),
        (_I, (1, 0, 0, 0, 0, 1, 0, -(2**127), -(2**127)), str(2**127), CheckStatus.PASS),
        (_I, (1, 0, 0, 0, 0, 1, 0, 10**5000, 10**5000), "1", CheckStatus.FAIL),
        (
            _D,
            (2, 0, 0, 0, 0, 2, 0, Decimal("-1.00000000001"), Decimal("1")),
            "1",
            CheckStatus.FAIL,
        ),
        (
            _F,
            (2, 0, 0, 0, 0, 2, 0, -0.10000000000000003, 0.1),
            "0.10000000000000003",
            CheckStatus.PASS,
        ),
        (
            _F,
            (2, 0, 0, 0, 0, 2, 0, -0.10000000000000003, 0.1),
            "0.1",
            CheckStatus.FAIL,
        ),
        (_F, (1, 0, 0, 0, 0, 1, 0, -0.0, 0.0), "0", CheckStatus.PASS),
        (_I, (2, 1, 0, 0, 0, 0, 1, None, None), "0", CheckStatus.ERROR),
        (_I, (2, 0, 0, 0, 1, 0, 1, None, None), "0", CheckStatus.ERROR),
        (_F, (2, 0, 0, 0, 0, 1, 1, 0.0, 0.0), "0", CheckStatus.ERROR),
    ],
)
@pytest.mark.regression_capture("aggregate-core-grouped-summary")
def test_aggregate_grouped_comparison(
    tmp_path: Path,
    domain: _NumericDomain,
    row: tuple[object, ...],
    threshold: str,
    status: CheckStatus,
) -> None:
    with localcontext() as context:
        context.prec = 3
        assert _compare(tmp_path, row, domain, Decimal(threshold), grouped=True).status is status


@pytest.mark.parametrize(
    "row",
    [
        (1, 0, 0, 0, 0, 0, 0, None, None),
        (0, 1, 0, 0, 0, 0, 0, None, None),
        (-1, -1, 0, 0, 0, 0, 0, None, None),
        (True, 1, 0, 0, 0, 0, 0, None, None),
        (1, 1.0, 0, 0, 0, 0, 0, None, None),
        (1, "1", 0, 0, 0, 0, 0, None, None),
        (1, None, 0, 0, 0, 0, 0, None, None),
        (1, 0, 0, 0, 0, 1, 0, None, None),
        (1, 0, 0, 0, 0, 1, 0, 0, None),
        (1, 0, 0, 0, 0, 1, 0, -1, 1),
        (2, 0, 0, 0, 0, 2, 0, 1, -1),
        (0, 0, 0, 0, 0, 0, 0, 0, 0),
        (2, 1, 0, 0, 0, 1, 0, 0, None),
        (1, 0, 0, 0, 0, 1, 0, 0.0, 0),
        (0, 0, 0, 0, 0, 0, 0, None),
    ],
)
@pytest.mark.regression_capture("aggregate-core-grouped-summary")
def test_aggregate_grouped_invalid_summary(tmp_path: Path, row: tuple[object, ...]) -> None:
    assert _compare(tmp_path, row, _I, grouped=True).status is CheckStatus.ERROR


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.regression_capture("aggregate-core-grouped-summary")
def test_aggregate_grouped_nonfinite_extrema(tmp_path: Path, value: float) -> None:
    row = (2, 1, 0, 0, 0, 1, 0, value, value)
    assert _compare(tmp_path, row, _F, grouped=True).status is CheckStatus.ERROR


@pytest.mark.parametrize(
    ("columns", "domains"),
    [
        (_SUMMARY_COLUMNS[::-1], (_I,) * 9),
        (_SUMMARY_COLUMNS, (_D,) + (_I,) * 8),
        (_SUMMARY_COLUMNS, (_I,) * 8 + (_D,)),
        (_SUMMARY_COLUMNS, (_I,) * 8),
    ],
)
@pytest.mark.regression_capture("aggregate-core-grouped-summary")
def test_aggregate_grouped_invalid_metadata(
    tmp_path: Path, columns: tuple[str, ...], domains: tuple[_NumericDomain, ...]
) -> None:
    row = (0, 0, 0, 0, 0, 0, 0, None, None)
    assert (
        _compare(tmp_path, row, _I, grouped=True, columns=columns, domains=domains).status
        is CheckStatus.ERROR
    )


@pytest.mark.parametrize("threshold", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity")])
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_invalid_admitted_threshold(tmp_path: Path, threshold: Decimal) -> None:
    assert _compare(tmp_path, (0, 0, 0), _I, threshold).status is CheckStatus.ERROR


@pytest.mark.regression_capture("aggregate-core-result-privacy")
def test_aggregate_comparison_diagnostic_does_not_expose_private_values(tmp_path: Path) -> None:
    private = "private-aggregate-value-73864"
    result = _compare(tmp_path, (private, 0, 0), _I)
    assert result.status is CheckStatus.ERROR
    assert private not in repr(result)
    assert private not in repr(result.to_dict())


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_comparison_ignores_decimal_context_limits(tmp_path: Path, grouped: bool) -> None:
    from decimal import Inexact, Overflow, Rounded, Underflow

    difference = Decimal("-999999999999999999.000000000000000001")
    if grouped:
        row = (1, 0, 0, 0, 0, 1, 0, difference, difference)
    else:
        row = (difference, Decimal(0), difference)
    with localcontext() as context:
        context.prec = 1
        context.Emax = 2
        context.Emin = -2
        for signal in (Inexact, Overflow, Rounded, Underflow):
            context.traps[signal] = True
        context.clear_flags()
        assert (
            _compare(tmp_path, row, _D, difference.copy_abs(), grouped=grouped).status
            is CheckStatus.PASS
        )
        assert (
            _compare(tmp_path, row, _D, Decimal("999999999999999999"), grouped=grouped).status
            is CheckStatus.FAIL
        )
        assert not any(context.flags.values())


@pytest.mark.parametrize(
    ("result", "domain", "threshold"),
    [
        (None, _I, Decimal(0)),
        ({"row": (1, 1, 0)}, _I, Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, [1, 1, 0]), _I, Decimal(0)),
        (_AggregateQueryResult(list(_SCALAR_COLUMNS), (_I,) * 3, (1, 1, 0)), _I, Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, [_I] * 3, (1, 1, 0)), _I, Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, ((1, 1, 0),)), _I, Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, (1, 1, 0)), "exact_integer", Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, (1, 1, 0)), None, Decimal(0)),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, (1, 1, 0)), _I, True),
        (_AggregateQueryResult(_SCALAR_COLUMNS, (_I,) * 3, (1, 1, 0)), _I, 0),
    ],
)
@pytest.mark.regression_capture("aggregate-core-numeric-comparison")
def test_aggregate_comparison_rejects_untyped_envelope(
    tmp_path: Path, result: object, domain: object, threshold: object
) -> None:
    outcome = _compare_aggregate_result(
        _compiled_aggregate(), _contract(tmp_path), result, domain=domain, tolerance=threshold
    )
    assert outcome.status is CheckStatus.ERROR
    assert not outcome.executed
    assert outcome.diagnostics[-1].code == "RC_RUNTIME_AGGREGATE_RESULT_INVALID"


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity")])
@pytest.mark.regression_capture("aggregate-core-grouped-summary")
def test_aggregate_grouped_decimal_nonfinite_extrema(tmp_path: Path, value: Decimal) -> None:
    row = (2, 1, 0, 0, 0, 1, 0, value, value)
    assert _compare(tmp_path, row, _D, grouped=True).status is CheckStatus.ERROR


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("status", [CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.ERROR])
@pytest.mark.regression_capture("aggregate-core-result-privacy")
def test_aggregate_comparison_does_not_publish_numeric_evidence(
    tmp_path: Path, grouped: bool, status: CheckStatus
) -> None:
    private = 739185729438765
    threshold = Decimal(private) if status is CheckStatus.PASS else Decimal(0)
    if grouped:
        row = (private, 0, 0, private - 1, 0, 1, 0, private, private)
        if status is CheckStatus.ERROR:
            row = (*row[:6], 1, private, private)
    else:
        row = (private, 0, private)
        if status is CheckStatus.ERROR:
            row = (private, 0, private + 1)
    result = _compare(tmp_path, row, _I, threshold, grouped=grouped)
    assert result.status is status
    assert str(private) not in repr(result)
    assert str(private) not in repr(result.to_dict())


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_runtime_requires_scan_decision(tmp_path: Path, grouped: bool) -> None:
    check = _compiled_aggregate(grouped=grouped)
    contract = _contract(tmp_path)
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.diagnostics[-1].code == "RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN"
    assert "aggregate" in result.diagnostics[-1].message.lower()
    assert "grain-key" not in result.diagnostics[-1].message.lower()


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    ("estimate_state", "code"),
    [
        (ScanEstimateState.PRESENT, "RC_RUNTIME_BOUNDED_LOCAL_SCAN_REQUIRED"),
        (ScanEstimateState.UNKNOWN, "RC_RUNTIME_SCAN_ESTIMATE_UNKNOWN"),
        (ScanEstimateState.UNAVAILABLE, "RC_RUNTIME_SCAN_ESTIMATE_UNSUPPORTED"),
        (ScanEstimateState.UNSUPPORTED, "RC_RUNTIME_SCAN_ESTIMATE_UNSUPPORTED"),
        (ScanEstimateState.MALFORMED, "RC_RUNTIME_SCAN_ESTIMATE_UNSUPPORTED"),
        (ScanEstimateState.OVER_BUDGET, "RC_RUNTIME_SCAN_BUDGET_EXCEEDED"),
        (ScanEstimateState.UNSAFE_PREFLIGHT, "RC_RUNTIME_UNSAFE_SCAN_PREFLIGHT"),
    ],
)
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_runtime_preserves_scan_blocker(
    tmp_path: Path, grouped: bool, estimate_state: ScanEstimateState, code: str
) -> None:
    check = _compiled_aggregate(grouped=grouped)
    contract = _contract(tmp_path)
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.PRODUCTION,
            relation_backed=True,
            bounded=False,
            estimate_state=estimate_state,
        )
    )
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
        scan_budget_decisions_by_check_id={check.id: decision},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.reason_code is decision.reason
    assert result.diagnostics[-1].code == code
    assert "aggregate" in result.diagnostics[-1].message.lower()
    assert "grain-key" not in repr(result.to_dict()).lower()


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("target_type", ["duckdb", "warehouse_test"])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_runtime_connection_context_precedes_scan(
    tmp_path: Path, grouped: bool, target_type: str
) -> None:
    check = _compiled_aggregate(grouped=grouped)
    contract = _contract(tmp_path)
    contract = replace(contract, target=replace(contract.target, connection="replica"))
    context = _AggregateExecutionContext(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={},
        connections_by_name={
            "warehouse": ConnectionConfig(
                name="warehouse", type="duckdb", config={"database": "private-source"}
            ),
            "replica": ConnectionConfig(
                name="replica", type=target_type, config={"database": "private-target"}
            ),
        },
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
    )
    result = _run_check(check, contract, context)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert result.diagnostics[-1].code == "RC_ADAPTER_CONNECTION_CONTEXT_UNSUPPORTED"
    assert "private-source" not in repr(result.to_dict())
    assert "private-target" not in repr(result.to_dict())


def _routing_plan(grouped: bool) -> _AggregateRuntimePlan:
    operation = "compare_grouped_aggregates" if grouped else "compare_aggregates"
    capabilities = ("grouped_aggregate" if grouped else "aggregate", "cte_support")

    def step(name: str) -> RenderedSql:
        return RenderedSql(
            sql=f"private-sql-{name}",
            operation_type=operation,
            step_name=name,
            required_capabilities=capabilities,
        )

    guards = ("group-key-types", "aggregate-input-types") if grouped else ("aggregate-input-types",)
    return _AggregateRuntimePlan(
        type_guards=tuple(step(name) for name in guards),
        domain_guard=step("aggregate-native-domain"),
        exact_query=step("aggregate-exact-result"),
        floating_query=step("aggregate-floating-result"),
        columns=_SUMMARY_COLUMNS if grouped else _SCALAR_COLUMNS,
        required_capabilities=capabilities,
    )


class _RoutingRenderer:
    adapter_type = "duckdb"

    def __init__(self, plan: object) -> None:
        self.plan = plan
        self.calls = 0

    def render_plan(self, operations: object, **kwargs: object) -> object:
        self.calls += 1
        return self.plan


class _RoutingAdapter:
    adapter_type = "duckdb"

    def __init__(
        self,
        connection: ConnectionConfig,
        results: list[object],
        *,
        missing: str | None = None,
    ) -> None:
        self.connection = connection
        self.results = results
        self.missing = missing
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            {
                name: CapabilitySupport.FULL
                for name in ("aggregate", "grouped_aggregate", "cte_support")
                if name != self.missing
            }
        )

    def execute(self, query: str) -> object:
        raise AssertionError("Public execute must not be used for aggregate runtime.")

    def _execute_aggregate_query(self, query: str, *, expected_columns: tuple[str, ...]) -> object:
        self.calls.append((query, expected_columns))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _route(
    tmp_path: Path,
    grouped: bool,
    adapter: object,
    renderer: object,
    *,
    tolerance: object = 0,
    scan_decision: ScanBudgetDecision | None = None,
) -> CheckResult:
    check = _compiled_aggregate(grouped=grouped, tolerance=tolerance)
    contract = _contract(tmp_path)
    connection = ConnectionConfig(name="warehouse", type="duckdb")
    decision = scan_decision
    if decision is None:
        decision = classify_scan_budget(
            ScanBudgetContext(
                environment=ScanExecutionEnvironment.LOCAL_DEV,
                relation_backed=True,
                bounded=True,
            )
        )
    # Explicit private collaborator shape; no public context expansion.
    context = SimpleNamespace(
        contracts_by_name={contract.contract_name: contract},
        adapters_by_connection={"warehouse": adapter},
        connections_by_name={"warehouse": connection},
        renderers_by_adapter_type={},
        aggregate_renderers_by_adapter_type={"duckdb": renderer},
        scan_budget_decisions_by_check_id={check.id: decision},
        tolerance_states_by_contract_id={contract.contract_id: _ToleranceReferenceState.ABSENT},
        aggregate_blockers_by_check_id={},
    )
    return _run_check(check, contract, context)


def _routing_results(grouped: bool, domain: _NumericDomain) -> list[object]:
    discriminator = {_I: 1, _D: 2, _F: 3}[domain]
    value = {_I: 1, _D: Decimal("1"), _F: 1.0}[domain]
    guard = _AggregateQueryResult(("type_check",), (_I,), (1,))
    proof = _AggregateQueryResult(("numeric_domain",), (_I,), (discriminator,))
    if grouped:
        final = _AggregateQueryResult(
            _SUMMARY_COLUMNS, (_I,) * 7 + (domain,) * 2, (1, 0, 0, 0, 0, 1, 0, value, value)
        )
    else:
        final = _AggregateQueryResult(_SCALAR_COLUMNS, (domain,) * 3, (value, value, value - value))
    return [guard] * (2 if grouped else 1) + [proof, final]


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("domain", [_I, _D, _F])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_runtime_executes_only_ordered_private_queries(
    tmp_path: Path, grouped: bool, domain: _NumericDomain
) -> None:
    plan = _routing_plan(grouped)
    adapter = _RoutingAdapter(
        ConnectionConfig(name="warehouse", type="duckdb"), _routing_results(grouped, domain)
    )
    renderer = _RoutingRenderer(plan)
    result = _route(tmp_path, grouped, adapter, renderer, tolerance=1)
    assert result.status is CheckStatus.PASS
    assert result.executed
    assert renderer.calls == 1
    assert adapter.calls == [
        *((guard.sql, ("type_check",)) for guard in plan.type_guards),
        (plan.domain_guard.sql, ("numeric_domain",)),
        (plan.final_query(domain).sql, plan.columns),
    ]
    assert not adapter.results
    assert "private-sql" not in repr(result.to_dict())


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    "broken", ["missing_renderer", "wrong_type", "public_shape", "no_executor"]
)
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_runtime_rejects_unproven_private_collaborators(
    tmp_path: Path, grouped: bool, broken: str
) -> None:
    connection = ConnectionConfig(name="warehouse", type="duckdb")
    adapter = _RoutingAdapter(connection, [])
    renderer = _RoutingRenderer(_routing_plan(grouped))
    if broken == "missing_renderer":
        renderer = None
    elif broken == "wrong_type":
        renderer.adapter_type = "other"
    elif broken == "public_shape":
        renderer.plan = ()
    elif broken == "no_executor":
        adapter._execute_aggregate_query = None
    result = _route(tmp_path, grouped, adapter, renderer)
    assert result.status in (CheckStatus.ERROR, CheckStatus.NOT_EXECUTABLE)
    assert result.diagnostics[-1].code != "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
    assert not result.executed
    assert adapter.calls == []


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("broken", ["guard", "domain", "exception"])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_runtime_stops_before_final_query_on_invalid_guard(
    tmp_path: Path, grouped: bool, broken: str
) -> None:
    results = _routing_results(grouped, _I)
    if broken == "guard":
        results[0] = _AggregateQueryResult(("type_check",), (_I,), (0,))
    elif broken == "domain":
        results[-2] = _AggregateQueryResult(("numeric_domain",), (_I,), (99,))
    else:
        results[0] = RuntimeError("private-query-error")
    adapter = _RoutingAdapter(ConnectionConfig(name="warehouse", type="duckdb"), results)
    result = _route(tmp_path, grouped, adapter, _RoutingRenderer(_routing_plan(grouped)))
    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert len(adapter.calls) == ((3 if grouped else 2) if broken == "domain" else 1)
    assert not any("result" in query for query, _ in adapter.calls)
    assert "private-query-error" not in repr(result.to_dict())


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize("malformed", ["truthy", "missing_proof", "contradictory", "wrong_object"])
@pytest.mark.regression_capture("aggregate-runtime-scan-preflight")
def test_aggregate_runtime_rejects_malformed_scan_approval(
    tmp_path: Path, grouped: bool, malformed: str
) -> None:
    decision = classify_scan_budget(
        ScanBudgetContext(
            environment=ScanExecutionEnvironment.LOCAL_DEV,
            relation_backed=True,
            bounded=True,
        )
    )
    if malformed == "wrong_object":
        decision = object()
    elif malformed == "truthy":
        decision = replace(decision, allowed="yes")
    elif malformed == "missing_proof":
        decision = replace(decision, diagnostics=())
    else:
        diagnostic = Diagnostic(
            code="RC_RUNTIME_SCAN_BUDGET_EXCEEDED",
            severity=DiagnosticSeverity.ERROR,
            message="private-scan-diagnostic",
        )
        decision = replace(decision, diagnostics=(*decision.diagnostics, diagnostic))
    adapter = _RoutingAdapter(
        ConnectionConfig(name="warehouse", type="duckdb"), _routing_results(grouped, _I)
    )
    renderer = _RoutingRenderer(_routing_plan(grouped))
    result = _route(tmp_path, grouped, adapter, renderer, tolerance=1, scan_decision=decision)
    assert result.status is CheckStatus.NOT_EXECUTABLE
    assert not result.executed
    assert adapter.calls == []
    assert renderer.calls == 0
    assert "private-scan-diagnostic" not in repr(result.to_dict())


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_runtime_rejects_duplicate_rendered_capabilities(
    tmp_path: Path, grouped: bool
) -> None:
    plan = _routing_plan(grouped)
    plan = replace(plan, required_capabilities=(*plan.required_capabilities, "cte_support"))
    adapter = _RoutingAdapter(
        ConnectionConfig(name="warehouse", type="duckdb"), _routing_results(grouped, _I)
    )
    result = _route(tmp_path, grouped, adapter, _RoutingRenderer(plan), tolerance=1)
    assert result.status is CheckStatus.ERROR
    assert result.diagnostics[-1].code == "RC_ADAPTER_RENDERER_METADATA_INVALID"
    assert adapter.calls == []


@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.regression_capture("aggregate-runtime-private-routing")
def test_aggregate_runtime_missing_prepared_adapter_is_error(tmp_path: Path, grouped: bool) -> None:
    renderer = _RoutingRenderer(_routing_plan(grouped))
    result = _route(tmp_path, grouped, None, renderer)
    assert result.status is CheckStatus.ERROR
    assert not result.executed
    assert result.diagnostics[-1].code == "RC_ADAPTER_RENDERER_METADATA_INVALID"
    assert renderer.calls == 0
