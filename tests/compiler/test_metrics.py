from recon_core.compiler.ids import INVALID_STABLE_ID_PART
from recon_core.compiler.metrics import (
    DUPLICATE_METRIC_NAME,
    UNKNOWN_METRIC_FIELD,
    UNSUPPORTED_METRIC_TYPE,
    compile_metrics,
)
from recon_core.compiler.models import (
    AdapterCapability,
    CheckOriginKind,
    CompiledCheckType,
    IdentityKind,
    OperationSide,
    OperationType,
)
from recon_core.diagnostics import DiagnosticSeverity


def test_compile_metrics_returns_no_checks_for_no_metrics() -> None:
    result = compile_metrics(
        (),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert result.succeeded
    assert result.checks == ()
    assert result.diagnostics == ()


def test_ungrouped_sum_metric_compiles_to_sum_diff_with_compare_aggregates() -> None:
    result = compile_metrics(
        ({"name": "total_revenue", "type": "sum", "column": "revenue"},),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert result.succeeded
    assert len(result.checks) == 1

    check = result.checks[0]
    assert check.id == "check.ecommerce_recon.customer_revenue.total_revenue"
    assert check.name == "total_revenue"
    assert check.check_type is CompiledCheckType.SUM_DIFF
    assert check.origin.kind is CheckOriginKind.METRIC
    assert check.origin.name == "total_revenue"
    assert check.identity.kind is IdentityKind.NONE
    assert check.identity.keys == ()
    assert not check.requirements.requires_grain_keys
    assert check.requirements.required_columns == ("revenue",)
    assert check.requirements.required_metrics == ("total_revenue",)
    assert check.requirements.required_capabilities == (AdapterCapability.AGGREGATE,)
    assert check.metric is not None
    assert check.metric.to_dict() == {
        "type": "sum",
        "column": "revenue",
        "group_by": [],
    }
    assert check.to_dict()["metric"] == {
        "type": "sum",
        "column": "revenue",
        "group_by": [],
    }
    assert check.plan.to_dict() == {
        "id": "plan.ecommerce_recon.customer_revenue.total_revenue",
        "operations": [
            {
                "type": "aggregate",
                "side": "source",
                "aggregate": "sum",
                "column": "revenue",
            },
            {
                "type": "aggregate",
                "side": "target",
                "aggregate": "sum",
                "column": "revenue",
            },
            {"type": "compare_aggregates"},
        ],
        "required_capabilities": ["aggregate"],
    }


def test_grouped_sum_metric_compiles_to_grouped_aggregate_diff() -> None:
    result = compile_metrics(
        (
            {
                "name": "revenue_by_month",
                "type": "sum",
                "column": "revenue",
                "group_by": ["month"],
            },
        ),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert result.succeeded
    assert len(result.checks) == 1

    check = result.checks[0]
    assert check.name == "revenue_by_month"
    assert check.check_type is CompiledCheckType.GROUPED_AGGREGATE_DIFF
    assert check.requirements.required_columns == ("revenue", "month")
    assert check.requirements.required_capabilities == (AdapterCapability.GROUPED_AGGREGATE,)
    assert check.metric is not None
    assert check.metric.group_by == ("month",)
    assert [operation.type for operation in check.plan.operations] == [
        OperationType.GROUPED_AGGREGATE,
        OperationType.GROUPED_AGGREGATE,
        OperationType.COMPARE_GROUPED_AGGREGATES,
    ]
    assert check.plan.operations[0].side is OperationSide.SOURCE
    assert check.plan.operations[0].group_by == ("month",)
    assert check.plan.operations[1].side is OperationSide.TARGET
    assert check.plan.operations[1].group_by == ("month",)


def test_metric_compilation_does_not_depend_on_grain_keys() -> None:
    result = compile_metrics(
        ({"name": "total_revenue", "type": "sum", "column": "revenue"},),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    check = result.checks[0]

    assert check.identity.kind is IdentityKind.NONE
    assert not check.requirements.requires_grain_keys
    assert not check.requirements.requires_non_null_grain
    assert not check.requirements.requires_unique_grain


def test_duplicate_metric_names_fail_validation_without_checks() -> None:
    result = compile_metrics(
        (
            {"name": "total_revenue", "type": "sum", "column": "revenue"},
            {"name": "total_revenue", "type": "sum", "column": "net_revenue"},
        ),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert not result.succeeded
    assert result.checks == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == DUPLICATE_METRIC_NAME
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "metric"
    assert diagnostic.resource_name == "total_revenue"
    assert "defined more than once" in diagnostic.message


def test_unknown_metric_fields_fail_validation_without_checks() -> None:
    result = compile_metrics(
        (
            {
                "name": "total_revenue",
                "type": "sum",
                "column": "revenue",
                "tolerence": 0.01,
            },
        ),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert not result.succeeded
    assert result.checks == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [UNKNOWN_METRIC_FIELD]
    assert result.diagnostics[0].resource_name == "total_revenue"
    assert "tolerence" in result.diagnostics[0].message


def test_unsupported_metric_type_fails_validation_without_checks() -> None:
    result = compile_metrics(
        ({"name": "average_revenue", "type": "avg", "column": "revenue"},),
        project_name="ecommerce_recon",
        contract_name="customer_revenue",
    )

    assert not result.succeeded
    assert result.checks == ()
    assert len(result.diagnostics) == 1

    diagnostic = result.diagnostics[0]
    assert diagnostic.code == UNSUPPORTED_METRIC_TYPE
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.resource_type == "metric"
    assert diagnostic.resource_name == "average_revenue"
    assert "unsupported type avg" in diagnostic.message


def test_metric_compilation_invalid_project_or_contract_id_parts_fail_without_exception() -> None:
    result = compile_metrics(
        ({"name": "total_revenue", "type": "sum", "column": "revenue"},),
        project_name="ecommerce-recon",
        contract_name="customer-revenue",
    )

    assert not result.succeeded
    assert result.checks == ()
    assert [diagnostic.code for diagnostic in result.diagnostics] == [
        INVALID_STABLE_ID_PART,
        INVALID_STABLE_ID_PART,
    ]
    assert [diagnostic.resource_type for diagnostic in result.diagnostics] == [
        "project",
        "contract",
    ]
