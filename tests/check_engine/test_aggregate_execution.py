"""Private aggregate admission and shared numeric policy tests."""

from dataclasses import fields, replace
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from recon_core._numeric_policy import absolute_tolerance
from recon_core.adapters._aggregate_runtime import (
    _SCALAR_COLUMNS,
    _SUMMARY_COLUMNS,
    _AggregateQueryResult,
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
