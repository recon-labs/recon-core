"""Admission and bounded comparison for the explicit aggregate execution family."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from recon_core._numeric_policy import absolute_tolerance
from recon_core.adapters._aggregate_runtime import (
    _SCALAR_COLUMNS,
    _SUMMARY_COLUMNS,
    _AggregateQueryResult,
    _NumericDomain,
)
from recon_core.adapters.rendering import ADAPTER_QUERY_ENDPOINT_UNSUPPORTED
from recon_core.artifacts.compiled_check_loader import (
    COMPILED_CHECK_ARTIFACT_INVALID,
    LoadedCompiledCheck,
)
from recon_core.artifacts.compiled_contract_loader import (
    COMPILED_CONTRACT_ARTIFACT_INVALID,
    LoadedCompiledContractArtifact,
    _ToleranceReferenceState,
)
from recon_core.check_engine.dispatch import UNSUPPORTED_TYPED_OPERATION
from recon_core.check_engine.execution_support import (
    error_result,
    has_materialization_policy,
    has_reserved_value,
    not_executable_result,
    relation_from_name,
)
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.check_engine.result_metadata import identity_label
from recon_core.compiled_artifact_schema import typed_operation_payload_fields
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

_TOLERANCE_POLICY_UNRESOLVED = "RC_RUNTIME_AGGREGATE_TOLERANCE_POLICY_UNRESOLVED"
_AGGREGATE_TYPES = frozenset({"sum_diff", "grouped_aggregate_diff"})


@dataclass(frozen=True, slots=True)
class _AggregateAdmission:
    tolerance: Decimal | None = None
    blocker: CheckResult | None = None


def is_aggregate_check_type(check_type: str) -> bool:
    return check_type in _AGGREGATE_TYPES


def _operation_fields_supported(operation: Mapping[str, object]) -> bool:
    operation_type = operation.get("type")
    if not isinstance(operation_type, str):
        return False
    payload_fields = typed_operation_payload_fields(operation_type)
    if payload_fields is None:
        return False
    if any(
        has_reserved_value(operation.get(key))
        for key in ("execution_placement", "comparison_location")
    ):
        return False
    if has_materialization_policy(operation.get("materialization_policy")):
        return False
    allowed_fields = payload_fields | {
        "type",
        "execution_placement",
        "comparison_location",
        "materialization_policy",
    }
    return set(operation).issubset(allowed_fields)


def is_supported_aggregate_plan_shape(check: LoadedCompiledCheck) -> bool:
    if not is_aggregate_check_type(check.check_type) or len(check.plan.operations) != 3:
        return False
    if not all(_operation_fields_supported(operation) for operation in check.plan.operations):
        return False
    source, target, comparison = check.plan.operations
    grouped = check.check_type == "grouped_aggregate_diff"
    operation_type = "grouped_aggregate" if grouped else "aggregate"
    comparison_type = "compare_grouped_aggregates" if grouped else "compare_aggregates"
    if comparison.get("type") != comparison_type:
        return False
    column = source.get("column")
    if not isinstance(column, str) or not column or column == "*":
        return False
    groups = source.get("group_by", [])
    if not isinstance(groups, list):
        return False
    if grouped != bool(groups) or any(
        not isinstance(key, str) or not key or key == "*" for key in groups
    ):
        return False
    for operation, side in ((source, "source"), (target, "target")):
        if (
            operation.get("type") != operation_type
            or operation.get("side") != side
            or operation.get("aggregate") != "sum"
            or operation.get("column") != column
            or operation.get("group_by", []) != groups
        ):
            return False
    payload = check.payload
    if not isinstance(payload, Mapping):
        return False
    if payload.get("identity") != {"kind": "none", "keys": []}:
        return False
    return payload.get("metric") == {"type": "sum", "column": column, "group_by": groups}


def _invalid_policy(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    *,
    code: str,
    message: str,
) -> _AggregateAdmission:
    diagnostic = Diagnostic(
        code=code,
        severity=DiagnosticSeverity.ERROR,
        message=message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint="Regenerate compiled artifacts with `recon compile`.",
    )
    return _AggregateAdmission(
        blocker=error_result(check, contract, message=message, diagnostics=(diagnostic,))
    )


def aggregate_admission(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    tolerance_state: _ToleranceReferenceState | None,
) -> _AggregateAdmission:
    """Validate the compiled aggregate plan and policy without querying an adapter."""
    if not is_supported_aggregate_plan_shape(check):
        return _AggregateAdmission(
            blocker=not_executable_result(
                check,
                contract,
                reason=CheckReason.UNSUPPORTED_TYPED_OPERATION,
                diagnostic_code=UNSUPPORTED_TYPED_OPERATION,
                message="Only matching explicit sum aggregate plans are supported.",
                hint="Regenerate the compiled aggregate plan with `recon compile`.",
            )
        )
    if contract.source.query is not None or contract.target.query is not None:
        return _AggregateAdmission(
            blocker=not_executable_result(
                check,
                contract,
                reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
                diagnostic_code=ADAPTER_QUERY_ENDPOINT_UNSUPPORTED,
                message="Aggregate execution requires relation-backed endpoints.",
                hint="Use compiled relation endpoints for the source and target.",
            )
        )
    for side, endpoint in (("source", contract.source), ("target", contract.target)):
        _, diagnostic = relation_from_name(
            endpoint.relation, side=side, contract_name=contract.contract_name
        )
        if diagnostic is not None:
            return _AggregateAdmission(
                blocker=error_result(
                    check, contract, message=diagnostic.message, diagnostics=(diagnostic,)
                )
            )

    assert check.payload is not None
    explicit = check.payload.get("tolerance")
    tolerance = absolute_tolerance(explicit) if explicit is not None else None
    if explicit is not None and tolerance is None:
        return _invalid_policy(
            check,
            contract,
            code=COMPILED_CHECK_ARTIFACT_INVALID,
            message="Compiled aggregate tolerance must be a finite non-negative absolute policy.",
        )
    if tolerance_state is _ToleranceReferenceState.INVALID:
        return _invalid_policy(
            check,
            contract,
            code=COMPILED_CONTRACT_ARTIFACT_INVALID,
            message="Compiled contract tolerance policy metadata is invalid.",
        )
    if tolerance_state not in {
        _ToleranceReferenceState.ABSENT,
        _ToleranceReferenceState.UNRESOLVED,
    } or (tolerance_state is _ToleranceReferenceState.UNRESOLVED and tolerance is None):
        return _AggregateAdmission(
            blocker=not_executable_result(
                check,
                contract,
                reason=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
                diagnostic_code=_TOLERANCE_POLICY_UNRESOLVED,
                message="Applicable aggregate tolerance policy is unresolved or unverified.",
                hint="Provide a valid explicit metric tolerance and verified compiled metadata.",
            )
        )
    return _AggregateAdmission(tolerance=tolerance if tolerance is not None else Decimal(0))


class _InvalidAggregateResult(ValueError):
    """The bounded evidence cannot establish a trustworthy outcome."""


def _validated_number(value: object, domain: _NumericDomain) -> int | Decimal | float:
    if domain is _NumericDomain.EXACT_INTEGER and type(value) is int:
        return value
    if domain is _NumericDomain.EXACT_DECIMAL and type(value) is Decimal and value.is_finite():
        return value
    if domain is _NumericDomain.NATIVE_FLOAT and type(value) is float and math.isfinite(value):
        return value
    raise _InvalidAggregateResult


def _magnitude(value: int | Decimal | float) -> int | Decimal:
    if isinstance(value, float):
        # Interpret the computed native difference, not independently converted operands.
        return Decimal(str(abs(value)))
    if isinstance(value, Decimal):
        return value.copy_abs()
    return abs(value)


def _scalar_comparison(
    row: tuple[object, ...], domain: _NumericDomain, tolerance: Decimal
) -> CheckStatus:
    source, target, difference = (
        None if value is None else _validated_number(value, domain) for value in row
    )
    if source is None or target is None:
        if difference is not None:
            raise _InvalidAggregateResult
        return CheckStatus.PASS if source is target else CheckStatus.FAIL
    if difference is None:
        raise _InvalidAggregateResult
    if domain is _NumericDomain.NATIVE_FLOAT:
        assert isinstance(source, float) and isinstance(target, float)
        if source - target != difference:
            raise _InvalidAggregateResult
    elif Fraction(source) - Fraction(target) != Fraction(difference):
        # Rational subtraction is exact even under a low ambient Decimal precision.
        raise _InvalidAggregateResult
    return CheckStatus.PASS if _magnitude(difference) <= tolerance else CheckStatus.FAIL


def _grouped_comparison(
    row: tuple[object, ...], domain: _NumericDomain, tolerance: Decimal
) -> CheckStatus:
    counts: list[int] = []
    for value in row[:7]:
        if type(value) is not int or value < 0:
            raise _InvalidAggregateResult
        counts.append(value)
    total, source_only, target_only, both_null, null_mismatch, valid, invalid = counts
    if total != source_only + target_only + both_null + null_mismatch + valid + invalid:
        raise _InvalidAggregateResult

    minimum, maximum = row[7:]
    if valid == 0:
        if minimum is not None or maximum is not None:
            raise _InvalidAggregateResult
        within_tolerance = True
    else:
        low = _validated_number(minimum, domain)
        high = _validated_number(maximum, domain)
        if low > high or (valid == 1 and low != high):
            raise _InvalidAggregateResult
        within_tolerance = max(_magnitude(low), _magnitude(high)) <= tolerance

    if invalid:
        raise _InvalidAggregateResult
    if source_only or target_only or null_mismatch or not within_tolerance:
        return CheckStatus.FAIL
    return CheckStatus.PASS


def _compare_aggregate_result(
    check: LoadedCompiledCheck,
    contract: LoadedCompiledContractArtifact,
    result: _AggregateQueryResult,
    *,
    domain: _NumericDomain,
    tolerance: Decimal,
) -> CheckResult:
    """Classify bounded typed evidence without exposing its private values."""
    grouped = check.check_type == "grouped_aggregate_diff"
    columns = _SUMMARY_COLUMNS if grouped else _SCALAR_COLUMNS
    domains = (_NumericDomain.EXACT_INTEGER,) * 7 + (domain,) * 2 if grouped else (domain,) * 3
    try:
        if (
            not is_aggregate_check_type(check.check_type)
            or type(domain) is not _NumericDomain
            or type(tolerance) is not Decimal
            or not tolerance.is_finite()
            or tolerance < 0
            or type(result) is not _AggregateQueryResult
            or type(result.columns) is not tuple
            or result.columns != columns
            or type(result.domains) is not tuple
            or len(result.domains) != len(domains)
            or any(
                actual is not expected
                for actual, expected in zip(result.domains, domains, strict=True)
            )
            or type(result.row) is not tuple
            or len(result.row) != len(columns)
        ):
            raise _InvalidAggregateResult
        compare = _grouped_comparison if grouped else _scalar_comparison
        status = compare(result.row, domain, tolerance)
    except _InvalidAggregateResult:
        message = "Aggregate execution returned invalid or untrustworthy numeric evidence."
        diagnostic = Diagnostic(
            code="RC_RUNTIME_AGGREGATE_RESULT_INVALID",
            severity=DiagnosticSeverity.ERROR,
            message=message,
            resource_type="compiled_check",
            resource_name=f"{check.contract_name}.{check.name}",
        )
        return error_result(check, contract, message=message, diagnostics=(diagnostic,))

    return CheckResult(
        check_id=check.id,
        name=check.name,
        check_type=check.check_type,
        contract_name=check.contract_name,
        status=status,
        executed=True,
        identity=identity_label(check),
        message=(
            "Aggregate check passed." if status is CheckStatus.PASS else "Aggregate check failed."
        ),
        diagnostics=check.diagnostics + contract.diagnostics,
    )
