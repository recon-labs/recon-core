"""Explicit metric compilation into aggregate comparison checks."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from recon_core.compiler.ids import build_check_id, build_plan_id
from recon_core.compiler.models import (
    AdapterCapability,
    CheckOrigin,
    CheckOriginKind,
    CheckPlan,
    CheckRequirements,
    CompiledCheck,
    CompiledCheckType,
    CompiledMetric,
    Identity,
    IdentityKind,
    OperationSide,
    TypedOperation,
)
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

DUPLICATE_METRIC_NAME = "RC_VALIDATE_DUPLICATE_METRIC_NAME"
INVALID_METRIC = "RC_VALIDATE_INVALID_METRIC"
UNSUPPORTED_METRIC_TYPE = "RC_VALIDATE_UNSUPPORTED_METRIC_TYPE"
SUPPORTED_METRIC_TYPES = frozenset({"sum"})


@dataclass(frozen=True, slots=True)
class MetricCompilationResult:
    """Result of compiling explicit metrics."""

    checks: tuple[CompiledCheck, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not any(
            diagnostic.severity is DiagnosticSeverity.ERROR for diagnostic in self.diagnostics
        )


@dataclass(frozen=True, slots=True)
class _MetricDefinition:
    name: str
    metric_type: str
    column: str
    group_by: tuple[str, ...] = ()


def compile_metrics(
    metrics: Sequence[Mapping[str, object]],
    *,
    project_name: str,
    contract_name: str,
) -> MetricCompilationResult:
    """Compile explicit authored metrics into aggregate comparison checks."""
    parsed_metrics: list[_MetricDefinition] = []
    diagnostics: list[Diagnostic] = []
    seen_names: set[str] = set()

    for raw_metric in metrics:
        metric = _parse_metric(raw_metric)
        if metric is None:
            diagnostics.append(_invalid_metric_diagnostic())
            continue

        if metric.name in seen_names:
            diagnostics.append(_duplicate_metric_diagnostic(metric.name))
            continue
        seen_names.add(metric.name)

        if metric.metric_type not in SUPPORTED_METRIC_TYPES:
            diagnostics.append(_unsupported_metric_type_diagnostic(metric.name, metric.metric_type))
            continue

        parsed_metrics.append(metric)

    if diagnostics:
        return MetricCompilationResult(diagnostics=tuple(diagnostics))

    return MetricCompilationResult(
        checks=tuple(
            _compile_metric(metric, project_name=project_name, contract_name=contract_name)
            for metric in parsed_metrics
        )
    )


def _parse_metric(raw_metric: Mapping[str, object]) -> _MetricDefinition | None:
    name = raw_metric.get("name")
    metric_type = raw_metric.get("type")
    column = raw_metric.get("column")
    group_by = raw_metric.get("group_by", ())

    if not isinstance(name, str) or not name:
        return None
    if not isinstance(metric_type, str) or not metric_type:
        return None
    if not isinstance(column, str) or not column:
        return None
    if not isinstance(group_by, list | tuple):
        return None
    if not all(isinstance(group, str) and group for group in group_by):
        return None

    return _MetricDefinition(
        name=name,
        metric_type=metric_type,
        column=column,
        group_by=tuple(group_by),
    )


def _compile_metric(
    metric: _MetricDefinition,
    *,
    project_name: str,
    contract_name: str,
) -> CompiledCheck:
    capability = (
        AdapterCapability.GROUPED_AGGREGATE if metric.group_by else AdapterCapability.AGGREGATE
    )
    check_type = (
        CompiledCheckType.GROUPED_AGGREGATE_DIFF if metric.group_by else CompiledCheckType.SUM_DIFF
    )
    plan = (
        _grouped_aggregate_plan(metric, project_name, contract_name)
        if metric.group_by
        else _aggregate_plan(metric, project_name, contract_name)
    )

    return CompiledCheck(
        id=build_check_id(project_name, contract_name, metric.name),
        name=metric.name,
        check_type=check_type,
        origin=CheckOrigin(kind=CheckOriginKind.METRIC, name=metric.name),
        identity=Identity(kind=IdentityKind.NONE),
        requirements=CheckRequirements(
            required_columns=(metric.column, *metric.group_by),
            required_metrics=(metric.name,),
            required_capabilities=(capability,),
        ),
        metric=CompiledMetric(
            metric_type=metric.metric_type,
            column=metric.column,
            group_by=metric.group_by,
        ),
        plan=plan,
    )


def _aggregate_plan(
    metric: _MetricDefinition,
    project_name: str,
    contract_name: str,
) -> CheckPlan:
    capability = AdapterCapability.AGGREGATE
    return CheckPlan(
        id=build_plan_id(project_name, contract_name, metric.name),
        operations=(
            TypedOperation.aggregate(
                side=OperationSide.SOURCE,
                aggregate=metric.metric_type,
                column=metric.column,
            ),
            TypedOperation.aggregate(
                side=OperationSide.TARGET,
                aggregate=metric.metric_type,
                column=metric.column,
            ),
            TypedOperation.compare_aggregates(),
        ),
        required_capabilities=(capability,),
    )


def _grouped_aggregate_plan(
    metric: _MetricDefinition,
    project_name: str,
    contract_name: str,
) -> CheckPlan:
    capability = AdapterCapability.GROUPED_AGGREGATE
    return CheckPlan(
        id=build_plan_id(project_name, contract_name, metric.name),
        operations=(
            TypedOperation.grouped_aggregate(
                side=OperationSide.SOURCE,
                aggregate=metric.metric_type,
                column=metric.column,
                group_by=metric.group_by,
            ),
            TypedOperation.grouped_aggregate(
                side=OperationSide.TARGET,
                aggregate=metric.metric_type,
                column=metric.column,
                group_by=metric.group_by,
            ),
            TypedOperation.compare_grouped_aggregates(),
        ),
        required_capabilities=(capability,),
    )


def _duplicate_metric_diagnostic(metric_name: str) -> Diagnostic:
    return Diagnostic(
        code=DUPLICATE_METRIC_NAME,
        severity=DiagnosticSeverity.ERROR,
        message=f"Metric name {metric_name} is defined more than once.",
        resource_type="metric",
        resource_name=metric_name,
        hint="Metric names must be unique within a contract.",
    )


def _invalid_metric_diagnostic() -> Diagnostic:
    return Diagnostic(
        code=INVALID_METRIC,
        severity=DiagnosticSeverity.ERROR,
        message="Metric definitions require string `name`, `type`, and `column` fields.",
        resource_type="metric",
        hint="Use a supported explicit metric such as `name`, `type: sum`, and `column`.",
    )


def _unsupported_metric_type_diagnostic(metric_name: str, metric_type: str) -> Diagnostic:
    return Diagnostic(
        code=UNSUPPORTED_METRIC_TYPE,
        severity=DiagnosticSeverity.ERROR,
        message=f"Metric {metric_name} has unsupported type {metric_type}.",
        resource_type="metric",
        resource_name=metric_name,
        hint="Only `sum` metrics are supported in the current compiler milestone.",
    )
