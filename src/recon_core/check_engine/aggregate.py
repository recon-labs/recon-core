"""Admission policy for the current explicit aggregate execution family."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from recon_core._numeric_policy import absolute_tolerance
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
from recon_core.check_engine.models import CheckReason, CheckResult
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
