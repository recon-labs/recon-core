"""Internal dispatch boundary for compiled checks."""

from dataclasses import dataclass
from typing import Final

from recon_core.artifacts import LoadedCompiledCheck
from recon_core.check_engine.models import CheckReason, CheckResult, CheckStatus
from recon_core.compiler.models import CompiledCheckType, OperationType
from recon_core.diagnostics import Diagnostic, DiagnosticSeverity

CHECK_NOT_EXECUTABLE = "RC_RUNTIME_CHECK_NOT_EXECUTABLE"
UNSUPPORTED_CHECK_TYPE = "RC_RUNTIME_UNSUPPORTED_CHECK_TYPE"
UNSUPPORTED_TYPED_OPERATION = "RC_RUNTIME_UNSUPPORTED_TYPED_OPERATION"
MISSING_ENGINE_CAPABILITY = "RC_RUNTIME_MISSING_ENGINE_CAPABILITY"
UNSUPPORTED_EXECUTION_PLACEMENT = "RC_RUNTIME_UNSUPPORTED_EXECUTION_PLACEMENT"
UNSUPPORTED_MATERIALIZATION_POLICY = "RC_RUNTIME_UNSUPPORTED_MATERIALIZATION_POLICY"

_KNOWN_LATER_PHASE_CHECK_TYPES: Final[frozenset[str]] = frozenset(
    check_type.value for check_type in CompiledCheckType
)
_KNOWN_TYPED_OPERATION_TYPES: Final[frozenset[str]] = frozenset(
    operation_type.value for operation_type in OperationType
)
_EMPTY_MATERIALIZATION_POLICIES = {None, "", "none", "not_applicable"}


@dataclass(frozen=True, slots=True)
class _DispatchClassification:
    reason: CheckReason
    diagnostic_code: str
    message: str


class CheckDispatcher:
    """Classify loaded compiled checks without executing them."""

    def dispatch(self, check: LoadedCompiledCheck) -> CheckResult:
        classification = _classify(check)
        diagnostic = _diagnostic_for(check, classification)
        return CheckResult(
            check_id=check.id,
            name=check.name,
            check_type=check.check_type,
            contract_name=check.contract_name,
            status=CheckStatus.NOT_EXECUTABLE,
            executed=False,
            reason_code=classification.reason,
            identity=_identity_label(check),
            message=classification.message,
            diagnostics=check.diagnostics + (diagnostic,),
        )


def _classify(check: LoadedCompiledCheck) -> _DispatchClassification:
    if check.check_type not in _KNOWN_LATER_PHASE_CHECK_TYPES:
        return _DispatchClassification(
            reason=CheckReason.UNSUPPORTED_CHECK_TYPE,
            diagnostic_code=UNSUPPORTED_CHECK_TYPE,
            message=(
                f"Compiled check type `{check.check_type}` is not supported by "
                "the current check-engine boundary."
            ),
        )

    unsupported_operation = _first_unsupported_operation_type(check)
    if unsupported_operation is not None:
        return _DispatchClassification(
            reason=CheckReason.UNSUPPORTED_TYPED_OPERATION,
            diagnostic_code=UNSUPPORTED_TYPED_OPERATION,
            message=(
                f"Typed operation `{unsupported_operation}` is not supported by "
                "the current check-engine boundary."
            ),
        )

    placement_operation = _operation_with_any_key(
        check,
        keys=("execution_placement", "comparison_location"),
    )
    if placement_operation is not None:
        return _DispatchClassification(
            reason=CheckReason.UNSUPPORTED_EXECUTION_PLACEMENT,
            diagnostic_code=UNSUPPORTED_EXECUTION_PLACEMENT,
            message=(
                f"Check `{check.name}` requires execution placement that is not "
                "implemented in the current check-engine boundary."
            ),
        )

    materialization_operation = _operation_with_materialization_policy(check)
    if materialization_operation is not None:
        return _DispatchClassification(
            reason=CheckReason.UNSUPPORTED_MATERIALIZATION_POLICY,
            diagnostic_code=UNSUPPORTED_MATERIALIZATION_POLICY,
            message=(
                f"Check `{check.name}` requires materialization policy that is not "
                "implemented in the current check-engine boundary."
            ),
        )

    missing_capability = _first_required_engine_capability(check)
    if missing_capability is not None:
        return _DispatchClassification(
            reason=CheckReason.MISSING_ENGINE_CAPABILITY,
            diagnostic_code=MISSING_ENGINE_CAPABILITY,
            message=(
                f"Check `{check.name}` requires engine capability "
                f"`{missing_capability}` that is not available in the current "
                "check-engine boundary."
            ),
        )

    return _DispatchClassification(
        reason=CheckReason.NOT_IMPLEMENTED_IN_CURRENT_PHASE,
        diagnostic_code=CHECK_NOT_EXECUTABLE,
        message=(f"Check `{check.name}` belongs to a later execution phase and did not run."),
    )


def _operation_with_any_key(
    check: LoadedCompiledCheck,
    *,
    keys: tuple[str, ...],
) -> dict[str, object] | None:
    for operation in check.plan.operations:
        if any(key in operation and operation[key] not in {None, ""} for key in keys):
            return operation
    return None


def _operation_with_materialization_policy(
    check: LoadedCompiledCheck,
) -> dict[str, object] | None:
    for operation in check.plan.operations:
        if operation.get("materialization_policy") not in _EMPTY_MATERIALIZATION_POLICIES:
            return operation
    return None


def _first_required_engine_capability(check: LoadedCompiledCheck) -> str | None:
    for capability in check.plan.required_capabilities:
        if capability:
            return capability
    return None


def _first_unsupported_operation_type(check: LoadedCompiledCheck) -> str | None:
    for operation in check.plan.operations:
        operation_type = operation.get("type")
        if not isinstance(operation_type, str):
            return None
        if operation_type not in _KNOWN_TYPED_OPERATION_TYPES:
            return operation_type
    return None


def _identity_label(check: LoadedCompiledCheck) -> str | None:
    payload = check.payload
    if payload is None:
        return None
    identity = payload.get("identity")
    if not isinstance(identity, dict):
        return None
    kind = identity.get("kind")
    return kind if isinstance(kind, str) else None


def _diagnostic_for(
    check: LoadedCompiledCheck,
    classification: _DispatchClassification,
) -> Diagnostic:
    return Diagnostic(
        code=classification.diagnostic_code,
        severity=DiagnosticSeverity.ERROR,
        message=classification.message,
        resource_type="compiled_check",
        resource_name=f"{check.contract_name}.{check.name}",
        hint="Run a later execution phase after its gate and implementation are complete.",
    )
